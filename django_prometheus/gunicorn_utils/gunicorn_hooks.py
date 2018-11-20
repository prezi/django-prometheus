import os


# these hooks are implementing reusable gunicorn worker ID (like uwsgi has)
# for gunicorn the worker ID will be in the APP_WORKER_ID environment variable
# the default behavior is to use the PID of the workers, but that made
# DBfiles piling up if the workers were restarting and getting new PIDs

# This is very much based on (copied from) the public gist of hynek
# https://gist.github.com/hynek/ba655c8756924a5febc5285c712a7946

# naming convention: prometheus_<gunicorn hook name>
# you can either call these from your existing gunicorn hooks, or import them
# as <gunicorn hook name> if you do not use these hooks currently.
def prometheus_on_starting(server):
    """
    Attach a set of IDs that can be temporarily re-used.

    Used on reloads when each worker exists twice.
    """
    server._worker_id_overload = set()


def prometheus_nworkers_changed(server, new_value, old_value):
    """
    Gets called on startup too.

    Set the current number of workers.  Required if we raise the worker count
    temporarily using TTIN because server.cfg.workers won't be updated and if
    one of those workers dies, we wouldn't know the ids go that far.
    """
    server._worker_id_current_workers = new_value


def _prometheus_next_worker_id(server):
    """
    If there are IDs open for re-use, take one.  Else look for a free one.
    """
    if server._worker_id_overload:
        return server._worker_id_overload.pop()

    in_use = set(w._worker_id for w in server.WORKERS.values() if w.alive)
    free = set(range(1, server._worker_id_current_workers + 1)) - in_use

    return free.pop()


def prometheus_on_reload(server):
    """
    Add a full set of ids into overload so it can be re-used once.
    """
    server._worker_id_overload = set(range(1, server.cfg.workers + 1))


def prometheus_pre_fork(server, worker):
    """
    Attach the next free worker_id before forking off.
    """
    worker._worker_id = _prometheus_next_worker_id(server)


def prometheus_post_fork(server, worker):
    """
    Put the worker_id into an env variable for further use within the app.
    """
    os.environ["APP_WORKER_ID"] = str(worker._worker_id)
