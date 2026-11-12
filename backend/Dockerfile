FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_HOME=/app/.cache/huggingface \
    AUTH_LOG_DIR=/var/log/jobaggregator

WORKDIR /app

# Dépendances d'abord : cette couche reste en cache tant que les requirements ne changent pas.
COPY requirements.txt requirements-ml.txt ./
RUN pip install -r requirements.txt -r requirements-ml.txt

# Utilisateur sans privilèges : un attaquant qui prendrait la main sur l'API ne serait pas root.
RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p "$AUTH_LOG_DIR" "$HF_HOME" \
    && chown -R appuser:appuser "$AUTH_LOG_DIR" /app

COPY --chown=appuser:appuser . .

USER appuser
EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5 \
    CMD python -c "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4).status == 200 else 1)"

# --proxy-headers : l'API voit la vraie IP du client transmise par Nginx (utile pour fail2ban).
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
