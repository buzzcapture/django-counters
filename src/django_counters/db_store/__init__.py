from django.conf import settings
import pycounters

__author__ = 'boaz'

from reporters import ViewReporter

reporting_config = settings.DJANGO_COUNTERS["reporting"]

if reporting_config.get("database") and reporting_config.get("database").get("active",True):
    db_config = reporting_config.get("database")
    db_reporter = ViewReporter(max_report_age_in_days=db_config.get("max_report_age_in_days",365))
    pycounters.register_reporter(db_reporter)

