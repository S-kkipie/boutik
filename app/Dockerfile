FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1

RUN useradd --uid 10001 --create-home --shell /usr/sbin/nologin boutik \
 && mkdir -p /data /creds && chown boutik:boutik /data

WORKDIR /srv
COPY pyproject.toml ./
COPY boutik ./boutik
RUN pip install --no-compile .

USER boutik
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --start-period=10s \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz',timeout=2).status==200 else 1)"
# --no-access-log: uvicorn would log full paths, and pay links are bearer capabilities.
# Proxy headers are trusted only from FORWARDED_ALLOW_IPS (uvicorn default 127.0.0.1),
# so clients cannot spoof X-Forwarded-For to dodge per-IP rate limits.
CMD ["uvicorn", "boutik.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--no-access-log"]
