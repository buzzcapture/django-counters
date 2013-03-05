import functools
import django.utils.log
from django.conf import settings
import pycounters
from pycounters.base import THREAD_DISPATCHER
from pycounters.counters import ThreadTimeCategorizer, FrequencyCounter, AverageTimeCounter, AverageWindowCounter
from . import base  # init django_counters


def count_view(name=None, categories=[], slow_request_threshold=settings.DJANGO_COUNTERS["slow_request_threshold"]):
    def decorater(func):
        view_name = name if name else func.__name__
        event_name = "v_" + view_name  # prefix all counters with v_

        view_categories = []
        if categories:
            view_categories.extend(categories)
        else:
            dvc = settings.DJANGO_COUNTERS.get("default_view_categories")
            if dvc:
                view_categories.extend(dvc)

        if view_categories:
            view_categories.append("rest")
            for counter in view_categories:
                c = AverageWindowCounter(event_name + "." + counter)
                pycounters.register_counter(c, throw_if_exists=False)

        c = AverageTimeCounter(event_name + "._total", events=[event_name])
        pycounters.register_counter(c, throw_if_exists=False)

        c = FrequencyCounter(event_name + "._rps", events=[event_name])
        pycounters.register_counter(c, throw_if_exists=False)

        slow_logger = django.utils.log.getLogger(name="slow_requests")

        func = pycounters.report_start_end("rest")(func)

        @pycounters.report_start_end(event_name)
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            tc = ThreadTimeCategorizer(event_name, view_categories)
            THREAD_DISPATCHER.add_listener(tc)
            try:
                r = func(*args, **kwargs)
                times = tc.get_times()
                total = sum([v for k, v in times])
                if slow_request_threshold and total > slow_request_threshold:
                        # Get the request from args, this can be either index 0 or 1
                        # depening on whether django view functions or classes are used
                        request = None
                        for arg in args:
                            if isinstance(arg, HttpRequest):
                                request = arg
                                break

                        assert request is not None, \
                            "Request object not found in args for view: %s" % view_name

                        slow_logger.warning(("Slow request (TIME: {total}): {url} \n" +
                                             "    USER: {user} \n" +
                                             "    GET: {get!r} \n" +
                                             "    POST: {post!r} \n" +
                                             "    COUNTERS: \n" +
                                             "        {counters}").format(
                            total=total,
                            url=request.build_absolute_uri(request.get_full_path()),
                            user=request.user if hasattr(request, "user") else None,
                            get=request.GET.lists(),
                            post=request.POST.lists(),
                            counters="\n        ".join(["%s:%s" % (k, v) for k, v in times])
                        ))
                tc.raise_value_events()
                r["__django_counters_total_time__"] = str(total)
                return r
            finally:
                THREAD_DISPATCHER.remove_listener(tc)

        return wrapper

    return decorater