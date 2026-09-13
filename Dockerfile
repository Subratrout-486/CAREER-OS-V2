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
    CAREER_OS_ARACHNE_ROOT=/data/.career_os/arachne \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR /app

# System libraries required by Playwright/Chromium at runtime. Kept with the
# base image so production live-execution (CAREER_OS_ENABLE_BROWSER=1) and
# resume PDF rendering (Playwright Chromium) both work out of the box.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libnss3 \
        libnspr4 \
        libatk1.0-0 \
        libatk-bridge2.0-0 \
        libcups2 \
        libdrm2 \
        libxkbcommon0 \
        libxcomposite1 \
        libxdamage1 \
        libxfixes3 \
        libxrandr2 \
        libgbm1 \
        libpango-1.0-0 \
        libcairo2 \
        libasound2 \
        libatspi2.0-0 \
        libx11-6 \
        libxcb1 \
        libxext6 \
        fonts-liberation \
        fonts-noto-color-emoji \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install the application and its runtime dependencies (standard, non-browser
# extras). Playwright Python is installed so the automatic browser provisioning
# below and the runtime downloader can both work; live browser execution is an
# explicit opt-in via CAREER_OS_ENABLE_BROWSER=1 (documented in README).
COPY pyproject.toml README.md ./
COPY src ./src
COPY dashboard ./dashboard
COPY candidate ./candidate
RUN pip install --upgrade pip && pip install -e . "playwright>=1.52" "scrapling>=0.4.15,<0.5"

# Provision the Playwright browser runtime (Chromium + headless shell) at build
# time so the container does not depend on a developer machine's Chromium.
RUN python -m playwright install chromium --with-deps 2>/dev/null || python -m playwright install chromium

# Non-root runtime user for the web service.
RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /ms-playwright \
    && mkdir -p /data && chown -R appuser:appuser /data

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=3).status==200 else 1)"

VOLUME ["/data"]

CMD ["uvicorn", "career_os.http_app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
