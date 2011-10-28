import django.utils.log
import re
from time import sleep

from . import patcher
import pycounters
from pycounters.base import THREAD_DISPATCHER, GLOBAL_DISPATCHER, EventLogger
from pycounters.counters import AverageTimeCounter, ThreadTimeCategorizer, FrequencyCounter, AverageWindowCounter
from pycounters.reporters import LogReporter, MultiProcessLogReporter
from pycounters.reporters.base import JSONFileOutputMixin
import sys
from django.conf import settings
import django.db.backends.util

# wrap django db access layer.

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



class JSONFileMultiProcessLogReporter(JSONFileOutputMixin,MultiProcessLogReporter):

    pass


class JSONFileLogReporter(JSONFileOutputMixin,LogReporter):

    pass


def count_view(name,counters=[]):

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


    c = AverageTimeCounter(name)
    pycounters.register_counter(c,throw_if_exists=False)


    # TODO: use functools.wraps
    def decorater(func):
        func = pycounters.report_start_end("rest")(func)
        @pycounters.report_start_end(name)
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

reporter=None
output_log = django.utils.log.getLogger(name="counters")

if settings.COUNTERS.get("server"):
    klass = JSONFileMultiProcessLogReporter if settings.COUNTERS.get("JSONFile") else MultiProcessLogReporter
    output_log.info("Multiprocess mode: klass: %s",klass)
    reporter=klass(
        collecting_address=settings.COUNTERS["server"],
        output_log=output_log,debug_log=django.utils.log.getLogger(name="pc_multiproc"),
        output_file=settings.COUNTERS.get("JSONFile")
    )
else:
    klass = JSONFileLogReporter if settings.COUNTERS.get("JSONFile") else LogReporter
    reporter=klass(output_log=django.utils.log.getLogger(name="counters"),
                             output_file=settings.COUNTERS.get("JSONFile"))

reporter.start_auto_report(seconds=settings.COUNTERS.get("reporting_interval" ,300))

if settings.COUNTERS.get("debug",False):
    GLOBAL_DISPATCHER.add_listener(EventLogger(django.utils.log.getLogger(name="counters.events"),property_filter="value"))
