from django.core.files.temp import NamedTemporaryFile
from django.template import loader
from django.test import TestCase
import pycounters
from pycounters.base import BaseListener, THREAD_DISPATCHER
from testproject.testapp.models import TestModel
from pycounters.reporters import JSONFileReporter
import django_counters.base  # initializes for tests.
from django_counters.munin_plugin import DjangoCountersMuninPlugin


class EventCatcher(object):
    def __init__(self, event_store):
        self.event_store = event_store

    def create_listener(self, event_store):
        class listener(BaseListener):
            def report_event(self, name, property, param):
                event_store.append((name, property, param))

        return listener()


    def __enter__(self):
        self.event_trace = self.create_listener(self.event_store)
        THREAD_DISPATCHER.add_listener(self.event_trace)

    def __exit__(self, exc_type, exc_value, traceback):
        THREAD_DISPATCHER.remove_listener(self.event_trace)


class DjangoCountersTests(TestCase):
    def test_db_hook(self):
        events = []
        with EventCatcher(events):
            TestModel.objects.get_or_create(pk="1")

        self.assertEqual(set(events),
                         set([
                             ("db_access", "start", None),
                             ("db_access", "end", None),
                         ])
                         )

    def test_template_hook(self):
        events = []
        with EventCatcher(events):
            loader.render_to_string("sleep.template.html")

        self.assertEqual(set(events),
                         set([
                             ("templating", "start", None),
                             ("templating", "end", None),
                         ])
                         )

    def test_sleep_view(self):
        events = []
        with EventCatcher(events):
            res = self.client.get("/sleep/",data=dict(sleep=0.2))
            self.assertIsNotNone(res["__django_counters_total_time__"])

        self.assertIn("v_sleep.sleep", [event for event, param, value in events])
        self.assertIn("v_sleep.templating", [event for event, param, value in events])
        self.assertIn("v_sleep.rest", [event for event, param, value in events])


class MuninPluginTests(TestCase):

    def test_auto_config(self):
        with NamedTemporaryFile() as json_file:
            reporter = JSONFileReporter(output_file=json_file.name)
            pycounters.register_reporter(reporter)
            try:
                self.client.get("/sleep/",data=dict(sleep=0.2))
                pycounters.output_report()

                munin_plugin = DjangoCountersMuninPlugin(json_output_file=json_file.name)

                config = munin_plugin.auto_generate_config_from_json()



            finally:
                pycounters.unregister_reporter(reporter)
