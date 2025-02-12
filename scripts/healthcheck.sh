# расположен в: police-bot-prod/scripts/healthcheck.sh

#!/bin/bash

response=$(curl --write-out '%{http_code}' --silent --output /dev/null http://localhost:8000/health)

if [ "$response" -eq 200 ]; then
  echo "Healthcheck OK"
  exit 0
else
  echo "Healthcheck FAILED"
  exit 1
fi