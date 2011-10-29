import datetime
import json
from pycounters.reporters import BaseReporter
from django_counters.models import ViewCounterValue

class ViewReporter(BaseReporter):
    """
       scans counter values for view counters and saves them to the db in a proper format.
       Also purges the db periodically.
    """

    def __init__(self,max_report_age_in_days=365):
        self.max_report_age_in_day=365

    def output_values(self,counter_values):
        storage_date = datetime.datetime.now()
        for counter,value in counter_values.iteritems():
            if counter.startswith("v_"): # a view counter
                json_value = json.dumps(value)
                vcv = ViewCounterValue()
                vcv.value =json_value
                view,sub_counter = counter.split(".",1)
                vcv.counter = sub_counter # remove view name
                vcv.view =view[2:] # remove prefix
                vcv.date_stored = storage_date
                vcv.save()

        # prune old entries
        prunning_date = storage_date - datetime.timedelta(self.max_report_age_in_day)
        ViewCounterValue.objects.filter(date_stored__lt = prunning_date).delete()
