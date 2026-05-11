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
# [Preflight] .env 파일 및 필수 키 확인
if [ ! -f .env ]; then
  echo "[ERROR] .env 파일이 없습니다. 서버에 .env 파일을 두고 다시 시도하세요."
  exit 1
fi

REQUIRED_KEYS=(
  SEOUL_API_KEY
  SEOUL_API_URL
  DATA_API_KEY
  DATA_API_URL
  SEOUL_API_CACHE_TTL_SEC
  SEOUL_API_ALL_REGION_MAX_WORKERS
  SEOUL_API_TIMEOUT_SEC
  SEOUL_API_MAX_ROWS
  INFRA_CACHE_TTL_SEC
  TOTAL_RISK_INFRA_WEIGHT
)

missing=0
for key in "${REQUIRED_KEYS[@]}"; do
  if ! grep -qE "^${key}=" .env; then
    echo "[ERROR] .env에 필수 키 누락: ${key}"
    missing=1
  fi
done
if [ "$missing" -ne 0 ]; then
  echo "[ERROR] .env가 불완전합니다. 위 키들을 추가한 후 재시도하세요."
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
  --env-file .env \
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
echo "Swagger: http://182.215.194.170:$PORT/docs"
