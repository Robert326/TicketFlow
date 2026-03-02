#!/bin/bash

# Find the API Gateway container ID
GATEWAY=$(docker ps -qf "name=ticketflow_gateway" | head -n1)

# Check if container was found
if [ -z "$GATEWAY" ]; then
    echo "error"
    exit 1
fi

# Copy the latest load_test.py to the container
docker cp load_test.py $GATEWAY:/app/load_test.py

echo "--- Starting Log Stream from Workers (Background) ---"
# Stream logs in background to see which worker picks up the task
docker service logs -f ticketflow_worker --raw --tail 0 &
LOG_PID=$!

echo "--- Running Load Test ---"
docker exec $GATEWAY python /app/load_test.py

# Cleanup connection to logs
kill $LOG_PID