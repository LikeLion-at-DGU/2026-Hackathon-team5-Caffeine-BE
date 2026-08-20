# Gunicorn configuration file for production
import multiprocessing

bind = "127.0.0.1:8000"
workers = multiprocessing.cpu_count() * 2 + 1
threads = 2
worker_class = "gthread"
worker_connections = 1000
# OpenAI 응답형 채팅/AI 진단 엔드포인트는 20~40초 이상 걸릴 수 있다.
# nginx proxy_read_timeout(deploy/nginx/caffeine-backend.conf)과 반드시 timeout <= proxy_read_timeout 순서를 지켜야
# gunicorn 워커가 먼저 죽어 502가 나는 상황을 막을 수 있다.
timeout = 180
graceful_timeout = 30
keepalive = 5

# Logging
accesslog = "/var/log/gunicorn/caffeine_access.log"
errorlog = "/var/log/gunicorn/caffeine_error.log"
loglevel = "info"
capture_output = True
