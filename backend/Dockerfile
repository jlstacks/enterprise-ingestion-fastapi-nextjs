FROM python:3.12-slim AS base
WORKDIR /srv
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/srv
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip==26.2
RUN pip install --no-cache-dir -r requirements.txt
RUN addgroup --system app && adduser --system --ingroup app app
COPY alembic.ini ./
COPY migrations ./migrations
COPY app ./app
COPY tests/integration_check.py tests/live_recovery_check.py ./tests/
COPY entrypoint.sh ./entrypoint.sh
RUN chmod +x ./entrypoint.sh && chown -R app:app /srv

FROM base AS test
USER root
COPY requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt
COPY tests ./tests
COPY security_audit.py ./security_audit.py
CMD ["pytest", "-q", "tests"]

FROM base AS runtime
USER app
EXPOSE 8000
CMD ["./entrypoint.sh"]
