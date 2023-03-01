#!/bin/bash
whoami

COMPOSE_FILE=${COMPOSE_FILE:-docker-compose.prod.yml}


echo "COMPOSE_FILE: $COMPOSE_FILE"
echo "Current working directory: $PWD"
echo "--------------"

echo "Dump"
echo "! Not implemented !"
echo "--------------"

echo "Free space"
df -hl /home | awk '{ sum+=$5 } END { print sum }'
echo "--------------"

echo "Current status"
docker-compose -f "$COMPOSE_FILE" ps
echo "--------------"

echo "Stop and update if new image pulled"
docker-compose -f "$COMPOSE_FILE" pull
docker-compose -f "$COMPOSE_FILE" up -d
echo "--------------"

# sleep
sleep 2

echo "Update the models and statics"
docker-compose -f "$COMPOSE_FILE" exec -T oha-app-prod-web sh post_update.sh
echo "Restart web"
docker-compose -f "$COMPOSE_FILE" restart oha-app-prod-web

sleep 5
echo "Step result"
docker-compose -f "$COMPOSE_FILE" ps

echo "Scale workers"
docker-compose -f "$COMPOSE_FILE" up --scale oha-app-prod-worker-hi=3 -d
docker-compose -f "$COMPOSE_FILE" up --scale oha-app-prod-worker-lo=3 -d
echo "Step result"
docker-compose -f "$COMPOSE_FILE" ps

echo "Current version"
docker-compose -f "$COMPOSE_FILE" exec oha-app-prod-web python manage.py shell -c "from import settings; print('OhaOha version {}'.format(settings.VERSION)); "

echo "Remove Docker Containers, Images, Volumes, and Networks"
docker system prune --force

docker-compose -f /home/devops/nginx/docker-compose.yml exec nginx nginx -s reload

echo "Script work time: $SECONDS sec."
