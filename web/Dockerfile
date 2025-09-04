FROM python:3.9-slim

WORKDIR /app

# Kopiujemy wymagania
COPY requirements.txt .

# Instalujemy pakiety globalnie, bez --user
RUN pip install --no-cache-dir -r requirements.txt

# Kopiujemy kod
COPY . .

# Ustawiamy PATH do ewentualnych skryptów (nie jest konieczne dla pakietów)
ENV PATH=/root/.local/bin:$PATH

# Uruchamiamy skrypt bez -m
CMD ["python3", "web_service.py"]
