import asyncio
import json
import logging
import re
import time
import httpx
from urllib.parse import urlparse, parse_qs

# Bot config
PANEL_URL = "http://169.58.23.67:8080"
BOT_TOKEN = "8970159364:AAH4VH26Y3_WfJwTQZOPjGF_3flA-Pnrk7g"
CHECK_INTERVAL = 300  # 5 minutes

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

# Store user chat_id
USER_CHAT_ID = None

async def send_telegram(token, chat_id, text):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    async with httpx.AsyncClient() as client:
        await client.post(url, json={"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True})

async def get_updates(token, offset=None):
    url = f"https://api.telegram.org/bot{token}/getUpdates"
    params = {"timeout": 30}
    if offset:
        params["offset"] = offset
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, params=params, timeout=35)
        return resp.json().get("result", [])

async def scrape_vinted(query_url):
    """Scrape Vinted from phone IP"""
    parsed = urlparse(query_url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1",
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "pl-PL,pl;q=0.9",
    }
    
    async with httpx.AsyncClient(follow_redirects=True, timeout=15) as client:
        # Get session cookies
        resp = await client.get(base, headers=headers)
        cookies = dict(resp.cookies)
        
        await asyncio.sleep(1)
        
        # Search API
        api_headers = {
            "User-Agent": headers["User-Agent"],
            "Accept": "application/json",
            "Referer": f"{base}/catalog",
        }
        
        params = parse_qs(parsed.query)
        api_params = {k: v[0] if len(v) == 1 else v for k, v in params.items()}
        api_params["per_page"] = "96"
        api_params["order"] = "newest_first"
        
        api_url = f"{base}/api/v2/catalog/items"
        resp = await client.get(api_url, params=api_params, headers=api_headers, cookies=cookies)
        
        if resp.status_code != 200:
            return None, f"Vinted returned {resp.status_code}"
        
        data = resp.json()
        items = data.get("items", [])
        
        results = []
        for item in items:
            price_obj = item.get("price", {})
            price = float(price_obj.get("amount", 0)) if isinstance(price_obj, dict) else 0
            
            user_obj = item.get("user", {})
            seller = user_obj.get("login") if isinstance(user_obj, dict) else None
            
            photo = None
            photos = item.get("photo", {})
            if isinstance(photos, dict):
                photo = photos.get("url") or photos.get("full_size_url")
            
            results.append({
                "vinted_id": str(item.get("id", "")),
                "title": item.get("title", ""),
                "price": price,
                "brand": item.get("brand_title"),
                "size": item.get("size_title"),
                "color": item.get("color"),
                "condition": item.get("status"),
                "category": item.get("catalog_title"),
                "url": f"{base}/items/{item.get('id', '')}",
                "image_url": photo,
                "seller": seller,
                "country": item.get("country"),
                "query": query_url,
            })
        
        return results, None

async def send_to_panel(items):
    """Send scraped items to panel API"""
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{PANEL_URL}/api/bot/import", json=items, timeout=30)
        return resp.json()

async def get_panel_queries():
    """Get active queries from panel"""
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{PANEL_URL}/api/bot/queries", timeout=10)
        data = resp.json()
        return data.get("queries", [])

async def run_scraper_loop():
    """Main scraper loop"""
    global USER_CHAT_ID
    
    while True:
        try:
            if not USER_CHAT_ID:
                await asyncio.sleep(5)
                continue
            
            queries = await get_panel_queries()
            
            if not queries:
                await asyncio.sleep(CHECK_INTERVAL)
                continue
            
            for q in queries:
                try:
                    items, error = await scrape_vinted(q["url"])
                    
                    if error:
                        logger.warning(f"Scrape error for {q['name']}: {error}")
                        continue
                    
                    if not items:
                        # Check if notify_empty is enabled
                        try:
                            async with httpx.AsyncClient() as hc:
                                qr = await hc.get(f"{PANEL_URL}/api/bot/queries", timeout=10)
                                queries_data = qr.json().get("queries", [])
                                for qd in queries_data:
                                    if qd["id"] == q["id"] and qd.get("notify_empty"):
                                        await send_telegram(BOT_TOKEN, USER_CHAT_ID,
                                            f"🔍 <b>{q['name']}</b>\n"
                                            f"📭 Nic nowego nie znaleziono\n"
                                            f"⏰ Następne sprawdzenie za {CHECK_INTERVAL//60} min")
                        except:
                            pass
                        continue
                    
                    # Send to panel
                    result = await send_to_panel(items)
                    imported = result.get("imported", 0)
                    
                    if imported > 0:
                        # Alert user on Telegram
                        msg = f"🔍 <b>{q['name']}</b>\n"
                        msg += f"📊 Znaleziono {len(items)} | Nowe: {imported}\n\n"
                        
                        for item in items[:5]:
                            price = item.get("price", 0)
                            brand = item.get("brand", "")
                            title = item.get("title", "")[:40]
                            msg += f"💰 <b>{price} zł</b> | {title}\n"
                            if brand:
                                msg += f"   🏷️ {brand}\n"
                            msg += f"   🔗 {item.get('url', '')}\n\n"
                        
                        if len(items) > 5:
                            msg += f"... i {len(items)-5} więcej w panelu"
                        
                        await send_telegram(BOT_TOKEN, USER_CHAT_ID, msg)
                        logger.info(f"Scraped {imported} new items for {q['name']}")
                    
                    await asyncio.sleep(2)  # Delay between queries
                    
                except Exception as e:
                    logger.error(f"Error scraping {q['name']}: {e}")
            
            await asyncio.sleep(CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Loop error: {e}")
            await asyncio.sleep(30)

async def main():
    global USER_CHAT_ID
    
    logger.info("🤖 Vinted Bot started!")
    
    offset = None
    
    # Start scraper in background
    asyncio.create_task(run_scraper_loop())
    
    while True:
        try:
            updates = await get_updates(BOT_TOKEN, offset)
            
            for update in updates:
                offset = update["update_id"] + 1
                msg = update.get("message", {})
                chat_id = msg.get("chat", {}).get("id")
                text = msg.get("text", "")
                
                if not chat_id or not text:
                    continue
                
                # Set user
                USER_CHAT_ID = chat_id
                
                if text == "/start":
                    await send_telegram(BOT_TOKEN, chat_id,
                        "🤖 <b>Vinted Bot</b>\n\n"
                        "Bot jest połączony z Twoim panelem!\n\n"
                        "📋 <b>Co robi:</b>\n"
                        "• Scrapuje Vinted z Twojego IP\n"
                        "• Wysyła dane do panelu\n"
                        "• Alerty na Telegram\n\n"
                        "⚡ Dodaj wyszukiwanie w panelu → bot automatycznie zacznie scrapować\n\n"
                        "📊 /status - status bota\n"
                        "🔍 /list - aktywne wyszukiwania"
                    )
                
                elif text == "/status":
                    await send_telegram(BOT_TOKEN, chat_id,
                        f"✅ Bot działa\n"
                        f"🔗 Panel: {PANEL_URL}\n"
                        f"⏰ Interwał: {CHECK_INTERVAL//60} min\n"
                        f"👤 Chat: {chat_id}"
                    )
                
                elif text == "/list":
                    queries = await get_panel_queries()
                    if queries:
                        msg = "📋 <b>Aktywne wyszukiwania:</b>\n\n"
                        for q in queries:
                            msg += f"• {q['name']}\n  {q['url'][:60]}...\n\n"
                    else:
                        msg = "Brak aktywnych wyszukiwań.\nDodaj w panelu!"
                    await send_telegram(BOT_TOKEN, chat_id, msg)
                
                else:
                    await send_telegram(BOT_TOKEN, chat_id,
                        "Nie zrozumiałem. Użyj /start /status /list"
                    )
        
        except Exception as e:
            logger.error(f"Update error: {e}")
            await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(main())
