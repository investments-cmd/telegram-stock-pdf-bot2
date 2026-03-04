import os
import re
import tempfile
import requests
from bs4 import BeautifulSoup
from zipfile import ZipFile
from telegram import Update
from telegram.ext import Application, MessageHandler, CommandHandler, ContextTypes, filters

# ===== CONFIG =====
BOT_TOKEN = "8728187007:AAESOl1NK4GY0m8tPzk5Jw9IvQkHE7cMtZ4"
ALLOWED_USERS = {1345952228, 1016594583}  # replace with your Telegram user_id(s)

# ===== PDF Downloader =====
def fetch_pdf(url, filepath):
    try:
        res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
        if res.status_code == 200 and 'application/pdf' in res.headers.get('Content-Type', ''):
            with open(filepath, 'wb') as f:
                f.write(res.content)
            return True
    except Exception as e:
        print(f"Error: {url} → {e}")
    return False

def scrape_documents(symbol: str, work_dir: str):
    symbol = symbol.upper().strip()
    folder = os.path.join(work_dir, symbol)
    os.makedirs(folder, exist_ok=True)
    url = f"https://www.screener.in/company/{symbol}/consolidated/"

    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code != 200:
            return None, f"Screener error: {r.status_code}"

        soup = BeautifulSoup(r.text, 'html.parser')
        links = []

        # Annual Report
        ann = soup.find(lambda tag: tag.name == "h3" and "Annual reports" in tag.text)
        if ann:
            li = ann.find_next('ul').find('li')
            if li and li.a:
                href = li.a['href']
                year = re.search(r'(\d{4})', li.text)
                links.append((href, os.path.join(folder, f"{symbol}_AnnualReport_{year.group(1) if year else 'latest'}.pdf")))

        # Concall Transcript and PPT
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
            return None, "No financial PDFs found."

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


# ===== Telegram Handlers =====
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ALLOWED_USERS:
        return
    await update.message.reply_text("📈 Send me an NSE/BSE ticker (e.g., RELIANCE, TCS) to get the latest financial reports.")

async def handle_ticker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ALLOWED_USERS:
        await update.message.reply_text("❌ Unauthorized")
        return

    ticker = update.message.text.strip().upper()
    msg = await update.message.reply_text(f"📡 Fetching reports for {ticker}...")

    with tempfile.TemporaryDirectory() as tmpdir:
        zip_path, error = scrape_documents(ticker, tmpdir)
        if zip_path:
            await msg.edit_text("✅ Reports fetched. Sending ZIP...")
            await update.message.reply_document(document=open(zip_path, 'rb'), filename=os.path.basename(zip_path))
        else:
            await msg.edit_text(f"❌ Error: {error}")


# ===== Main Entrypoint =====
def main():
    if not BOT_TOKEN:
        print("BOT_TOKEN missing.")
        return

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_ticker))
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
