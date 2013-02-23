from django.template import loader
from django.test import TestCase
from pycounters.base import BaseListener, THREAD_DISPATCHER
from testproject.testapp.models import TestModel


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
            loader.render_to_string("count_me.template.html")

        self.assertEqual(set(events),
                         set([
                             ("templating", "start", None),
                             ("templating", "end", None),
                         ])
                         )

