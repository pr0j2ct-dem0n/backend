배포 지시서 (Docker 운영 반영)

개요
- 목적: 이미지에 민감정보를 포함하지 않고 서버에서 `.env`를 주입하도록 `deploy.sh`와 `.dockerignore`를 갱신합니다.

변경 사항
- `deploy.sh`: 컨테이너 실행 시 `--env-file .env` 옵션 추가, 배포 전 `.env` 파일 존재 및 필수 키 검증 추가.
- `.dockerignore`: `.env` 및 `.env.*`를 무시하도록 추가.

서버에 필요한 `.env` 필수값 (예)
- SEOUL_API_KEY=...
- SEOUL_API_URL=http://openAPI.seoul.go.kr:8088
- DATA_API_KEY=...
- DATA_API_URL=https://api.odcloud.kr/api
- SEOUL_API_CACHE_TTL_SEC=45
- SEOUL_API_ALL_REGION_MAX_WORKERS=2
- SEOUL_API_TIMEOUT_SEC=6
- SEOUL_API_MAX_ROWS=3000
- INFRA_CACHE_TTL_SEC=86400
- TOTAL_RISK_INFRA_WEIGHT=0.3

중요 주의사항
- `.env` 파일은 서버에 직접 파일로 존재해야 합니다. (`--env-file .env` 사용)
- `.env`가 없으면 공공데이터/서울시 API 호출이 실패합니다.
- `DATA_API_URL`은 반드시 `https://api.odcloud.kr/api` 이어야 합니다.

재배포 절차
1. 서버에서 프로젝트 경로로 이동:

```bash
cd /path/to/backend
```

2. 배포 스크립트 실행:

```bash
./deploy.sh
```

배포 후 검증
- 컨테이너 상태 확인 (정상: Up):

```bash
docker ps --filter "name=sewer-api"
```

- 로그 확인 (최근 100줄):

```bash
docker logs --tail 100 sewer-api
```

- 헬스 체크:

```bash
curl http://127.0.0.1:8000/health
```

정상 응답: HTTP 200

- 기능 확인 예시 (응답에 필수 필드 존재 확인):

```bash
curl http://127.0.0.1:8000/sewer-pipe/gu
```

응답 JSON에 아래 필드들이 포함되어야 합니다:
- water_risk
- infra_score
- total_risk
- facility_count
- facility_capacity
- inflow_amount
- discharge_amount

문제 발생 시 체크리스트
- 서버에 `.env`가 존재하는가?
- `.env` 내 `DATA_API_URL` 값이 `https://api.odcloud.kr/api` 인가?
- `docker logs`에서 오류 메시지를 확인하고, API 키 관련 에러(인증/권한)를 점검하세요.

문의
- 추가 수정이나 자동화(예: 시스템d 서비스, CI/CD)가 필요하면 알려주세요.
