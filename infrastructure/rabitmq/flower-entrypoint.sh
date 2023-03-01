#!/bin/bash
echo FLOWER_BROKER=${FLOWER_BROKER}
flower --broker=${FLOWER_BROKER} --port=5555
