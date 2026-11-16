FROM python:3.11-slim-bookworm AS runtime
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 MPLBACKEND=Agg FINTECH_ROOT=/app \
    MLFLOW_ENABLE_SYSTEM_METRICS_LOGGING=false DO_NOT_TRACK=1
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 curl \
    && rm -rf /var/lib/apt/lists/*
COPY constraints.txt requirements-runtime.txt ./
RUN --mount=type=cache,target=/root/.cache/pip pip install --upgrade pip==26.3 \
    && pip install --timeout 120 --retries 5 -c constraints.txt -r requirements-runtime.txt
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-deps .
COPY params.yaml alembic.ini ./
COPY migrations ./migrations
COPY dashboard ./dashboard
COPY .streamlit/config.toml ./.streamlit/config.toml
COPY scripts ./scripts
COPY configs ./configs
RUN useradd --create-home --uid 10001 fintech && mkdir -p artifacts reports/generated storage \
    && chown -R fintech:fintech /app
USER fintech
EXPOSE 8000 8501 5000
CMD ["uvicorn", "fintech_risk.api:app", "--host", "0.0.0.0", "--port", "8000"]

FROM runtime AS training
USER root
RUN apt-get update && apt-get install -y --no-install-recommends openjdk-17-jre-headless \
    && rm -rf /var/lib/apt/lists/*
RUN --mount=type=cache,target=/root/.cache/pip \
    --mount=type=bind,source=.wheelhouse,target=/wheels,readonly \
    pip install --timeout 120 --retries 5 --resume-retries 5 --find-links /wheels -c constraints.txt pyspark==3.5.8
# Wheels cached on Windows may lose POSIX executable bits on Spark launchers.
RUN chmod a+x /usr/local/lib/python3.11/site-packages/pyspark/bin/* \
    /usr/local/lib/python3.11/site-packages/pyspark/sbin/*
USER fintech
ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
CMD ["fintech", "prepare"]
