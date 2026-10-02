# Lido automaticamente pelo gunicorn quando está na mesma pasta do app.py
# (comando de start continua: gunicorn app:app).
#
# Por que isto existe: com 1 worker síncrono (padrão), UMA conversão lenta ou
# travada bloqueia o site inteiro - todas as outras ferramentas ficam "carregando".
# Com vários workers/threads, uma requisição problemática não derruba as demais.
import os

workers = int(os.environ.get("WEB_CONCURRENCY", "2"))
threads = int(os.environ.get("GUNICORN_THREADS", "4"))
worker_class = "gthread"
# Menor que o limite de 120 s do front-end: o servidor responde com erro antes
# de o navegador desistir, e o worker preso é reiniciado automaticamente.
timeout = int(os.environ.get("GUNICORN_TIMEOUT", "100"))
graceful_timeout = 30
keepalive = 5
bind = "0.0.0.0:" + os.environ.get("PORT", "8000")
