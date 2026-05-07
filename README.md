# Seoul Under-Dash Backend

## Scope
현재 백엔드는 서울시 강우량/하천 수위/하수관로 수위/하수도 시설 capacity 데이터를 기반으로
수위 상승 추세와 배수 한계 도달 가능성을 분석합니다.

## Available APIs
- `GET /` : 서버 상태 확인
- `GET /rainfall/raw` : 서울시 강우량 API 원본 데이터 반환
- `GET /rainfall/gu` : 자치구별 평균/최대 10분 강우량 반환
- `GET /rainfall/gu/{gu_name}/summary` : 특정 자치구 강우량 요약 반환
- `GET /river/raw`, `GET /river/gu`, `GET /river/gu/{gu_name}/summary`
- `GET /sewer-pipe/raw`, `GET /sewer-pipe/gu`, `GET /sewer-pipe/gu/{gu_name}/summary`
- `GET /integrated/gu/{gu_name}`
- `GET /trend/drainpipe/{region}`
- `GET /predict/gu/{gu_name}`

## Notes
- `.env` 구조는 유지합니다.
- 서울시 API 키는 코드에 직접 작성하지 않고 환경 변수(`SEOUL_API_KEY`)를 사용합니다.
