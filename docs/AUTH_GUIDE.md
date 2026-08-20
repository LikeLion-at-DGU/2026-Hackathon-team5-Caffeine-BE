# 인증 가이드 (프론트엔드 연동용)

백엔드는 **DRF TokenAuthentication**을 사용합니다. 이 문서는 프론트엔드가 붙일 때
필요한 것만 담았습니다.

---

## 1. 지금 당장은 아무것도 안 해도 됩니다 (DEMO_MODE)

배포 서버는 `DEMO_MODE=1`로 떠 있습니다. 이 상태에서는 **`Authorization` 헤더가
없는 요청을 데모 계정으로 자동 인증**하므로, 기존 프론트엔드 코드가 그대로 동작합니다.

```
GET /api/businesses/1/analytics/summary/?year=2026&month=8     → 200 (데모 사업장)
```

단, 게스트로 인증된 요청은 **`is_demo=True` 사업장에만** 접근할 수 있습니다.
회원가입으로 만들어진 실제 사용자 사업장은 `403`입니다.

```
GET /api/businesses/{실제_사용자_사업장}/...   → 403 FORBIDDEN_BUSINESS_ACCESS
```

`.env`에서 `DEMO_MODE=0`으로 바꾸면 데모 사업장도 토큰을 요구합니다(`401`).

---

## 2. 로그인 붙이기 (3단계)

### 2-1. 로그인 API

**`POST /api/auth/login/`**

```json
{ "username": "demo", "password": "demo1234" }
```

응답 (`200`):
```json
{
  "success": true,
  "code": "LOGIN_SUCCESS",
  "message": "로그인에 성공했습니다.",
  "data": {
    "token": "9f2c1a...",
    "user_id": 1,
    "username": "demo",
    "primary_business_id": 1,
    "businesses": [
      { "id": 1, "business_name": "수아네 커피집", "representative_name": "조수아",
        "tax_type": "GENERAL", "is_demo": true }
    ]
  }
}
```

> `client.js`의 response 인터셉터가 envelope을 언랩하므로, 프론트에서는
> `res.data.token` / `res.data.primary_business_id`로 바로 접근됩니다.

실패 시 `400`, `code: "INVALID_CREDENTIALS"`.
분당 10회 초과 시 `429`, `code: "THROTTLED"`.

### 2-2. 토큰 저장

```js
// src/api/auth.js (신규)
import client from "./client";

const TOKEN_KEY = "caffeine_token";
const BUSINESS_KEY = "caffeine_business_id";

export async function login(username, password) {
  const { data } = await client.post("/auth/login/", { username, password });
  localStorage.setItem(TOKEN_KEY, data.token);
  localStorage.setItem(BUSINESS_KEY, String(data.primary_business_id));
  return data;
}

export async function logout() {
  try {
    await client.post("/auth/logout/");
  } finally {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(BUSINESS_KEY);
  }
}

export const getToken = () => localStorage.getItem(TOKEN_KEY);
export const getBusinessId = () => localStorage.getItem(BUSINESS_KEY);
export const isLoggedIn = () => Boolean(getToken());
```

### 2-3. `src/api/client.js`에 request 인터셉터 추가

현재 `client.js` 7번 라인의 TODO 자리에 넣으면 됩니다. **형식은 `Token <key>`이고,
`Bearer`가 아닙니다.**

```js
import axios from "axios";

const client = axios.create({
  baseURL: `${import.meta.env.VITE_API_BASE_URL}/api`,
});

// 저장된 토큰이 있으면 실어 보낸다. 없으면 헤더를 붙이지 않는다
// (백엔드가 DEMO_MODE일 때 데모 계정으로 폴백하므로 로그인 전에도 화면이 뜬다).
client.interceptors.request.use((config) => {
  const token = localStorage.getItem("caffeine_token");
  if (token) {
    config.headers.Authorization = `Token ${token}`;   // Bearer 아님
  }
  return config;
});

client.interceptors.response.use(
  (res) => {
    if (res.data && typeof res.data === "object" && "data" in res.data) {
      res.data = res.data.data;
    }
    return res;
  },
  (error) => {
    const status = error.response?.status;
    if (status === 401) {
      // 토큰이 만료·폐기됨. 지우고 로그인으로 보낸다.
      localStorage.removeItem("caffeine_token");
      localStorage.removeItem("caffeine_business_id");
      // window.location.assign("/login");
    }
    return Promise.reject(error);
  }
);

export default client;
```

> ⚠️ `config.headers.Authorization`을 빈 문자열로라도 설정하면 백엔드의 데모 폴백이
> 발동하지 않고 `401`이 됩니다. 토큰이 없을 때는 **키 자체를 넣지 마세요.**

---

## 3. 엔드포인트

| 메서드 | 경로 | 인증 | 설명 |
| :-- | :-- | :-- | :-- |
| POST | `/api/auth/register/` | 불필요 | 회원가입 + 기본 사업장 생성 + 토큰 발급 (`201`) |
| POST | `/api/auth/login/` | 불필요 | 토큰 발급 (`200`) |
| POST | `/api/auth/logout/` | 필요 | 토큰 폐기 (`200`). 이후 같은 토큰은 `401` |
| GET | `/api/auth/me/` | 필요 | 내 계정 + 소유 사업장 목록 |

**회원가입 요청**
```json
{ "username": "chosooa", "password": "Caffeine!2026",
  "business_name": "수아네 커피집", "representative_name": "조수아" }
```
`business_name` / `representative_name`은 생략 가능합니다.
비밀번호는 **8자 이상**이며 Django 기본 검증기를 통과해야 합니다
(숫자만 안 됨, 흔한 비밀번호 안 됨, 아이디와 유사하면 안 됨).
실패 시 `400`, `errors.password`에 사유 배열이 담깁니다.

---

## 4. 에러 코드

| HTTP | `code` | 프론트 처리 |
| :-- | :-- | :-- |
| 401 | `UNAUTHORIZED` | 토큰 없음/무효/폐기됨 → 토큰 삭제 후 로그인 |
| 403 | `FORBIDDEN_BUSINESS_ACCESS` | 내 사업장이 아님 → `primary_business_id` 재확인 |
| 404 | `BUSINESS_NOT_FOUND` | 존재하지 않는 `business_id` |
| 400 | `INVALID_BUSINESS_ID` | `business_id` 누락 또는 형식 오류 |
| 429 | `THROTTLED` | 로그인 10/분, AI 20/분 초과 |

모든 에러 응답 형태:
```json
{ "success": false, "code": "...", "message": "...", "errors": {} }
```

---

## 5. API 문서

- Swagger UI: `/api/schema/swagger-ui/`
- ReDoc: `/api/schema/redoc/`
- OpenAPI JSON: `/api/schema/`

Swagger에서 인증이 필요한 엔드포인트를 테스트할 때는 우측 상단 **Authorize**에
`Token <key>` 전체를 넣습니다.

---

## 6. 데모 계정

`python manage.py seed_demo_data --reset` 로 생성됩니다.

```
username: demo
password: demo1234
business_id: 1  (수아네 커피집, is_demo=True)
```
