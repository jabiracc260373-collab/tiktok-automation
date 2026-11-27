FROM python:3.11-slim

WORKDIR /app

# Install system dependencies that Chromium needs
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
    libasound2 \
    libpango-1.0-0 \
    libcairo2 \
    libatspi2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# CRITICAL: Set the browser path BEFORE installing
# This ensures the installer and the runtime code look at the same place.
ENV PLAYWRIGHT_BROWSERS_PATH=/app/.playwright

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Now install Chromium into /app/.playwright (because ENV is set above)
RUN playwright install chromium

# Copy application code
COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "10000"]
