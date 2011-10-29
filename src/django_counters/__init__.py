import django.utils.log
import re
from time import sleep
from django_counters.reporters import ViewReporter

import pycounters
from pycounters.base import THREAD_DISPATCHER, GLOBAL_DISPATCHER, EventLogger
from pycounters.counters import AverageTimeCounter, ThreadTimeCategorizer, FrequencyCounter, AverageWindowCounter
from pycounters.reporters import LogReporter, JSONFileReporter
from pycounters.reporters.base import JSONFileOutputMixin
import sys
from django.conf import settings
import django.db.backends.util

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


def count_view(name,counters=[]):

    name = "v_" + name # prefix view counters with v_

    view_counters=[]
    if counters:
        view_counters.extend(counters)
    else:
        dvc =  settings.COUNTERS.get("default_view_counters")
        if dvc: view_counters.extend(dvc)

    if view_counters:
        view_counters.append("rest")
        for counter in view_counters:
            c = AverageWindowCounter(name + "." + counter)
            pycounters.register_counter(c,throw_if_exists=False)


    c = AverageTimeCounter(name+".total")
    pycounters.register_counter(c,throw_if_exists=False)


    # TODO: use functools.wraps
    def decorater(func):
        func = pycounters.report_start_end("rest")(func)
        @pycounters.report_start_end(name+".total")
        def wrapper(*args,**kwargs):
            tc=ThreadTimeCategorizer(name,view_counters)
            THREAD_DISPATCHER.add_listener(tc)
            try:
              r=func(*args,**kwargs)
              tc.raise_value_events()
              return r
            finally:
                THREAD_DISPATCHER.remove_listener(tc)

        return wrapper
    return decorater

from django.conf import settings


db_reporter = ViewReporter(max_report_age_in_days=settings.COUNTERS.get("max_report_age_in_days",365))
pycounters.register_reporter(db_reporter)

output_log = django.utils.log.getLogger(name="counters")

log_reporter= LogReporter(output_log=output_log)
pycounters.register_reporter(log_reporter)

if settings.COUNTERS.get("JSONFile"):
    json_file_reporter = JSONFileReporter(output_file=settings.COUNTERS.get("JSONFile"))


if settings.COUNTERS.get("server"):
    pycounters.configure_multi_process_collection(
        collecting_address=settings.COUNTERS["server"],
    )

pycounters.start_auto_reporting(seconds=settings.COUNTERS.get("reporting_interval" ,300))

if settings.COUNTERS.get("debug",False):
    GLOBAL_DISPATCHER.add_listener(EventLogger(django.utils.log.getLogger(name="counters.events"),property_filter="value"))
