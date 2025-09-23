import asyncio
import aiohttp
import json
import os
import re
from datetime import datetime
from telegram import Bot
from bs4 import BeautifulSoup

# ===== CONFIG =====
TELEGRAM_TOKEN = "8257182835:AAEWU_lY0ft0V6tpLRqi2fDI9H9G2dkq0H4"
CHAT_ID = "-1003066403880"

BINANCE_FUTURES_URL = "https://www.binance.com/en/support/announcement/c-48"
SEEN_ANNOUNCEMENTS_FILE = "seen_futures.json"

# Keywords for Binance USDT-M Futures (expanded for delistings & airdrops)
BINANCE_FUTURES_KEYWORDS = [
    # Listings
    "launch", "listing", "list", "add", "adds", "adding", "introduce", "introduces",
    # Delistings
    "delist", "delisting", "remove", "removal", "suspend", "suspension",
    # Airdrops & Rewards
    "airdrop", "reward", "distribution", "snapshot", "claim",
    # Futures Context
    "futures", "perpetual", "perp", "USDT-M", "USDⓈ-M", "trading", "contracts",
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

# ===== EXTRACT COIN SYMBOL FROM TITLE =====
def extract_coin_symbol(title):
    """Extract coin symbol from title like 'PEPEUSDT' or '$PEPEUSDT' → 'PEPE'"""
    # Match $PEPEUSDT or PEPEUSDT
    match = re.search(r'(?:\$)?([A-Z]+)USDT\b', title)
    if match:
        return match.group(1)  # Returns "PEPE", "SOL", etc.
    return None

# ===== BINANCE FUTURES SCRAPER =====
async def scrape_binance_futures():
    seen = load_seen()
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36'
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
                    # Must contain "USDT" and "futures" or "perpetual"
                    if "usdt" in title_lower and ("futures" in title_lower or "perpetual" in title_lower):
                        # Check if it matches any of our keywords
                        if any(kw.lower() in title_lower for kw in BINANCE_FUTURES_KEYWORDS):

                            # Extract coin symbol
                            coin_symbol = extract_coin_symbol(title)

                            # Build clean URL (FIXED: no extra spaces)
                            full_url = f"https://www.binance.com{href}" if href.startswith('/') else href

                            # Build message
                            msg = f"🚨 *BINANCE FUTURES ALERT*\n\n📌 {title}"
                            if coin_symbol:
                                msg += f"\n🔖 Coin: `{coin_symbol}`"
                            msg += f"\n🔗 [Read Announcement]({full_url})\n🕒 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

                            # SEND ALERT — even if CoinGecko fails (we removed it!)
                            if await send_telegram(msg):
                                seen.add(article_id)
                                save_seen(seen)
                                print(f"📬 Sent Binance alert: {title[:50]}...")

    except Exception as e:
        print(f"❌ Binance scraping error: {e}")

# ===== MAIN LOOP =====
async def main():
    print("🚀 Starting Binance Futures Alert Bot (Listings, Delistings, Airdrops)")
    print("📡 Monitoring only: Binance Futures Announcements")

    while True:
        print(f"\n🔍 Checking at {datetime.now().strftime('%H:%M:%S')}...")
        await scrape_binance_futures()
        print("💤 Sleeping for 5 minutes...")
        await asyncio.sleep(300)  # 5 minutes

# ===== RUN BOT =====
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user.")
    except Exception as e:
        print(f"💥 Critical error: {e}")
