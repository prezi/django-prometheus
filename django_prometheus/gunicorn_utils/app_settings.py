import os


def return_worker_id_from_env():
    return os.environ.get("APP_WORKER_ID", None)


# in order to 'teach' the prometheus python client to not use PIDs for DBfiles
# in multiprocess mode,
# we need to override the pidFunc in prometheus_client.core
# to determine if we run in multiprocess mode (and gunicorn)
# we check for the multiproc dir to be set
# this should be called in the django_app's settings.py
# and should get the prometheus_client.core as input
def override_pidfunc_for_prometheus_client_core(core):
    if os.environ.get('prometheus_multiproc_dir', None):
        core._ValueClass = core._MultiProcessValue(
            _pidFunc=return_worker_id_from_env)
