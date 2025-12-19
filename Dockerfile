FROM python:3.11-slim

# Install dependencies for Chrome and nodriver
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Install Google Chrome Stable
RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/

# Nodriver often requires --no-sandbox in Docker
# We will pass these flags in the code, but the environment is ready.
# Run the application
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8080"]

# Ensure xvfb is available if we were running headless with virtual display (optional but good for specific res)
# For now nodriver handles headless args, but if we need xvfb for pixel perfect matching:
# ENV DISPLAY=:99
# CMD Xvfb :99 -screen 0 1280x720x24 & uvicorn src.main:app --host 0.0.0.0 --port 8080
