FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app \
    BU_CDP_URL=http://127.0.0.1:9222 \
    BH_HOME=/home/worker/.browser-harness

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl gnupg fonts-liberation git \
    && curl -fsSL https://dl.google.com/linux/linux_signing_key.pub \
      | gpg --dearmor -o /usr/share/keyrings/google-chrome.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] https://dl.google.com/linux/chrome/deb/ stable main" \
      > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --uid 10001 worker
WORKDIR /app

COPY browser_worker/requirements.txt /tmp/browser-worker-requirements.txt
RUN python -m pip install --no-cache-dir -r /tmp/browser-worker-requirements.txt

COPY . /app/dev_control
RUN chmod +x /app/dev_control/browser_worker/start.sh \
    && chown -R worker:worker /app /home/worker

USER worker
EXPOSE 8080
ENTRYPOINT ["/app/dev_control/browser_worker/start.sh"]
