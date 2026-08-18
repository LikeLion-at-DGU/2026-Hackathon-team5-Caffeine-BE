# 🚀 카페비서(Caffeine) 가비아 Ubuntu 서버 배포 가이드

이 문서는 멋쟁이사자처럼에서 제공한 **가비아 Ubuntu 22.04/24.04 서버**에 카페비서 백엔드를 배포하는 전체 과정을 한 줄씩 쉽게 따라할 수 있도록 정리한 가이드입니다.

---

## 📋 배포 전체 흐름
1. **내 컴퓨터**: SSH로 가비아 서버 접속
2. **서버**: 기본 패키지(Python, Nginx 등) 설치
3. **서버**: 프로젝트 Git Clone 및 가상환경 생성
4. **서버**: `.env` 파일 작성 (OpenAI 키, 비밀키 등)
5. **서버**: DB 마이그레이션 및 정적 파일(`collectstatic`) 생성
6. **서버**: Gunicorn(systemd) 서비스 등록 및 실행
7. **서버**: Nginx 설정 적용 및 실행
8. **확인**: 웹 브라우저 및 Postman으로 API 호출 테스트

---

## 1단계: 가비아 서버에 SSH 접속하기 (내 컴퓨터 터미널)

내 컴퓨터(PowerShell 또는 터미널)에서 아래 명령어를 실행합니다:

```powershell
# 예시: ssh -i "키파일경로.pem" ubuntu@서버공인IP
ssh -i "C:\path\to\your-key.pem" ubuntu@<가비아_서버_IP>
```
> **팁**: 처음 접속 시 `Are you sure you want to continue connecting (yes/no/[fingerprint])?` 라고 물어보면 `yes`를 입력하고 Enter를 누릅니다.

---

## 2단계: 서버 기본 패키지 설치 (서버 터미널)

서버에 접속되면 아래 명령어를 순서대로 실행합니다:

```bash
# 1. 패키지 목록 업데이트 및 기본 도구 설치
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3-pip python3-venv nginx git curl

# 2. Gunicorn 로그 저장용 폴더 생성
sudo mkdir -p /var/log/gunicorn
sudo chown -R ubuntu:ubuntu /var/log/gunicorn
```

---

## 3단계: 프로젝트 Clone 및 Python 가상환경 구성 (서버 터미널)

```bash
# 1. 홈 디렉터리로 이동
cd /home/ubuntu

# 2. 저장소 Clone (중앙 저장소)
git clone https://github.com/LikeLion-at-DGU/2026-Hackathon-team5-Caffeine-BE.git
cd 2026-Hackathon-team5-Caffeine-BE

# 3. Python 가상환경 생성 및 활성화
python3 -m venv venv
source venv/bin/activate

# 4. 필수 라이브러리 설치
pip install --upgrade pip
pip install -r requirements.txt
```

---

## 4단계: `.env` 환경변수 파일 생성 (서버 터미널)

`.env` 파일을 생성하고 설정을 입력합니다:

```bash
# nano 편집기 실행
nano .env
```

아래 내용을 복사하여 붙여넣고, **`<가비아_서버_IP>`**와 **`OPENAI_API_KEY`** 등을 실제 값으로 채워 넣습니다:

```ini
DJANGO_DEBUG=False
DJANGO_SECRET_KEY=caffeine-hackathon-super-secret-key-2026!@#
DJANGO_ALLOWED_HOSTS=<가비아_서버_IP>,localhost,127.0.0.1
CORS_ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173

# 데이터 암호화 키 (아래 5단계에서 생성한 Fernet 키 입력)
APP_ENCRYPTION_KEY=

# OpenAI API 설정
OPENAI_API_KEY=sk-proj-여기에_실제_OPENAI_API_KEY_입력
OPENAI_MODEL=gpt-5.6-luna
OPENAI_TIMEOUT_SECONDS=20
OPENAI_MAX_OUTPUT_TOKENS=1200
OPENAI_REASONING_EFFORT=none

# CODEF 설정
CODEF_MODE=mock
PAYMENT_GATEWAY_MODE=mock
```

> **저장 방법**: `Ctrl + O` 누르고 `Enter` (저장) → `Ctrl + X` (편집기 종료)

### 🔑 APP_ENCRYPTION_KEY 생성 방법:
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```
출력된 키 문자열을 복사해서 `.env` 파일의 `APP_ENCRYPTION_KEY=` 뒤에 넣어줍니다.

---

## 5단계: DB 마이그레이션 및 정적 파일 수집 (서버 터미널)

```bash
# 1. DB 테이블 생성
python manage.py migrate

# 2. 정적 파일 수집 (Nginx 서빙용)
python manage.py collectstatic --noinput
```

---

## 6단계: Gunicorn 서비스(systemd) 등록 및 실행 (서버 터미널)

```bash
# 1. 서비스 설정 파일 복사
sudo cp deploy/systemd/caffeine-backend.service /etc/systemd/system/

# 2. systemd 데몬 새로고침 및 서비스 활성화 & 시작
sudo systemctl daemon-reload
sudo systemctl enable caffeine-backend
sudo systemctl start caffeine-backend

# 3. 실행 상태 확인
sudo systemctl status caffeine-backend
```
> **정상 결과**: 초록색 글씨로 `Active: active (running)`이 표시됩니다. (`q`를 누르면 상태창에서 빠져나옵니다)

---

## 7단계: Nginx 리버스 프록시 설정 적용 (서버 터미널)

```bash
# 1. Nginx 설정 파일 복사
sudo cp deploy/nginx/caffeine-backend.conf /etc/nginx/sites-available/

# 2. 설정 활성화 심볼릭 링크 생성
sudo ln -sf /etc/nginx/sites-available/caffeine-backend.conf /etc/nginx/sites-enabled/

# 3. 기본 default 사이트 비활성화
sudo rm -f /etc/nginx/sites-enabled/default

# 4. Nginx 설정 문법 검사
sudo nginx -t

# 5. Nginx 재시작
sudo systemctl restart nginx
```
> **정상 결과**: `nginx: configuration file /etc/nginx/nginx.conf test is successful` 메시지가 출력됩니다.

---

## 8단계: 외부 접속 테스트 및 프론트 연동 확인

웹 브라우저나 Postman에서 아래 URL을 호출해 봅니다:

- **기본 API 테스트**: `http://<가비아_서버_IP>/api/businesses/`
- **Chat API 테스트**: `http://<가비아_서버_IP>/api/chat/messages/`
- **Django Admin**: `http://<가비아_서버_IP>/admin/`

---

## 🛠️ 추후 코드 업데이트 시 배포 갱신 방법 (간편 3줄)

서버에서 코드를 최신으로 업데이트할 때는 아래 3줄만 실행하면 됩니다:

```bash
cd /home/ubuntu/2026-Hackathon-team5-Caffeine-BE
git pull origin main
sudo systemctl restart caffeine-backend
```
