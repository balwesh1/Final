# Utiliser Python 3.11 slim
FROM python:3.11-slim

# Définir le dossier de travail
WORKDIR /app

# Copier le fichier Python unique et le .env
COPY trading_bot_allinone.py .
COPY .env .

# Installer toutes les dépendances nécessaires
RUN pip install --no-cache-dir \
    ccxt \
    alpaca-trade-api \
    pandas \
    numpy \
    ta \
    python-telegram-bot==20.7 \
    requests \
    python-dotenv

# Exposer le port pour Render
EXPOSE 5000

# Lancer le bot
CMD ["python", "trading_bot_allinone.py"]
