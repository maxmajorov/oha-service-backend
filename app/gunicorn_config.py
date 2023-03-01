import os
import sys


def cpu_count():
    if sys.platform.startswith('linux'):
        # noinspection PyUnresolvedReferences
        return len(os.sched_getaffinity(0))  # return real available cpu's

    return os.cpu_count()


bind = '0.0.0.0:8000'

if os.getenv('GUNICORN_MULTIPROCESSING', 'false').lower() in ('true', 't', 'yes'):
    workers = int(os.getenv('OHA_GUNICORN_WORKERS', 1))
else:
    threads = int(os.getenv('OHA_GUNICORN_THREADS', min(2 * cpu_count() + 1, 2)))

# https://github.com/ShanshanHe/pmp/pull/14
timeout = 120

# log all messages to stdout
log_file = '-'
capture_output = True
