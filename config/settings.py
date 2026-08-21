"""카페비서 백엔드의 Django 실행 환경 설정."""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from django.core.exceptions import ImproperlyConfigured
from cryptography.fernet import Fernet

# 모든 파일 경로는 프로젝트 루트를 기준으로 계산한다.
BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")

IS_TEST_RUN = "test" in sys.argv


# 배포 환경에서는 디버그 모드를 기본적으로 비활성화한다.
DEBUG = os.environ.get("DJANGO_DEBUG", "False").strip().lower() in (
    "true",
    "1",
    "yes",
    "y",
)

# 로컬·테스트만 개발용 키를 허용하고, 배포에서는 환경변수를 강제한다.
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY") or (
    "django-insecure-5l()ew9)0in=29ppj$m^uge_+eppw8mtzgkkhb0!g%fkki12ju"
    if DEBUG or IS_TEST_RUN
    else None
)
if not SECRET_KEY:
    raise ImproperlyConfigured(
        "DJANGO_SECRET_KEY 환경변수가 설정되어야 합니다 (DEBUG=False인 배포 환경)."
    )

# HTTPS 리다이렉트와 보안 쿠키는 실제 배포에서만 적용한다.
IS_PRODUCTION = not DEBUG and not IS_TEST_RUN

# 암호화 키는 배포 환경변수를 사용하고 테스트에서만 임시 키를 생성한다.
APP_ENCRYPTION_KEY = (
    os.environ.get("APP_ENCRYPTION_KEY")
    or os.environ.get("PAYROLL_ENCRYPTION_KEY")  # 기존 배포 환경변수와의 호환 유지
    or (Fernet.generate_key().decode() if "test" in sys.argv else None)
)
# 기존 급여 암호화 코드가 같은 키를 참조하도록 별칭을 유지한다.
PAYROLL_ENCRYPTION_KEY = APP_ENCRYPTION_KEY

ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get(
        "DJANGO_ALLOWED_HOSTS",
        "localhost,127.0.0.1,testserver",
    ).split(",")
    if host.strip()
]


# Django 앱 구성

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework.authtoken',
    'drf_spectacular',
    'corsheaders',
    'core',
    'payroll',
    'businesses',
    'analytics',
    'transactions',
    'settings',
    'reports',
    'tax',
    'chat',
    'benchmark',
]

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-5.6-luna").strip()
OPENAI_TIMEOUT_SECONDS = float(os.environ.get("OPENAI_TIMEOUT_SECONDS", "20"))
OPENAI_MAX_OUTPUT_TOKENS = int(os.environ.get("OPENAI_MAX_OUTPUT_TOKENS", "1200"))
OPENAI_REASONING_EFFORT = os.environ.get("OPENAI_REASONING_EFFORT", "none").strip()

# 테스트에서는 유료 호출을 차단하고 규칙 기반 응답으로 대체한다.
_default_chat_responder = (
    "chat.services.openai_responder.OpenAIChatResponder"
    if OPENAI_API_KEY and "test" not in sys.argv
    else "chat.services.responder.RuleBasedChatResponder"
)
CHAT_RESPONDER_CLASS = (
    os.environ.get("CHAT_RESPONDER_CLASS", "").strip()
    or _default_chat_responder
)

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


# 데이터베이스

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# 비밀번호 검증

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# 지역 및 시간대

LANGUAGE_CODE = 'ko-kr'

TIME_ZONE = 'Asia/Seoul'

USE_I18N = True

USE_TZ = True


# 정적 파일

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# 기본 기본키 타입

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# CODEF 제공자는 환경에 따라 목업 또는 실제 연동으로 선택한다.
CODEF_MODE = os.environ.get("CODEF_MODE", "mock").strip().lower()

CODEF_CLIENT_ID = os.environ.get("CODEF_CLIENT_ID", "").strip()
CODEF_CLIENT_SECRET = os.environ.get("CODEF_CLIENT_SECRET", "").strip()
CODEF_API_BASE_URL = os.environ.get("CODEF_API_BASE_URL", "").strip().rstrip("/")
CODEF_TIMEOUT_SECONDS = float(
    os.environ.get("CODEF_TIMEOUT_SECONDS", "20")
)
CODEF_PUBLIC_KEY = os.environ.get("CODEF_PUBLIC_KEY", "").strip()

# 서울시 상권분석 인증키는 저장소에 남지 않도록 환경변수로만 주입한다.
SEOUL_DATA_API_KEY = os.environ.get("SEOUL_DATA_API_KEY", "").strip()
SEOUL_DATA_API_BASE_URL = os.environ.get("SEOUL_DATA_API_BASE_URL", "http://openapi.seoul.go.kr:8088").strip().rstrip("/")
SEOUL_DATA_TIMEOUT_SECONDS = float(os.environ.get("SEOUL_DATA_TIMEOUT_SECONDS", "10"))

PAYMENT_GATEWAY_MODE = "mock"

# 인증·인가 정책
# 데모 모드의 무인증 요청은 `is_demo=True` 사업장으로만 제한한다.
DEMO_MODE = os.environ.get("DEMO_MODE", "True").strip().lower() in (
    "true",
    "1",
    "yes",
    "y",
)
DEMO_USERNAME = os.environ.get("DEMO_USERNAME", "demo").strip()

# 소유자가 없는 테스트 픽스처는 테스트 실행 중에만 허용한다.
ALLOW_UNOWNED_BUSINESS_ACCESS = "test" in sys.argv

TEST_RUNNER = "core.test_runner.LegacyAuthTestRunner"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.TokenAuthentication",
        # 명시된 토큰을 우선 검증한 뒤 데모 게스트 인증을 시도한다.
        "core.authentication.DemoGuestAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "core.exceptions.custom_exception_handler",
    "DEFAULT_THROTTLE_RATES": {
        # 로그인 무차별 대입 방지
        "login": "10/min",
        # 데모 모드에서 유료 LLM 호출이 남용되지 않도록 제한
        "llm": "20/min",
    },
}

SPECTACULAR_SETTINGS = {
    "TITLE": "카페비서 (Caffeine) API",
    "DESCRIPTION": "개인 카페/소상공인 세무·회계·노무·경영진단 AI 어시스턴트 API",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
}

CORS_ALLOW_ALL_ORIGINS = os.environ.get("CORS_ALLOW_ALL_ORIGINS", "False").strip().lower() in (
    "true",
    "1",
    "yes",
    "y",
)
CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get(
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://localhost:8080",
    ).split(",")
    if origin.strip()
]
CORS_URLS_REGEX = r"^/api/.*$"
CSRF_TRUSTED_ORIGINS = CORS_ALLOWED_ORIGINS

MEDIA_ROOT = BASE_DIR / "media"
MEDIA_URL = "/media/"

# 세무사 리포트 이메일
# SMTP 계정이 없으면 로컬 확인이 가능한 콘솔 출력으로 대체한다.
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "").strip()
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "").strip()
EMAIL_BACKEND = (
    "django.core.mail.backends.smtp.EmailBackend"
    if EMAIL_HOST_USER
    else "django.core.mail.backends.console.EmailBackend"
)
EMAIL_HOST = os.environ.get("EMAIL_HOST", "smtp.gmail.com").strip()
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_USE_TLS = True
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER or "no-reply@caffeine.local"

# 배포 보안 헤더
# Nginx의 전달 프로토콜을 신뢰하되, 로컬·테스트에서는 HTTPS 강제를 적용하지 않는다.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = IS_PRODUCTION
SESSION_COOKIE_SECURE = IS_PRODUCTION
CSRF_COOKIE_SECURE = IS_PRODUCTION
SECURE_HSTS_SECONDS = int(os.environ.get("SECURE_HSTS_SECONDS", "0"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = SECURE_HSTS_SECONDS > 0
SECURE_HSTS_PRELOAD = SECURE_HSTS_SECONDS > 0
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[{asctime}] {levelname} {name}: {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": os.environ.get("DJANGO_LOG_LEVEL", "INFO"),
    },
}
