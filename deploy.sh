#!/bin/bash

IMAGE_NAME="sewer-api"
CONTAINER_NAME="sewer-api"
PORT="8000"

echo "========================================"
echo " Seoul Sewer FastAPI Auto Deploy"
echo "========================================"

echo ""
echo "[1] Git pull"
git pull
if [ $? -ne 0 ]; then
  echo "[ERROR] git pull 실패"
  exit 1
fi

echo ""
echo "[2] Stop old container"
docker stop "$CONTAINER_NAME" 2>/dev/null || true
docker rm "$CONTAINER_NAME" 2>/dev/null || true

echo ""
echo "[3] Build Docker image"
docker build -t "$IMAGE_NAME" .
if [ $? -ne 0 ]; then
  echo "[ERROR] Docker build 실패"
  exit 1
fi

echo ""
echo "[4] Run Docker container"
docker run -d \
  --name "$CONTAINER_NAME" \
  -p "$PORT:$PORT" \
  --restart unless-stopped \
  "$IMAGE_NAME"

if [ $? -ne 0 ]; then
  echo "[ERROR] Docker 실행 실패"
  exit 1
fi

echo ""
echo "[5] Container status"
docker ps --filter "name=$CONTAINER_NAME"

echo ""
echo "[6] Recent logs"
docker logs --tail 30 "$CONTAINER_NAME"

echo ""
echo "========================================"
echo " Deploy Complete"
echo "========================================"
echo "Swagger: http://서버IP:$PORT/docs"
