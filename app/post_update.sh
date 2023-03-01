#!/bin/bash

_STEPS="6"

echo "Start post update scenario"
echo "- makemigrations 1/${_STEPS} -"
python manage.py makemigrations
echo "- migrate 2/${_STEPS} -"
python manage.py migrate
echo "- collectstatic 3/${_STEPS} -"
python manage.py collectstatic --noinput | tail -1
echo "- clearsessions 4/${_STEPS} -"
python manage.py clearsessions
echo "- init app script 5/${_STEPS} -"
python manage.py init_app
echo "- gen docs 6/${_STEPS} -"
cd /app/docs && make html
