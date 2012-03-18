import functools
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpRequest
import django.utils.log
from django_counters.db_store.reporters import ViewReporter

import pycounters
from pycounters.base import THREAD_DISPATCHER, GLOBAL_DISPATCHER, EventLogger
from pycounters.counters import AverageTimeCounter, ThreadTimeCategorizer, FrequencyCounter, AverageWindowCounter
from pycounters.reporters import LogReporter, JSONFileReporter
from django.conf import settings
import django.db.backends.util


if not hasattr(settings,"DJANGO_COUNTERS"):
    raise ImproperlyConfigured("Django settings must contain a DJANGO_COUNTERS entry.")

# wrap django db access layer.
from pycounters.utils import patcher

@pycounters.report_start_end("db_access")
def patched_execute(self,*args,**kwargs):
    return self.cursor.execute(*args,**kwargs)

@pycounters.report_start_end("db_access")
def patched_executemany(self,*args,**kwargs):
    return self.cursor.executemany(*args,**kwargs)


# we cannot use PyCounters' patching utility as CursorWrapper is a proxy
django.db.backends.util.CursorWrapper.execute = patched_execute
django.db.backends.util.CursorWrapper.executemany = patched_executemany


# wrap django's internals with events
DJANGO_EVENTS_SCHEME=[
        {"class" : "django.db.backends.util.CursorDebugWrapper","method":"execute","event":"db_access"},
        {"class" : "django.db.backends.util.CursorDebugWrapper","method":"executemany","event":"db_access"},
        {"class" : "django.template.Template","method":"render","event":"templating"},
]

patcher.execute_patching_scheme(DJANGO_EVENTS_SCHEME)

def count_view(name=None,categories=[],slow_request_threshold=settings.DJANGO_COUNTERS["slow_request_threshold"]):

    def decorater(func):
        view_name = name if name else func.__name__
        event_name = "v_" + view_name # prefix all counters with v_

        view_categories=[]
        if categories:
            view_categories.extend(categories)
        else:
            dvc =  settings.DJANGO_COUNTERS.get("default_view_categories")
            if dvc: view_categories.extend(dvc)

        if view_categories:
            view_categories.append("rest")
            for counter in view_categories:
                c = AverageWindowCounter(event_name + "." + counter)
                pycounters.register_counter(c,throw_if_exists=False)

        c = AverageTimeCounter(event_name+"._total",events=[event_name])
        pycounters.register_counter(c,throw_if_exists=False)

        c = FrequencyCounter(event_name+"._rps",events=[event_name])
        pycounters.register_counter(c,throw_if_exists=False)

        slow_logger = django.utils.log.getLogger(name="slow_requests")

        func = pycounters.report_start_end("rest")(func)

        @pycounters.report_start_end(event_name)
        @functools.wraps(func)
        def wrapper(*args,**kwargs):
            tc=ThreadTimeCategorizer(event_name,view_categories)
            THREAD_DISPATCHER.add_listener(tc)
            try:
              r=func(*args,**kwargs)
              if slow_request_threshold:
                  times = tc.get_times()
                  total = sum([v for k,v in times])
                  if total > slow_request_threshold:
                      # Get the request from args, this can be either index 0 or 1
                      # depening on whether django view functions or classes are used
                      request = None
                      for arg in args:
                          if isinstance(arg, HttpRequest):
                              request = arg
                              break

                      assert request is not None, \
                        "Request object not found in args for view: %s" % view_name

                      slow_logger.warning(("Slow request (TIME: {total}): {url} \n"+
                                          "    USER: {user} \n"+
                                          "    GET: {get!r} \n"+
                                          "    POST: {post!r} \n"+
                                          "    COUNTERS: \n"+
                                          "        {counters}").format(
                                              total=total,
                                              url=request.build_absolute_uri(request.get_full_path()),
                                              user=request.user if hasattr(request,"user") else None,
                                              get=request.GET.lists(),
                                              post=request.POST.lists(),
                                              counters="\n        ".join(["%s:%s" % (k,v) for k,v in times])
                                          ))
              tc.raise_value_events()
              return r
            finally:
                THREAD_DISPATCHER.remove_listener(tc)

        return wrapper
    return decorater

from django.conf import settings


output_log = django.utils.log.getLogger(name="counters")
log_reporter= LogReporter(output_log=output_log)
pycounters.register_reporter(log_reporter)




reporting_config = settings.DJANGO_COUNTERS["reporting"]


if reporting_config.get("JSONFile"):
    json_file_reporter = JSONFileReporter(output_file=reporting_config.get("JSONFile"))
    pycounters.register_reporter(json_file_reporter)


if settings.DJANGO_COUNTERS.get("server"):
    pycounters.configure_multi_process_collection(
        collecting_address=settings.DJANGO_COUNTERS["server"],
    )

pycounters.start_auto_reporting(seconds=reporting_config.get("interval" ,300))

if settings.DJANGO_COUNTERS.get("debug",False):
    GLOBAL_DISPATCHER.add_listener(EventLogger(django.utils.log.getLogger(name="counters.events"),property_filter="value"))
