#!/bin/bash

exec celery ${CELERY_WORKER:-worker} -A ${CELERY_APP} -l ${CELERY_LOGLEVEL:-info} --pidfile= $@
