#!/bin/bash

# Stop on any error
set -e
docker compose build gateway
docker stack deploy -c docker-compose.yml ticketflow
docker service ls

