FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt
COPY . .

ENV PATH=/root/.local/bin:$PATH

CMD ["python3", "web_service.py"]

