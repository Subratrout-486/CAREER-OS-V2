# ARACHNE · Career OS Control Plane
#
# Single container that serves the ARACHNE dashboard at "/" and the control
# plane under /api. Built from the existing FastAPI app (career_os.http_app).
#
# Build:
#   docker build -t career-os-v2 .
# Run:
#   docker run -p 8000:8000 -v career_os_data:/data career-os-v2
#
# Persistent state (execution store, ARACHNE index, checkpoints) lives under
# /data, which should be a mounted volume so it survives container recreation.

FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/src \
    CAREER_OS_EXECUTION_ROOT=/data/.career_os/executions \
    CAREER_OS_ARACHNE_ROOT=/data/.career_os/arachne

WORKDIR /app

# Install the application and its runtime dependencies (standard, non-browser
# extras). Live browser execution is an explicit opt-in, documented separately.
COPY pyproject.toml README.md ./
COPY src ./src
COPY dashboard ./dashboard
COPY candidate ./candidate
RUN pip install --upgrade pip && pip install -e .

# Non-root runtime user for the web service.
RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /data && chown -R appuser:appuser /data

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=3).status==200 else 1)"

VOLUME ["/data"]

CMD ["uvicorn", "career_os.http_app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
