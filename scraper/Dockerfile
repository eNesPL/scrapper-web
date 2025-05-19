FROM python:3.9-slim

WORKDIR /app

COPY ./scrapers/ /app/scrapers
COPY ./common/ /app/common
COPY ./main.py /app
COPY ./requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

CMD ["python3", "-m", "main"]
