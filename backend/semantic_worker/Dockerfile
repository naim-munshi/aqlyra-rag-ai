FROM python:3.13-slim AS build
ENV PYTHONDONTWRITEBYTECODE=1 PIP_DISABLE_PIP_VERSION_CHECK=1 HF_HOME=/opt/hf-cache
WORKDIR /build
COPY semantic_worker/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir --target=/opt/packages -r requirements.txt
COPY semantic_worker/model.py ./semantic_worker/model.py
RUN PYTHONPATH=/opt/packages:/build python -c "from semantic_worker.model import download_public_model; download_public_model()"

FROM python:3.13-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 HF_HOME=/opt/hf-cache HF_HUB_OFFLINE=1 \
    HF_HUB_DISABLE_TELEMETRY=1 TOKENIZERS_PARALLELISM=false PYTHONPATH=/opt/packages:/app
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -m -u 10002 appworker
WORKDIR /app
COPY --from=build /opt/packages /opt/packages
COPY --from=build /opt/hf-cache /opt/hf-cache
COPY semantic_worker /app/semantic_worker
RUN chown -R appworker:appworker /opt/hf-cache /app
USER appworker
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "semantic_worker.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
