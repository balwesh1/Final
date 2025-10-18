import os
import ccxt
import pandas as pd
import numpy as np
import requests
import time
from ta.trend import EMAIndicator
from ta.momentum import RSIIndicator
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from dotenv import load_dotenv
import alpaca_trade_api as tradeapi
import threading

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

# ------------------------ Indicators & Strategy ------------------------
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

# ------------------------ Market Data ------------------------
def get_symbol_data(symbol, interval='1min'):
    try:
        url = f'https://www.alphavantage.co/query?function=TIME_SERIES_INTRADAY&symbol={symbol}&interval={interval}&apikey={ALPHA_API_KEY}'
        r = requests.get(url)
        data = r.json()
        ts = data.get(f'Time Series ({interval})', {})
        if not ts:
            return None
        df = pd.DataFrame.from_dict(ts, orient='index')
        df = df.rename(columns={'1. open':'open','2. high':'high','3. low':'low','4. close':'close','5. volume':'volume'})
        df = df.astype(float)
        df = df.sort_index()
        return df
    except Exception as e:
        send_telegram_message(f"Erreur récupération données : {e}")
        return None

# ------------------------ Backtest ------------------------
def run_backtest(symbol, interval='1min', candles=100):
    df = get_symbol_data(symbol, interval)
    if df is None:
        return
    df = df.tail(candles)
    df = calculate_indicators(df)
    trades = []
    for i in range(1, len(df)):
        df_slice = df.iloc[:i+1]
        signal = check_entry_signal(df_slice)
        if signal:
            entry = df_slice['close'].iloc[-1]
            atr = df_slice['close'].iloc[-14].std() if len(df_slice)>=14 else 0.5
            tp, sl = calculate_tp_sl(entry, atr, signal)
            outcome = 'WIN' if (signal=='BUY' and df_slice['close'].iloc[-1] >= tp) or (signal=='SELL' and df_slice['close'].iloc[-1] <= tp) else 'LOSS'
            trades.append({'entry': entry, 'signal': signal, 'tp': tp, 'sl': sl, 'outcome': outcome})
    if trades:
        wins = sum(1 for t in trades if t['outcome']=='WIN')
        losses = sum(1 for t in trades if t['outcome']=='LOSS')
        total = len(trades)
        profit = wins - losses
        message = f"""
Backtest : {symbol} | Intervalle {interval}
Total trades : {total}
Gagnants : {wins} ({wins*100/total:.0f}%)
Perdants : {losses} ({losses*100/total:.0f}%)
Profit net : {profit}
"""
        send_telegram_message(message)

# ------------------------ Live Analysis ------------------------
def run_analysis():
    symbols = ["XAUUSD","EURUSD"]  # ajouter d'autres symbols
    intervals = ["1min","5min","15min"]
    for symbol in symbols:
        message = f"<b>Analyse live : {symbol}</b>\n"
        for interval in intervals:
            df = get_symbol_data(symbol, interval)
            if df is None:
                continue
            df = calculate_indicators(df)
            signal = check_entry_signal(df)
            if signal:
                entry_price = df['close'].iloc[-1]
                atr = df['close'].iloc[-14].std() if len(df)>=14 else 0.5
                tp, sl = calculate_tp_sl(entry_price, atr, signal)
                prob = calculate_probability(df)
                message += f"\nIntervalle {interval} :\nSignal : {signal}\nPrix : {entry_price:.2f}\nTP : {tp:.2f} | SL : {sl:.2f}\nProbabilité : {prob}%\n"
        send_telegram_message(message)

# ------------------------ Telegram Commands ------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot de trading démarré ✅\nAnalyses et backtests automatiques activés.")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Status: Trading actif | Analyses et backtests en cours")

app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("status", status))

# ------------------------ Loop Automatique ------------------------
def main_loop():
    while True:
        try:
            # Backtest rapide sur tous les symboles et intervalles
            symbols = ["XAUUSD","EURUSD"]
            intervals = ["1min","5min","15min"]
            for sym in symbols:
                for intrvl in intervals:
                    run_backtest(sym, interval=intrvl)
            # Analyse live
            run_analysis()
        except Exception as e:
            send_telegram_message(f"Erreur boucle : {e}")
        time.sleep(300)  # toutes les 5 minutes

# ------------------------ Main ------------------------
if __name__ == "__main__":
    send_telegram_message("Bot de trading initialisé 🔥")
    thread = threading.Thread(target=main_loop)
    thread.start()
    app.run_polling()
