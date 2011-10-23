import logging
import re
from time import sleep
import pycounters
from pycounters.base import THREAD_DISPATCHER, GLOBAL_DISPATCHER, EventLogger
from pycounters.counters import AverageTimeCounter, ThreadTimeCategorizer, FrequencyCounter, AverageWindowCounter
from pycounters.reporters import LogReporter, MultiProcessLogReporter
from pycounters.reporters.base import JSONFileOutputMixin
import sys
from django.conf import settings


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
output_log = logging.getLogger(name="counters")

if settings.COUNTERS.get("server"):
    klass = JSONFileMultiProcessLogReporter if settings.COUNTERS.get("JSONFile") else MultiProcessLogReporter
    output_log.info("Multiprocess mode: klass: %s",klass)
    reporter=klass(
        collecting_address=settings.COUNTERS["server"],
        output_log=output_log,debug_log=logging.getLogger(name="pc_multiproc"),
        output_file=settings.COUNTERS.get("JSONFile")
    )
else:
    klass = JSONFileLogReporter if settings.COUNTERS.get("JSONFile") else LogReporter
    reporter=klass(output_log=logging.getLogger(name="counters"),
                             output_file=settings.COUNTERS.get("JSONFile"))

reporter.start_auto_report(seconds=settings.COUNTERS.get("reporting_interval" ,300))

if settings.COUNTERS.get("debug",False):
    GLOBAL_DISPATCHER.add_listener(EventLogger(logging.getLogger(name="counters.events"),property_filter="value"))
