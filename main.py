import asyncio
import aiohttp
import json
import os
import re
from datetime import datetime
from telegram import Bot
from bs4 import BeautifulSoup
import feedparser

# ===== CONFIG =====
TELEGRAM_TOKEN = "7838823091:AAEXMGY6kQVLK6h2XZgTU63vxTPkxmkD0zs"  # 👈 Your Bot Token
CHAT_ID = "-1002915874071"  # 👈 Your Chat ID

BINANCE_FUTURES_URL = "https://www.binance.com/en/support/announcement/c-48"
SEEN_ANNOUNCEMENTS_FILE = "seen_realtime_news.json"

# Enhanced keyword list for USDT-M Futures
BINANCE_FUTURES_KEYWORDS = [
    # Core Action Words
    "launch", "listing", "list", "add", "adds", "adding",
    "open", "opens", "opening", "available", "live", "now live",
    "support", "supports", "introduce", "introduces",
    # Product Type
    "futures", "perpetual", "perp", "USDT-M", "USDⓈ-M",
    # Context Words
    "trading", "trading pair", "contracts", "margin", "leverage",
]

# ===== UTILS =====
def load_seen():
    if os.path.exists(SEEN_ANNOUNCEMENTS_FILE):
        try:
            with open(SEEN_ANNOUNCEMENTS_FILE, 'r', encoding='utf-8') as f:
                return set(json.load(f))
        except:
            return set()
    return set()

def save_seen(seen):
    try:
        with open(SEEN_ANNOUNCEMENTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(list(seen), f, indent=2)
    except Exception as e:
        print(f"⚠️ Error saving seen items: {e}")

async def send_telegram(text):
    """Send message to Telegram with retry logic"""
    bot = Bot(token=TELEGRAM_TOKEN)
    for attempt in range(3):
        try:
            await bot.send_message(chat_id=CHAT_ID, text=text, parse_mode="Markdown")
            print("✅ Alert sent to Telegram.")
            return True
        except Exception as e:
            print(f"📡 Telegram send attempt {attempt + 1} failed: {e}")
            await asyncio.sleep(2 ** attempt)
    print("❌ Failed to send Telegram message after 3 attempts.")
    return False

# ===== BINANCE FUTURES SCRAPER =====
async def scrape_binance_futures():
    seen = load_seen()
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(BINANCE_FUTURES_URL, headers=headers) as response:
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')

                links = soup.find_all('a', href=re.compile(r'/en/support/announcement/'))

                for link in links:
                    href = link.get('href', '')
                    title = link.get_text(strip=True)
                    article_id = href.split('/')[-1] if href else ''

                    if not article_id or article_id in seen:
                        continue

                    title_lower = title.lower()
                    if ("usdt" in title_lower and ("futures" in title_lower or "perpetual" in title_lower)) and \
                       any(kw.lower() in title_lower for kw in BINANCE_FUTURES_KEYWORDS):

                        full_url = f"https://www.binance.com{href}" if href.startswith('/') else href
                        msg = (
                            f"🚨 *NEW BINANCE USDT-M FUTURES LISTING*\n\n"
                            f"📌 {title}\n"
                            f"🔗 [Read Announcement]({full_url})\n"
                            f"🕒 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                        )
                        if await send_telegram(msg):
                            seen.add(article_id)
                            save_seen(seen)
                            print(f"📬 Sent Binance alert: {title[:50]}...")

    except Exception as e:
        print(f"❌ Binance scraping error: {e}")

# ===== COINTELEGRAPH RSS FEED =====
async def fetch_cointelegraph_news():
    seen = load_seen()
    feed_url = "https://cointelegraph.com/rss"

    try:
        feed = feedparser.parse(feed_url)
        for entry in feed.entries[:5]:  # Top 5 articles
            title = entry.title
            link = entry.link
            article_id = link.split('/')[-1].split('?')[0]  # Simple unique ID

            if article_id in seen:
                continue

            # Skip if it's old or not relevant
            if any(x in title.lower() for x in ["weekly", "monthly", "explainer", "podcast"]):
                continue

            msg = (
                f"📰 *BREAKING CRYPTO NEWS*\n\n"
                f"📌 {title}\n"
                f"🔗 [Read More]({link})\n"
                f"🕒 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            if await send_telegram(msg):
                seen.add(article_id)
                save_seen(seen)
                print(f"📬 Sent Cointelegraph alert: {title[:50]}...")

    except Exception as e:
        print(f"❌ RSS feed error: {e}")

# ===== MAIN LOOP =====
async def main():
    print("🚀 Starting Real-Time Crypto News Bot...")
    print("📡 Monitoring: Binance Futures + Cointelegraph RSS")

    while True:
        print(f"\n🔍 Checking for new alerts at {datetime.now().strftime('%H:%M:%S')}...")
        await scrape_binance_futures()
        await fetch_cointelegraph_news()
        print("💤 Sleeping for 5 minutes...")
        await asyncio.sleep(300)  # Check every 5 minutes

# ===== RUN BOT =====
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user.")
    except Exception as e:

        print(f"💥 Critical error: {e}")
