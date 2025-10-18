# Utiliser python 3.11 slim
FROM python:3.11-slim

WORKDIR /app

# Copier le fichier unique et .env
COPY trading_bot_allinone.py .
COPY .env .

# Installer les dépendances
RUN pip install --no-cache-dir \
    ccxt \
    alpaca-trade-api \
    pandas \
    numpy \
    ta \
    backtrader \
    python-telegram-bot==20.7 \
    flask \
    requests \
    python-dotenv

# Lancer le bot
CMD ["python", "trading_bot_allinone.py"]
