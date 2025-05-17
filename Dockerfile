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

# Install yacron
RUN apt-get update && apt-get install -y --no-install-recommends yacron && rm -rf /var/lib/apt/lists/*

# Copy yacron configuration
COPY yacron.conf /etc/yacron.conf

# Start script
RUN echo '#!/bin/sh\nyacron &\npython web_service.py >> /var/log/web_service.log 2>&1\ntail -f /var/log/web_service.log' > /start.sh && \
    chmod +x /start.sh

ENV PATH=/root/.local/bin:$PATH

CMD ["/start.sh"]
