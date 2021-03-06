import django
from django_prometheus.testutils import PrometheusTestCaseMixin
from testapp.views import ObjectionException
from django.test import SimpleTestCase
import unittest


def M(metric_name):
    """Make a full metric name from a short metric name.

    This is just intended to help keep the lines shorter in test
    cases.
    """
    return 'django_http_%s' % metric_name


class TestMiddlewareMetrics(PrometheusTestCaseMixin, SimpleTestCase):
    """Test django_prometheus.middleware.

    Note that counters related to exceptions can't be tested as
    Django's test Client only simulates requests and the exception
    handling flow is very different in that simulation.
    """
    def test_request_counters(self):
        r = self.saveRegistry()
        self.client.get('/')
        self.client.get('/')
        self.client.get('/help')
        self.client.post('/', {'test': 'data'})

        # We have 3 requests with no post body, and one with a few
        # bytes, but buckets are cumulative so that is 4 requests with
        # <=128 bytes bodies.
        self.assertMetricDiff(
            r, 3, M('request_size_bytes_bucket'), le='0.0')
        self.assertMetricDiff(
            r, 4, M('request_size_bytes_bucket'), le='128.0')
        self.assertMetricEquals(
            None, M('template_responses_total'),
            template_name='help.html'
        )
        self.assertMetricDiff(
            r, 3, M('template_responses_total'),
            template_name='index.html'
        )

        self.assertMetricDiff(
            r, 2, M('responses_total'),
            code='200', method='get', handler='testapp.views.index')
        self.assertMetricDiff(
            r, 1, M('responses_total'),
            code='200', method='get', handler='testapp.views.help')
        self.assertMetricDiff(
            r, 1, M('responses_total'),
            code='200', method='post', handler='testapp.views.index')

        self.assertMetricDiff(
            r, 0, M('response_size_bytes_bucket'), le='0.0')
        self.assertMetricDiff(
            r, 3, M('response_size_bytes_bucket'), le='128.0')
        self.assertMetricDiff(
            r, 4, M('response_size_bytes_bucket'), le='8192.0')
        self.assertMetricDiff(r, 0, M('streaming_responses_total'))

    def test_latency_histograms(self):
        # Caution: this test is timing-based. This is not ideal. It
        # runs slowly (each request to /slow takes at least .1 seconds
        # to complete) and it may be flaky when run on very slow
        # systems.

        r = self.saveRegistry()

        # This always takes more than .1 second, so checking the lower
        # buckets is fine.
        self.client.get('/slow')

        self.assertMetricDiff(
            r, 0,
            'django_view_duration_seconds_bucket',
            le='0.05', handler='slow')
        self.assertMetricDiff(
            r, 1,
            'django_view_duration_seconds_bucket',
            le='5.0', handler='slow')

        self.assertMetricDiff(
            r, 0,
            'django_http_request_duration_seconds_bucket',
            le='0.05', handler='slow')
        self.assertMetricDiff(
            r, 1,
            'django_http_request_duration_seconds_bucket',
            le='5.0', handler='slow')

    def test_exception_latency_histograms(self):
        r = self.saveRegistry()

        try:
            self.client.get('/objection')
        except ObjectionException:
            pass

        self.assertMetricDiff(  # Still measure latency on exceptions
            r, 1,
            'django_view_duration_seconds_bucket',
            le='0.05', handler='testapp.views.objection')
        self.assertMetricDiff(
            r, 1,
            'django_http_request_duration_seconds_bucket',
            le='0.05', handler='testapp.views.objection')
        self.assertMetricDiff(  # Measure exception count
            r, 1,
            'django_exceptions_total',
            handler="testapp.views.objection", method="get")

    def test_streaming_responses(self):
        r = self.saveRegistry()
        self.client.get('/')
        self.client.get('/file')
        self.assertMetricDiff(r, 1, M('streaming_responses_total'))
        self.assertMetricDiff(
            r, 1,
            M('response_size_bytes_bucket'), le='+Inf')
