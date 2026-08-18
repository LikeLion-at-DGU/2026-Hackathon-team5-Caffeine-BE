# Gunicorn configuration file for production
import multiprocessing

bind = "127.0.0.1:8000"
workers = multiprocessing.cpu_count() * 2 + 1
threads = 2
worker_class = "gthread"
worker_connections = 1000
timeout = 60
keepalive = 5

# Logging
accesslog = "/var/log/gunicorn/caffeine_access.log"
errorlog = "/var/log/gunicorn/caffeine_error.log"
loglevel = "info"
capture_output = True
