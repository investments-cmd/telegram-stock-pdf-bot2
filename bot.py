# bot.py - final working version using python-telegram-bot v21.0
import os
import re
import tempfile
import requests
from bs4 import BeautifulSoup
from zipfile import ZipFile
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

BOT_TOKEN = "8728187007:AAESOl1NK4GY0m8tPzk5Jw9IvQkHE7cMtZ4"

def fetch_pdf(url, filepath):
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code == 200 and 'application/pdf' in r.headers.get('Content-Type', ''):
            with open(filepath, 'wb') as f:
                f.write(r.content)
            return True
    except Exception as e:
        print(f"Download error: {url} -> {e}")
    return False

def scrape_documents(symbol: str, work_dir: str):
    symbol = symbol.upper().strip()
    folder = os.path.join(work_dir, symbol)
    os.makedirs(folder, exist_ok=True)
    screener_url = f"https://www.screener.in/company/{symbol}/consolidated/"

    try:
        res = requests.get(screener_url, headers={"User-Agent": "Mozilla/5.0"})
        if res.status_code != 200:
            return None, f"Screener page error: {res.status_code}"

        soup = BeautifulSoup(res.text, 'html.parser')
        links = []

        ann = soup.find(lambda tag: tag.name == "h3" and "Annual reports" in tag.text)
        if ann:
            li = ann.find_next('ul').find('li')
            if li and li.a:
                url = li.a['href']
                year = re.search(r'(\d{4})', li.text)
                name = f"{symbol}_AnnualReport_{year.group(1) if year else 'latest'}.pdf"
                links.append((url, os.path.join(folder, name)))

        con = soup.find(lambda tag: tag.name == "h3" and "Concalls" in tag.text)
        if con:
            li = con.find_next('ul').find('li')
            if li:
                date = re.search(r'([A-Za-z]+ \d{4})', li.text)
                stamp = date.group(1).replace(' ', '') if date else 'latest'
                a1 = li.find('a', string=re.compile("Transcript", re.I))
                a2 = li.find('a', string=re.compile("PPT", re.I))
                if a1:
                    links.append((a1['href'], os.path.join(folder, f"{symbol}_Transcript_{stamp}.pdf")))
                if a2:
                    links.append((a2['href'], os.path.join(folder, f"{symbol}_Presentation_{stamp}.pdf")))

        if not links:
            return None, "No document links found."

        for url, path in links:
            fetch_pdf(url, path)

        zip_path = os.path.join(work_dir, f"{symbol}.zip")
        with ZipFile(zip_path, 'w') as zipf:
            for _, path in links:
                if os.path.exists(path):
                    zipf.write(path, os.path.relpath(path, work_dir))

        return zip_path, None

    except Exception as e:
        return None, str(e)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Send me a stock ticker (e.g., RELIANCE, TCS) to get the latest reports.")

async def handle_ticker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ticker = update.message.text.strip().upper()
    await update.message.reply_text(f"Fetching reports for {ticker}...")

    with tempfile.TemporaryDirectory() as tmpdir:
        zip_path, err = scrape_documents(ticker, tmpdir)
        if zip_path:
            await update.message.reply_document(document=open(zip_path, 'rb'), filename=os.path.basename(zip_path))
        else:
            await update.message.reply_text(f"Error: {err}")

def main():
    if not BOT_TOKEN:
        print("BOT_TOKEN not set. Set it in Railway environment.")
        return
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_ticker))
    print("Bot running...")
    app.run_polling()

if __name__ == '__main__':
    main()
