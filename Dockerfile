# Use Python 3.11, which is fully compatible with greenlet and Playwright
FROM python:3.11-slim

WORKDIR /app

# Install Playwright's system dependencies
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
    && rm -rf /var/lib/apt/lists/*

# Install Python packages (greenlet will install a pre-built wheel, no compilation)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install the Chromium browser binary (system deps are already installed above)
RUN playwright install chromium

# Copy application code
COPY . .

# Keep Playwright browser files inside the project directory for persistence
ENV PLAYWRIGHT_BROWSERS_PATH=./.playwright

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "10000"]
