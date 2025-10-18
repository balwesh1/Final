import os
import ccxt
import pandas as pd
import numpy as np
import requests
from ta.trend import EMAIndicator
from ta.momentum import RSIIndicator
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from dotenv import load_dotenv
import alpaca_trade_api as tradeapi

# ------------------------ Load .env ------------------------
load_dotenv()

# OKX
OKX_API_KEY = os.getenv('OKX_API_KEY')
OKX_SECRET = os.getenv('OKX_SECRET')
OKX_PASSPHRASE = os.getenv('OKX_PASSPHRASE')

# Alpaca
ALPACA_API_KEY = os.getenv('ALPACA_API_KEY')
ALPACA_SECRET_KEY = os.getenv('ALPACA_SECRET_KEY')
APCA_API_BASE_URL = os.getenv('APCA_API_BASE_URL')

# Telegram
BOT_TOKEN = os.getenv('BOT_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')

# Alpha Vantage
ALPHA_API_KEY = os.getenv('ALPHA_API_KEY')

# ------------------------ OKX & Alpaca Setup ------------------------
okx = ccxt.okx({'apiKey': OKX_API_KEY,'secret': OKX_SECRET,'password': OKX_PASSPHRASE})
alpaca = tradeapi.REST(ALPACA_API_KEY, ALPACA_SECRET_KEY, APCA_API_BASE_URL, api_version='v2')

# ------------------------ Utils ------------------------
def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID,"text": message,"parse_mode":"HTML"}
    requests.post(url, data=payload)

# ------------------------ Strategy ------------------------
def calculate_indicators(df):
    df['EMA8'] = EMAIndicator(df['close'], window=8).ema_indicator()
    df['EMA21'] = EMAIndicator(df['close'], window=21).ema_indicator()
    df['RSI'] = RSIIndicator(df['close'], window=14).rsi()
    return df

def check_entry_signal(df):
    last = df.iloc[-1]
    if last['EMA8'] > last['EMA21'] and last['RSI'] < 70:
        return 'BUY'
    elif last['EMA8'] < last['EMA21'] and last['RSI'] > 30:
        return 'SELL'
    return None

# ------------------------ TP/SL & Probability ------------------------
def calculate_tp_sl(entry_price, atr, direction, risk_reward=2):
    if direction == 'BUY':
        sl = entry_price - atr
        tp = entry_price + atr * risk_reward
    else:
        sl = entry_price + atr
        tp = entry_price - atr * risk_reward
    return tp, sl

def calculate_probability(df):
    last = df.iloc[-1]
    score = 50
    if last['EMA8'] > last['EMA21']:
        score += 25
    else:
        score -= 25
    if last['RSI'] < 30:
        score += 10
    elif last['RSI'] > 70:
        score -= 10
    return min(max(score,0),100)

# ------------------------ Backtest ------------------------
def backtest(df):
    df = calculate_indicators(df)
    trades = []
    for i in range(1, len(df)):
        df_slice = df.iloc[:i+1]
        signal = check_entry_signal(df_slice)
        if signal:
            entry = df_slice['close'].iloc[-1]
            atr = df_slice['close'].iloc[-14].std() if len(df_slice) >= 14 else 0.5
            tp, sl = calculate_tp_sl(entry, atr, signal)
            prob = calculate_probability(df_slice)
            trades.append({'entry': entry, 'signal': signal, 'tp': tp, 'sl': sl, 'probability': prob})
    return trades

# ------------------------ Live Trading ------------------------
def place_order_okx(symbol, side, amount, price=None):
    order_type = 'limit' if price else 'market'
    order = okx.create_order(symbol, order_type, side, amount, price)
    return order

def place_order_alpaca(symbol, side, qty):
    order = alpaca.submit_order(symbol, qty, side, 'market', 'gtc')
    return order

# ------------------------ Alpha Vantage Data ------------------------
def get_symbol_data(symbol, interval='1min'):
    url = f'https://www.alphavantage.co/query?function=TIME_SERIES_INTRADAY&symbol={symbol}&interval={interval}&apikey={ALPHA_API_KEY}'
    r = requests.get(url)
    data = r.json()
    df = pd.DataFrame.from_dict(data.get(f'Time Series ({interval})', {}), orient='index')
    df = df.rename(columns={'1. open':'open','2. high':'high','3. low':'low','4. close':'close','5. volume':'volume'})
    df = df.astype(float)
    df = df.sort_index()
    return df

# ------------------------ Telegram Commands ------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot de trading démarré ✅")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Status: Trading actif | Open trades: 0 | PnL: 0$")

async def set_tp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tp = context.args[0]
    await update.message.reply_text(f"Take profit défini à {tp}")

async def set_sl(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sl = context.args[0]
    await update.message.reply_text(f"Stop loss défini à {sl}")

def start_telegram_bot():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("set_tp", set_tp))
    app.add_handler(CommandHandler("set_sl", set_sl))
    app.run_polling()

# ------------------------ Main ------------------------
if __name__ == "__main__":
    send_telegram_message("Bot de trading initialisé 🔥")
    start_telegram_bot()
