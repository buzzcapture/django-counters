import functools
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpRequest
import django.utils.log

import pycounters
from pycounters.base import THREAD_DISPATCHER, GLOBAL_DISPATCHER, EventLogger
from pycounters.counters import AverageTimeCounter, ThreadTimeCategorizer, FrequencyCounter, AverageWindowCounter
from pycounters.reporters import LogReporter, JSONFileReporter
from django.conf import settings
import django.db.backends.util


if not hasattr(settings, "DJANGO_COUNTERS"):
    raise ImproperlyConfigured("Django settings must contain a DJANGO_COUNTERS entry.")

# wrap django db access layer.
from pycounters.utils import patcher


@pycounters.report_start_end("db_access")
def patched_execute(self, *args, **kwargs):
    return self.cursor.execute(*args, **kwargs)


@pycounters.report_start_end("db_access")
def patched_executemany(self, *args, **kwargs):
    return self.cursor.executemany(*args, **kwargs)


# we cannot use PyCounters' patching utility as CursorWrapper is a proxy
django.db.backends.util.CursorWrapper.execute = patched_execute
django.db.backends.util.CursorWrapper.executemany = patched_executemany


# wrap django's internals with events
DJANGO_EVENTS_SCHEME = [
    {"class": "django.db.backends.util.CursorDebugWrapper", "method": "execute", "event": "db_access"},
    {"class": "django.db.backends.util.CursorDebugWrapper", "method": "executemany", "event": "db_access"},
    {"class": "django.template.Template", "method": "render", "event": "templating"},
]

patcher.execute_patching_scheme(DJANGO_EVENTS_SCHEME)

output_log = django.utils.log.getLogger(name="counters")
log_reporter = LogReporter(output_log=output_log)
pycounters.register_reporter(log_reporter)

reporting_config = settings.DJANGO_COUNTERS["reporting"]

if reporting_config.get("JSONFile"):
    json_file_reporter = JSONFileReporter(output_file=reporting_config.get("JSONFile"))
    pycounters.register_reporter(json_file_reporter)

if settings.DJANGO_COUNTERS.get("server"):
    pycounters.configure_multi_process_collection(
        collecting_address=settings.DJANGO_COUNTERS["server"],
    )

pycounters.start_auto_reporting(seconds=reporting_config.get("interval", 300))

if settings.DJANGO_COUNTERS.get("debug", False):
    GLOBAL_DISPATCHER.add_listener(EventLogger(django.utils.log.getLogger(name="counters.events"),
                                               property_filter="value"))
