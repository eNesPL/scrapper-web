# Build stage
FROM python:3.9-slim as builder

WORKDIR /app
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Runtime stage
FROM python:3.9-slim

WORKDIR /app
COPY --from=builder /root/.local /root/.local
COPY . .

# No cron needed

# Start script
RUN echo '#!/bin/sh\nwhile true; do python main.py >> /var/log/scraper.log 2>&1; sleep 3600; done\npython web_service.py &\ntail -f /dev/null' > /start.sh && \
    chmod +x /start.sh

ENV PATH=/root/.local/bin:$PATH

CMD ["/start.sh"]
