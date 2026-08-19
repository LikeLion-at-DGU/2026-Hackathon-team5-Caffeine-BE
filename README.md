# ☕ 카페비서 (Caffeine Backend)

> **소상공인 카페 사장님을 위한 AI 세무·경영 컨설팅 & 스마트 장부 자동화 솔루션**  
> 2026 동국대학교 멋쟁이사자처럼 해커톤 Team 5 (Caffeine)

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=flat&logo=python&logoColor=white)](https://python.org)
[![Django](https://img.shields.io/badge/Django-5.2-092E20?style=flat&logo=django&logoColor=white)](https://djangoproject.com)
[![DRF](https://img.shields.io/badge/DRF-3.15-red?style=flat)](https://www.django-rest-framework.org/)
[![OpenAI](https://img.shields.io/badge/OpenAI-GPT--5.6--Luna-412991?style=flat&logo=openai&logoColor=white)](https://openai.com)
[![Tests](https://img.shields.io/badge/Unit%20Tests-284%20Passed-brightgreen?style=flat)]()
[![Deploy](https://img.shields.io/badge/Deploy-Gabia%20Ubuntu%20%7C%20HTTPS-blue?style=flat)](https://backendkingjinho.shop)

---

## 📌 서비스 소개

동네 소형 카페 사장님들은 매일 에스프레소를 내리고 손님을 맞이하느라 **복잡한 세무 정리(부가세, 의제매입세액, 인건비)**와 **경영 원가 관리(식자재율, 임대료, 상권 분석)**에 시간을 쏟기 어렵습니다.

**카페비서**는:
1. **카카오 간편인증 1회**로 홈택스/카드사 매출·매입 데이터를 실시간 자동 수집하고,
2. 카페 특화 **우유·원두 의제매입세액 공제 자동화**로 부가세 폭탄을 방어하며,
3. **서울시 상권분석 OpenAPI**와 결합해 내 매장의 건강도(86점 등)와 **3대 맞춤 경영 처방**을 제공하고,
4. **24시간 AI 세무 챗봇**과 **세무사 원클릭 신고 리포트 전송**까지 지원하는 올인원 AI 비서입니다.

---

## 🏛️ 시스템 아키텍처

```mermaid
flowchart TD
    subgraph Client["Frontend (Flutter / Web)"]
        UI["사장님 모바일 / 웹 대시보드"]
    end

    subgraph Server["Caffeine Backend (Django & DRF)"]
        AUTH["인증 & 사업장 (businesses)"]
        TX["스마트 장부 & 중복탐지 (transactions)"]
        TAX["부가세 & 의제매입공제 (tax)"]
        PAY["알바 인건비 & 급여 (payroll)"]
        BENCH["AI 상권 경영진단 (benchmark)"]
        CHAT["24시간 AI 세무챗봇 (chat)"]
        REP["세무사 리포트 & 메일링 (reports)"]
    end

    subgraph External["외부 연동 API (Third-Party)"]
        CODEF["CODEF API<br/>(홈택스/카드사 실시간 스크래핑)"]
        SEOUL["서울시 상권분석 OpenAPI<br/>(외식업·커피음료 골목상권 통계)"]
        OPENAI["OpenAI API<br/>(GPT-5.6-Luna / Structured Output)"]
    end

    UI <-->|RESTful JSON API / HTTPS| Server
    TX <-->|실거래 데이터 동기화| CODEF
    BENCH <-->|상권 평균 매출/비용 수집| SEOUL
    BENCH & CHAT <-->|AI 진단 & 세무 상담| OPENAI
```

---

## ✨ 핵심 기능

### 1. 📱 금융 & 국세청 데이터 자동 연동 (`businesses`, `transactions`)
- **카카오 2-Way 간편인증**을 통한 국세청 홈택스 및 사업용 카드사 연동
- 현금영수증 매출, 전자세금계산서 매입/매출, 사업용 신용카드 매입, 카드사 월별 매출 집계 자동 동기화
- **AI 기반 중복 거래 의심 자동 탐지 & 병합**

### 2. 💰 카페 특화 부가세 예측 & 의제매입세액 공제 (`tax`)
- **우유/생과일 등 면세 식자재 자동 식별** 및 의제매입세액 공제액 자동 산출
- 사장님이 놓친 면세 계산서 누락 알림 및 매입세액 공제/불공제 검토 워크플로우
- 실시간 예상 부가세 납부세액 계산

### 3. 🏆 AI 상권 벤치마크 & 맞춤 경영 진단 (`benchmark`)
- **서울시 상권분석 OpenAPI(커피-음료 `CS100010`)** 실시간 통계 결합
- 내 매장 원가율(식자재 36.5%, 인건비 23.3%, 임대료 10.0%, 소모품 6.2%) vs 골목상권 평균 비교
- OpenAI 구조화 진단 엔진: **종합 건강도 점수(86점 도넛), 사장님 3대 원포인트 처방, 3대 요약** 제공

### 4. 👥 알바생 인건비 & 급여 관리 (`payroll`)
- 시급제/주휴수당 자동 계산 및 주민등록번호 AES-256 암호화 저장
- 급여명세서 조회 및 급여대장 엑셀 다운로드

### 5. 💬 24시간 AI 세무 챗봇 & 세무사 신고 전송 (`chat`, `reports`)
- 내 매장 장부 기반 맞춤형 실시간 세무 질의응답 (GPT-5.6-Luna)
- 세무 신고용 월별 장부 PDF/Excel 자동 생성 및 **담당 세무사 이메일 원클릭 발송**

---

## 🌐 라이브 배포 환경

- **Production Server**: `https://backendkingjinho.shop`
- **인프라 구성**: Gabia Ubuntu 22.04 LTS + Nginx + Gunicorn (Systemd Service) + Let's Encrypt SSL (HTTPS)

### 주요 API 엔드포인트

| 도메인 | Method | URI | 설명 |
| :--- | :--- | :--- | :--- |
| **Benchmark** | `GET` | `/api/businesses/{id}/benchmark/?year=2026&month=8` | AI 벤치마크 종합 대시보드 |
| **Benchmark** | `GET` | `/api/businesses/{id}/benchmark/categories/?year=2026&month=8` | 카테고리별 비용 비교 바차트 |
| **Benchmark** | `POST`| `/api/businesses/{id}/benchmark/ai-diagnosis/` | OpenAI 경영 진단 새로고침 |
| **Analytics** | `GET` | `/api/businesses/{id}/analytics/monthly-summary/?year=2026&month=8` | 월별 매출/지출/손익 요약 |
| **Tax** | `GET` | `/api/tax/deduction-breakdown/?business_id={id}&year=2026&month=8` | 부가세 공제 구조 & 의제매입세액 |
| **Transactions** | `GET` | `/api/transactions/?business_id={id}` | 거래 내역 조회 및 필터링 |
| **Chat** | `POST`| `/api/chat/messages/` | AI 세무 비서 실시간 상담 |
| **Reports** | `POST`| `/api/businesses/{id}/reports/{year_month}/send-email/` | 세무사 이메일 신고자료 전송 |

---

## 🛠️ 로컬 개발 환경 실행

```bash
# 1. 레포지토리 클론
git clone https://github.com/LikeLion-at-DGU/2026-Hackathon-team5-Caffeine-BE.git
cd 2026-Hackathon-team5-Caffeine-BE

# 2. 가상환경 생성 및 활성화
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. 의존성 패키지 설치
pip install -r requirements.txt

# 4. 환경 변수 설정
cp .env.example .env
# .env 파일 내 OPENAI_API_KEY, SEOUL_DATA_API_KEY, CODEF 키 입력

# 5. 데이터베이스 마이그레이션 & 시드 데이터 적재
python manage.py migrate
python manage.py seed_demo_data
python manage.py seed_benchmark_data --fetch-live

# 6. 로컬 개발 서버 실행
python manage.py runserver
```

---

## 🧪 테스트 실행

```bash
# 전체 284개 단위 테스트 및 시스템 점검 실행
python manage.py test
python manage.py check
```

---

## 👥 Caffeine Backend Team

- **LikeLion at Dongguk Univ. (2026 Hackathon Team 5)**
- Copyright © 2026 Caffeine. All rights reserved.
