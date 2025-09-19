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
COINGECKO_API_KEY = "CG-vyYJD8oHKW6yfMedh39CdXrB"  # 👈 YOUR KEY HERE

BINANCE_FUTURES_URL = "https://www.binance.com/en/support/announcement/c-48"
SEEN_ANNOUNCEMENTS_FILE = "seen_futures.json"

# Keywords for Binance USDT-M Futures
BINANCE_FUTURES_KEYWORDS = [
    "launch", "listing", "list", "add", "adds", "adding",
    "open", "opens", "opening", "available", "live", "now live",
    "support", "supports", "introduce", "introduces",
    "futures", "perpetual", "perp", "USDT-M", "USDⓈ-M",
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
    """Extract coin symbol from title like '$PEPEUSDT' → 'pepe'"""
    match = re.search(r'\$([A-Z]+)USDT', title)
    if match:
        return match.group(1).lower()
    # Fallback: try to find any word ending with "USDT"
    match = re.search(r'\b([A-Z]+)USDT\b', title)
    if match:
        return match.group(1).lower()
    return None

# ===== FETCH COIN DATA FROM COINGECKO =====
async def get_coin_data(coin_symbol):
    """Fetch real-time data from CoinGecko using your API key"""
    if not coin_symbol:
        return None

    url = f"https://api.coingecko.com/api/v3/coins/{coin_symbol}"
    headers = {
        "accept": "application/json",
        "x-cg-demo-api-key": COINGECKO_API_KEY
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status != 200:
                    print(f"⚠️ CoinGecko API returned {response.status} for {coin_symbol}")
                    return None
                data = await response.json()
                market_data = data.get('market_data', {})
                return {
                    'price': market_data.get('current_price', {}).get('usd', 0),
                    'change_24h': market_data.get('price_change_percentage_24h', 0),
                    'market_cap': market_data.get('market_cap', {}).get('usd', 0),
                    'market_cap_rank': data.get('market_cap_rank', 'N/A'),
                    'name': data.get('name', coin_symbol.upper())
                }
    except Exception as e:
        print(f"❌ CoinGecko fetch error for {coin_symbol}: {e}")
        return None

# ===== FORMAT COIN DATA FOR TELEGRAM =====
def format_coin_data(coin_data, symbol):
    if not coin_data:
        return f"💰 ${symbol.upper()}: Data not available"

    price = coin_data['price']
    change = coin_data['change_24h']
    market_cap = coin_data['market_cap']
    rank = coin_data['market_cap_rank']

    # Format numbers
    price_str = f"${price:,.8f}" if price < 0.01 else f"${price:,.2f}"
    mc_str = f"${market_cap:,.0f}" if market_cap else "N/A"
    change_str = f"{change:+.1f}%"

    return f"💰 {coin_data['name']} ({symbol.upper()}): {price_str} ({change_str})\n📈 Market Cap: {mc_str} (#{rank})"

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

                        # Extract coin symbol
                        coin_symbol = extract_coin_symbol(title)
                        coin_data = None
                        if coin_symbol:
                            coin_data = await get_coin_data(coin_symbol)

                        full_url = f"https://www.binance.com{href}" if href.startswith('/') else href

                        # Build message
                        msg = f"🚨 *NEW BINANCE USDT-M FUTURES LISTING*\n\n📌 {title}"
                        if coin_data:
                            msg += f"\n{format_coin_data(coin_data, coin_symbol)}"
                        msg += f"\n🔗 [Read Announcement]({full_url})\n🕒 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

                        if await send_telegram(msg):
                            seen.add(article_id)
                            save_seen(seen)
                            print(f"📬 Sent Binance alert: {title[:50]}...")

    except Exception as e:
        print(f"❌ Binance scraping error: {e}")

# ===== MAIN LOOP =====
async def main():
    print("🚀 Starting Binance USDT-M Futures + CoinGecko Alert Bot...")
    print("📡 Using your CoinGecko API key for real-time data")

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
