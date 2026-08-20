# 카페비서 백엔드 통합 초안 인수인계

## 현재 데이터 흐름

```text
Business/CODEF Mock
  -> Transactions 정규화·중복·카테고리·사업/개인 지출
  -> Tax 공제 검토·예상 부가세·월 마감
  -> Analytics 매출/지출/증감 집계
  -> Reports CSV/PDF 생성·승인·전송
  -> Chat Tax/Analytics 결과 설명
  -> Payroll 직원·급여·원천세·명세서
```

Benchmark와 실제 OpenAI 호출은 이번 초안 범위에서 제외한다. Chat은 현재 실제 DB 계산값을 설명하는 규칙 기반 responder를 사용하며, `CHAT_RESPONDER_CLASS`만 교체할 수 있게 분리되어 있다.

## 로컬 데모 실행

```bash
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo_data --reset
python manage.py runserver
```

`seed_demo_data`는 2026-08 CODEF Mock을 사용해 데모 사업장, 거래 29건, 카드매출 월 집계, 직원·급여, 공제 확정, 월 마감, 보고서 파일까지 생성한다. 명령 출력의 `business_id`를 API 요청에 사용한다.

## 주요 API

### Business

- `GET/PATCH /api/businesses/{business_id}/`
- `POST /api/businesses/{business_id}/codef-auth/`
- `GET /api/businesses/{business_id}/codef-auth/status/`
- `POST /api/businesses/{business_id}/tax-type/sync/`

### Transactions

- `POST /api/transactions/sync/`
- `GET /api/transactions/?business_id=1`
- `GET /api/transactions/{transaction_id}/?business_id=1`
- `PATCH /api/transactions/{transaction_id}/category/?business_id=1`
- `PATCH /api/transactions/{transaction_id}/purpose/?business_id=1`
- `GET/PATCH /api/transactions/duplicates/...`

### Tax

- `GET /api/tax/deductions/?business_id=1&year_month=2026-08`
- `PATCH /api/tax/deductions/{transaction_id}/` (`business_id`, `confirmed_status`)
- `GET /api/tax/vat-forecast/?business_id=1&year=2026&month=8`
- `GET /api/tax/deduction-breakdown/?business_id=1&year=2026&month=8`
- `GET /api/tax/closing/2026-08/?business_id=1`
- `POST /api/tax/closing/2026-08/approve/` (`business_id`)

의제매입은 `면세 원재료 후보` 중 사업용·공제확정 거래를 대상으로 한다. 2026년 음식점업 사업장은 개인사업자·과세표준 2억원 이하를 가정해 `9/109` 추정액을 계산하지만, 현재 Business 모델에 개인/법인 구분과 과세기간 과세표준 누계가 없어 법정 공제한도는 적용하지 않는다. 응답의 `deemed_purchase_calculation_status`, `calculation_assumptions`, `warnings`를 함께 표시해야 하며 확정 신고세액으로 표현하면 안 된다.

신용카드 월 매출 집계는 공급가액과 세액이 분리되어 있지 않으므로 일반과세 카페의 전액 과세 매출을 가정해 `총액 × 10/110`으로 매출세액을 추정한다. `card_sales_summary.is_estimate`, `calculation_method`, `warnings`를 함께 표시해야 하며 면세·영세율 매출이 섞인 경우 실제 신고세액과 달라질 수 있다.

### Analytics

- `GET /api/businesses/{business_id}/analytics/cost-ratio/?year=2026&month=8`
- `GET /api/businesses/{business_id}/analytics/trend/?category=RAW_MATERIAL&end_year=2026&end_month=8`
- `GET /api/businesses/{business_id}/analytics/summary/?year=2026&month=8`
- `GET /api/businesses/{business_id}/analytics/monthly-summary/?year=2026&month=8`
- `GET /api/businesses/{business_id}/analytics/export/?year=2026&month=8&format=csv`

기존 Analytics 월 마감 URL은 호환용으로 남아 있지만, 월 마감 단일 원본은 Tax의 `MonthlyClose`다.

### Reports

- `POST /api/businesses/{business_id}/reports/2026-08/generate/`
- `GET /api/businesses/{business_id}/reports/2026-08/`
- `GET /api/businesses/{business_id}/reports/2026-08/download/?type=csv|pdf`
- `POST /api/businesses/{business_id}/reports/2026-08/approve/`
- `POST /api/businesses/{business_id}/reports/2026-08/send-email/`

Tax 월 마감 승인 전에는 생성과 Analytics 내보내기가 `409 MONTHLY_CLOSE_REQUIRED`로 차단된다.

### Chat

- `POST /api/chat/messages/` (`business_id`, `message`, 선택 `year_month`)
- `GET /api/chat/messages/?business_id=1`

POST 응답에는 FE 편의를 위한 `data.answer`와 전체 `assistant_message`가 함께 들어간다.

### Payroll

- `/api/businesses/{business_id}/payroll/employees/`
- `/api/businesses/{business_id}/payroll/payments/`
- `/api/businesses/{business_id}/payroll/payments/export/`
- `/api/businesses/{business_id}/payroll/summary/?year=2026&month=8`

## 프론트엔드에서 수정해야 하는 계약

백엔드에서 FE 코드는 수정하지 않았다. FE의 `VITE_API_BASE_URL`은 `http://localhost:8000/api`로 두고, 아래를 반영해야 한다.

1. 거래 화면의 `category`는 현재 사업/개인 구분 용도로 잘못 사용되고 있다. 사업/개인은 `expense_purpose.code` (`BUSINESS`, `PERSONAL`, `UNCLASSIFIED`)이며 수정 URL은 `/purpose/`다. `category.code`는 `RAW_MATERIAL`, `UTILITIES`, `SUPPLIES` 같은 비용 항목이다.
2. Transactions 상세·수정·중복 API와 Tax·Chat API 요청에 `business_id`를 전달해야 한다.
3. 부가세 공제 구조 분석 호출은 Analytics가 아니라 `/tax/deduction-breakdown/`으로 변경해야 한다.
4. Tax 월 마감 조회·승인에도 `business_id`가 필요하다.
5. Reports는 숫자 report ID가 아니라 `business_id + year_month`로 조회·생성·다운로드한다. 다운로드 쿼리는 `format`이 아니라 `type`이다.
6. Payroll 고용형태 enum은 `FULL_TIME`, `PART_TIME`, `FREELANCER`다. FE Mock의 `REGULAR`는 `FULL_TIME`으로 바꿔야 한다.
7. Payroll 요약 호출에는 `year`, `month`가 필요하다.
8. Analytics `expense_breakdown`에서 화면 표시명은 `label`, 필터·식별값은 `category`다.
9. 거래의 `is_deemed`는 후보 표시용이다. Tax 응답의 `deemed_purchase_deduction`도 명시된 가정에 따른 추정값이므로 실제 의제매입 공제 확정값으로 표현하면 안 된다.

로컬 Vite 기본 주소 `http://localhost:5173`은 백엔드 CORS 허용 목록에 포함되어 있다.
