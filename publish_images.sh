#!/usr/bin/env bash
set -e

REGISTRY=${REGISTRY:-registry.gitlab.com/tochka-masters/ohooho}

VERSION=${VERSION:-$(python app/version.py)}

echo "VERSION=${VERSION}"

echo "[BUILD]"

VERSION=${VERSION} docker-compose -f docker-compose.publish.yml build --pull

docker image tag ${REGISTRY}/web:dev ${REGISTRY}/web:latest
docker image tag ${REGISTRY}/web:dev ${REGISTRY}/web:${VERSION}

docker image tag ${REGISTRY}/worker:dev ${REGISTRY}/worker:latest
docker image tag ${REGISTRY}/worker:dev ${REGISTRY}/worker:${VERSION}

_STEPS="4"

echo "[PUSH 1/${_STEPS}]"
docker push ${REGISTRY}/web:latest

echo "[PUSH 2/${_STEPS}]"
docker push ${REGISTRY}/web:${VERSION}

echo "[PUSH 3/${_STEPS}]"
docker push ${REGISTRY}/worker:latest

echo "[PUSH 4/${_STEPS}]"
docker push ${REGISTRY}/worker:${VERSION}

echo "[PUBLISH IMAGES DONE]"
