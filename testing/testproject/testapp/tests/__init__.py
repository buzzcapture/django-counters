from contextlib import contextmanager
import functools
from django.core.files.temp import NamedTemporaryFile
from django.template import loader
from django.test import TestCase
import pycounters
from pycounters.base import BaseListener, THREAD_DISPATCHER
import testproject.testapp.views
from testproject.testapp.models import TestModel
from pycounters.reporters import JSONFileReporter
import django_counters.base  # initializes for tests.
from django_counters.munin_plugin import DjangoCountersMuninPlugin


@contextmanager
def disable_all_views_but(*args):
    """
    :param args: a list of view names that shouldn't be disabled.
    :return: a dictionary of original settings that can be restored with restore_views
    """
    original_state = {}
    views = testproject.testapp.views
    for v in dir(views):
        if v in args:
            continue
        if not isinstance(getattr(views, v), functools.partial):
            continue

        original_state[v] = getattr(views,v)
        setattr(views,v, original_state[v].func)
    yield

    for v in original_state:
        setattr(views, v, original_state[v])

def reset_pycounters():
    pycounters.base.GLOBAL_REGISTRY.registry.clear()
    pycounters.reporters.base.GLOBAL_REPORTING_CONTROLLER.clear()
    reload(testproject.testapp.views)

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

    def setUp(self):
        reset_pycounters()


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
            res = self.client.get("/sleep/", data=dict(sleep=0.2))
            self.assertIsNotNone(res["__django_counters_total_time__"])

        self.assertIn("v_sleep.sleep", [event for event, param, value in events])
        self.assertIn("v_sleep.templating", [event for event, param, value in events])
        self.assertIn("v_sleep.rest", [event for event, param, value in events])

    def test_db_access_view(self):
        events = []
        with EventCatcher(events):
            res = self.client.get("/db_access/")
            self.assertIsNotNone(res["__django_counters_total_time__"])

        self.assertIn("v_db_access.db_access", [event for event, param, value in events])
        self.assertIn("v_db_access.templating", [event for event, param, value in events])


class MuninPluginTests(TestCase):

    def setUp(self):
        reset_pycounters()

    def test_auto_config(self):
        with disable_all_views_but("sleep"), NamedTemporaryFile() as json_file:
            reporter = JSONFileReporter(output_file=json_file.name)
            pycounters.register_reporter(reporter)
            try:
                self.client.get("/sleep/", data=dict(sleep=0.2))
                pycounters.output_report()

                munin_plugin = DjangoCountersMuninPlugin(json_output_file=json_file.name)

                config = munin_plugin.auto_generate_config_from_json(include_views=["sleep"])

                expected = [{
                                'id': u'django_counters_v_sleep._rps',
                                'global': {'category': None,
                                           'vlabel': 'time',
                                           'title': u'Average times for view sleep'
                                },
                                'data': [{'draw': 'LINE1', 'counter': u'v_sleep._total', 'label': 'Total'},
                                         {'draw': 'AREASTACK', 'counter': u'v_sleep.rest', 'label': u'rest'},
                                         {'draw': 'AREASTACK', 'counter': u'v_sleep.sleep', 'label': u'sleep'},
                                         {'draw': 'AREASTACK', 'counter': u'v_sleep.templating', 'label': u'templating'}
                                ]
                            },
                            {
                                'id': u'django_counters_v_sleep._rps',
                                'global': {'category': None, 'vlabel': 'rps',
                                           'title': u'Requests per second for view sleep'},
                                'data': [
                                    {'draw': 'LINE1', 'counter': u'v_sleep._rps',
                                     'label': 'Requests per sec'
                                    }
                                ],
                            }
                ]
                self.assertListEqual(config, expected)



            finally:
                pycounters.unregister_reporter(reporter)
