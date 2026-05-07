# Seoul Under-Dash Backend

## Stage 1 Scope
현재 백엔드는 서울시 강우량 API 연동 및 자치구별 강우량 조회 기능만 제공합니다.

- 예측 API(` /predict `)는 현재 단계에서 제공하지 않습니다.
- 위험도 예측 API는 5단계에서 구현 예정입니다.

## Available APIs
- `GET /` : 서버 상태 확인
- `GET /rainfall/raw` : 서울시 강우량 API 원본 데이터 반환
- `GET /rainfall/gu` : 자치구별 평균/최대 10분 강우량 반환
- `GET /rainfall/gu/{gu_name}/summary` : 특정 자치구 강우량 요약 반환

## Notes
- `.env` 구조는 유지합니다.
- 서울시 API 키는 코드에 직접 작성하지 않고 환경 변수(`SEOUL_API_KEY`)를 사용합니다.
