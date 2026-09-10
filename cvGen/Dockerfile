# ──────────────────────────────────────────────
# Stage 1: build / install dependencies
# ──────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Install packages into a dedicated prefix so they can be copied cleanly
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ──────────────────────────────────────────────
# Stage 2: production image
# ──────────────────────────────────────────────
FROM python:3.12-slim AS production

# 1. Set a global environment variable for Playwright
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers

# Create a non-root user
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser

WORKDIR /app

COPY --from=builder /install /usr/local

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libnss3 \
    libdbus-1-3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libasound2 \
    libgbm1 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxrandr2 \
    libxrender1 \
    libxtst6 \
    && rm -rf /var/lib/apt/lists/*

# 2. Create the browser directory and install there
RUN mkdir -p $PLAYWRIGHT_BROWSERS_PATH && \
    python -m playwright install chromium && \
    chmod -R 755 $PLAYWRIGHT_BROWSERS_PATH

# Copy application source
COPY app/ ./app/

# 3. Fix permissions for the tmp folder and the browser folder
RUN mkdir -p /app/app/services/tmp && \
    chown -R appuser:appgroup /app/app/services/tmp && \
    chown -R appuser:appgroup $PLAYWRIGHT_BROWSERS_PATH

USER appuser

EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]

