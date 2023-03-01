#!/usr/bin/env bash
set -eo pipefail

exec gunicorn --config=gunicorn_config.py app.wsgi $@