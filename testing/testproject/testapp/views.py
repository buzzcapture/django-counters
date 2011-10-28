# Create your views here.
import time
from django.http import HttpResponse
from django.template import loader
from django.template.context import RequestContext
import django_counters
import pycounters


@django_counters.count_view("count_me",["sleep"])
def count_me(request):
    sleep = float(request.GET.get("sleep",0))

    pycounters.report_start("sleep")
    time.sleep(sleep)
    pycounters.report_end("sleep")

    snooze = float(request.GET.get("snooze",0.1))
    time.sleep(snooze)
    tc = dict(sleep=sleep,snooze=snooze)

    return HttpResponse(loader.render_to_response("count_me.template.html",tc,
                            context_instance = RequestContext(request)))



