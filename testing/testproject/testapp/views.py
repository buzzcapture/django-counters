# Create your views here.
import time
from django.http import HttpResponse
from django.template.context import RequestContext
from django.shortcuts import render_to_response
import django_counters.view_counters
import pycounters
from testproject.testapp.models import TestModel


@django_counters.view_counters.count_view("sleep", ["sleep", "templating"])
def sleep(request):
    sleep = float(request.GET.get("sleep", 0))

    pycounters.report_start("sleep")
    time.sleep(sleep)
    pycounters.report_end("sleep")

    snooze = float(request.GET.get("snooze", 0.1))
    time.sleep(snooze)
    tc = dict(sleep=sleep, snooze=snooze)

    return render_to_response("sleep.template.html", tc, context_instance=RequestContext(request))


@django_counters.view_counters.count_view("db_access")
def db_access(request):

    a = TestModel()
    a.char_field = "hello"
    a.save()

    snooze = float(request.GET.get("snooze", 0.1))
    time.sleep(snooze)
    tc = dict(sleep=0, snooze=snooze)

    return render_to_response("sleep.template.html", tc, context_instance=RequestContext(request))

