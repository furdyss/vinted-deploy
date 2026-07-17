import asyncio
import json
import httpx
from urllib.parse import urlparse, parse_qs

PANEL_URL = "http://169.58.23.67:8080"
BOT_TOKEN = "8970159364:AAH4VH26Y3_WfJwTQZOPjGF_3flA-Pnrk7g"
CHECK_INTERVAL = 120

USER_CHAT_ID = None

_http_client = None

def get_http_client():
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(follow_redirects=True, timeout=15)
    return _http_client

async def send_telegram(text):
    global USER_CHAT_ID
    if not USER_CHAT_ID: return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        await get_http_client().post(url, json={"chat_id": USER_CHAT_ID, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True})
    except Exception as e:
        print(f"Telegram error: {e}")

async def get_updates(offset=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
    params = {"timeout": 30}
    if offset: params["offset"] = offset
    try:
        resp = await get_http_client().get(url, params=params, timeout=35)
        return resp.json().get("result", [])
    except:
        return []

async def scrape_vinted(query_url):
    parsed = urlparse(query_url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15",
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "pl-PL,pl;q=0.9",
    }
    async with httpx.AsyncClient(follow_redirects=True, timeout=15) as client:
        resp = await client.get(base, headers=headers)
        cookies = dict(resp.cookies)
        await asyncio.sleep(1)
        api_headers = {"User-Agent": headers["User-Agent"], "Accept": "application/json", "Referer": f"{base}/catalog"}
        params = parse_qs(parsed.query)
        api_params = {k: v[0] if len(v) == 1 else v for k, v in params.items()}
        api_params["per_page"] = "96"
        api_params["order"] = "newest_first"
        resp = await client.get(f"{base}/api/v2/catalog/items", params=api_params, headers=api_headers, cookies=cookies)
        if resp.status_code != 200: return [], f"Vinted {resp.status_code}"
        items = resp.json().get("items", [])
        results = []
        for item in items:
            po = item.get("price", {})
            price = float(po.get("amount", 0)) if isinstance(po, dict) else 0
            user_obj = item.get("user", {})
            seller = user_obj.get("login") if isinstance(user_obj, dict) else None
            photo = None
            ph = item.get("photo", {})
            if isinstance(ph, dict): photo = ph.get("url") or ph.get("full_size_url")
            results.append({"vinted_id": str(item.get("id","")), "title": item.get("title",""), "price": price, "brand": item.get("brand_title"), "size": item.get("size_title"), "color": item.get("color"), "condition": item.get("status"), "category": item.get("catalog_title"), "url": f"{base}/items/{item.get('id','')}", "image_url": photo, "seller": seller, "country": item.get("country"), "query": query_url})
        return results, None

async def send_to_panel(items):
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{PANEL_URL}/api/bot/import", json=items, timeout=30)
        return resp.json()

async def get_queries():
    try:
        resp = await get_http_client().get(f"{PANEL_URL}/api/bot/queries", timeout=10)
        return resp.json().get("queries", [])
    except:
        return []

async def handle_login(email, password):
    try:
        headers = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15", "Accept": "text/html", "Accept-Language": "pl-PL,pl;q=0.9"}
        async with httpx.AsyncClient(follow_redirects=True, timeout=20) as client:
            resp = await client.get("https://www.vinted.pl", headers=headers)
            cookies = dict(resp.cookies)
            await asyncio.sleep(1)
            login_headers = {"User-Agent": headers["User-Agent"], "Accept": "application/json", "Content-Type": "application/json", "X-Requested-With": "XMLHttpRequest", "Referer": "https://www.vinted.pl"}
            resp = await client.post("https://www.vinted.pl/session", json={"email": email, "password": password}, headers=login_headers, cookies=cookies)
            if resp.status_code == 200:
                sc = cookies.get("_vinted_fr_session", "")
                async with httpx.AsyncClient() as pc:
                    await pc.post(f"{PANEL_URL}/api/vinted/set-cookie", json={"email": email, "cookie": sc})
                return True, "Zalogowano!"
            return False, f"Status: {resp.status_code}"
    except Exception as e:
        return False, str(e)


async def get_brand_averages():
    try:
        resp = await get_http_client().get(f"{PANEL_URL}/api/brand-averages", timeout=10)
        return resp.json()
    except:
        return {}


async def get_watched_sellers():
    try:
        resp = await get_http_client().get(f"{PANEL_URL}/api/bot/sellers", timeout=10)
        return resp.json().get("sellers", [])
    except:
        return []

async def check_seller(seller):
    try:
        username = seller["username"]
        user_id = seller.get("user_id")
        seller_id = seller["id"]
        last_count = seller.get("last_item_count", 0)
        
        if not user_id:
            try:
                async with httpx.AsyncClient(follow_redirects=True, timeout=10) as client:
                    resp = await client.get(f"https://www.vinted.pl/api/v2/users/{username}",
                        headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
                    if resp.status_code == 200:
                        data = resp.json().get("user", {})
                        user_id = str(data.get("id", ""))
                        async with httpx.AsyncClient() as pc:
                            await pc.post(f"{PANEL_URL}/api/bot/sellers/update",
                                json={"seller_id": seller_id, "user_id": user_id})
            except:
                pass
        
        if not user_id:
            return
        
        headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15",
            "Accept": "application/json",
            "Accept-Language": "pl-PL,pl;q=0.9",
        }
        
        async with httpx.AsyncClient(follow_redirects=True, timeout=15) as client:
            resp = await client.get(f"https://www.vinted.pl/api/v2/catalog/items",
                params={"user_id": user_id, "per_page": "96", "order": "newest_first"},
                headers=headers)
            if resp.status_code != 200:
                return
            items = resp.json().get("items", [])
            current_count = len(items)
            
            # Get previously tracked items
            old_resp = await get_http_client().get(f"{PANEL_URL}/api/bot/seller-items/{seller_id}", timeout=10)
                old_items = {i["vinted_id"]: i["price"] for i in old_resp.json().get("items", [])}
            
            current_ids = set()
            
            for item in items:
                vid = str(item.get("id", ""))
                current_ids.add(vid)
                price_obj = item.get("price", {})
                price = price_obj.get("amount", 0) if isinstance(price_obj, dict) else 0
                photo = item.get("photo", {})
                photo_url = photo.get("url") if isinstance(photo, dict) else None
                brand = item.get("brand_title")
                
                # Update item in panel
                try:
                    await get_http_client().post(f"{PANEL_URL}/api/bot/seller-items/update", json={
                        "vinted_id": vid, "seller_id": seller_id,
                        "title": item.get("title", ""), "price": price,
                        "photo_url": photo_url, "url": f"https://www.vinted.pl/items/{vid}",
                        "brand": brand, "is_available": True
                    })
                
                # Check for price change
                if vid in old_items and old_items[vid] != price and old_items[vid] > 0:
                    old_price = old_items[vid]
                    diff = round(old_price - price, 2)
                    emoji = "📉" if price < old_price else "📈"
                    msg = f"{emoji} <b>Zmiana ceny!</b> {username}\n"
                    msg += f"📦 {item.get('title', '')}\n"
                    msg += f"💰 {old_price} zł → <b>{price} zł</b>"
                    if diff > 0:
                        msg += f" (taniej o {diff} zł)"
                    else:
                        msg += f" (drożej o {abs(diff)} zł)"
                    msg += f"\n🔗 https://www.vinted.pl/items/{vid}"
                    await send_telegram(msg)
            
            # Check for new items
            if last_count > 0 and current_count > last_count:
                new_count = current_count - last_count
                msg = f"👤 <b>{username}</b> dodał {new_count} nowych ogłoszeń!\n\n"
                for item in items[:5]:
                    price_obj = item.get("price", {})
                    price = price_obj.get("amount", 0) if isinstance(price_obj, dict) else 0
                    msg += f"💰 <b>{price} zł</b> | {item.get('title', '')[:40]}\n"
                    msg += f"🔗 https://www.vinted.pl/items/{item.get('id', '')}\n\n"
                await send_telegram(msg)
            
            # Check for sold items (were tracked but no longer in current list)
            for old_vid in old_items:
                if old_vid not in current_ids:
                    try:
                        await get_http_client().post(f"{PANEL_URL}/api/bot/seller-items/update", json={
                            "vinted_id": old_vid, "seller_id": seller_id,
                            "title": "", "price": old_items[old_vid],
                            "is_available": False
                        })
                    except:
                        pass
                    msg = f"✅ <b>Sprzedano!</b> {username}\n"
                    msg += f"📦 Przedmiot został sprzedany\n"
                    msg += f"💰 Ostatnia cena: {old_items[old_vid]} zł"
                    await send_telegram(msg)
            
            # Update seller count
            try:
                await get_http_client().post(f"{PANEL_URL}/api/bot/sellers/update", 
                    json={"seller_id": seller_id, "item_count": current_count})
    
    except Exception as e:
        print(f"Seller check error: {e}")

async def scraper_loop():
    global USER_CHAT_ID
    while True:
        try:
            if not USER_CHAT_ID:
                await asyncio.sleep(5)
                continue

            # Process search queries
            queries = await get_queries()
            if queries:
                averages = await get_brand_averages()
                for q in queries:
                    try:
                        items, error = await scrape_vinted(q["url"])
                        if error or not items:
                            if q.get("notify_empty") and not error:
                                await send_telegram(f"🔍 <b>{q['name']}</b>\n📭 Nic nowego")
                            continue
                        result = await send_to_panel(items)
                        imported = result.get("imported", 0)
                        if imported > 0:
                            for i in items[:imported]:
                                price = i.get('price', 0)
                                target = q.get('target_price')
                                brand = i.get('brand')
                                avg = averages.get(brand, {}).get('avg') if brand else None

                                is_target_deal = target and price > 0 and price <= target
                                is_brand_deal = avg and price > 0 and price <= avg * 0.6

                                if is_target_deal:
                                    savings = round(target - price, 2)
                                    msg = f"🔥 <b>OKAZJA CENOWA!</b> {q['name']}\n"
                                    msg += f"💰 <b>{price} zł</b> (docelowa: {target} zł)\n"
                                    msg += f"💵 Oszczędzasz: {savings} zł\n"
                                    msg += f"📦 {i.get('title','')}\n"
                                    if brand: msg += f"🏷️ {brand}\n"
                                    msg += f"🔗 {i.get('url','')}"
                                elif is_brand_deal:
                                    discount = round((1 - price/avg) * 100)
                                    msg = f"⚡ <b>OKAZJA RYNKOWA!</b> {q['name']}\n"
                                    msg += f"💰 <b>{price} zł</b> (śr. {avg} zł — {discount}% taniej!)\n"
                                    msg += f"📦 {i.get('title','')}\n"
                                    if brand: msg += f"🏷️ {brand}\n"
                                    msg += f"🔗 {i.get('url','')}"
                                else:
                                    msg = f"🔍 <b>{q['name']}</b>\n"
                                    msg += f"💰 <b>{price} zł</b>\n"
                                    msg += f"📦 {i.get('title','')}\n"
                                    if brand: msg += f"🏷️ {brand}\n"
                                    if i.get('size'): msg += f"📏 {i['size']}\n"
                                    msg += f"🔗 {i.get('url','')}"
                                await send_telegram(msg)
                                await asyncio.sleep(1)
                        await asyncio.sleep(3)
                    except Exception as e:
                        print(f"Error scraping {q['name']}: {e}")
                        await asyncio.sleep(5)

            # Check watched sellers
            sellers = await get_watched_sellers()
            for seller in sellers:
                await check_seller(seller)
                await asyncio.sleep(3)

            await asyncio.sleep(CHECK_INTERVAL)

        except Exception as e:
            print(f"Loop error: {e}")
            await asyncio.sleep(30)

async def main():
    global USER_CHAT_ID
    print("Bot started!")
    asyncio.create_task(scraper_loop())
    offset = None
    while True:
        try:
            updates = await get_updates(offset)
            for update in updates:
                offset = update["update_id"] + 1
                msg = update.get("message", {})
                chat_id = msg.get("chat", {}).get("id")
                text = msg.get("text", "")
                if not chat_id or not text: continue
                USER_CHAT_ID = chat_id
                
                if text == "/start":
                    await send_telegram("🤖 <b>Vinted Bot</b>\n\nGotowy!\n\nKomendy:\n/status - status\n/list - wyszukiwania\n/login email haslo - logowanie")
                
                elif text == "/status":
                    await send_telegram(f"✅ Bot działa\n🔗 Panel: {PANEL_URL}\n⏰ Co {CHECK_INTERVAL//60} min")
                
                elif text.startswith("/login"):
                    parts = text.split(" ", 2)
                    if len(parts) < 3:
                        await send_telegram("Użycie: /login email haslo")
                    else:
                        await send_telegram("⏳ Logowanie...")
                        ok, msg = await handle_login(parts[1], parts[2])
                        await send_telegram(f"{'✅' if ok else '❌'} {msg}")
                
                elif text == "/list":
                    queries = await get_queries()
                    if queries:
                        msg = "📋 <b>Wyszukiwania:</b>\n\n"
                        for q in queries:
                            msg += f"• {q['name']}\n"
                        await send_telegram(msg)
                    else:
                        await send_telegram("Brak wyszukiwań. Dodaj w panelu!")
                
                else:
                    await send_telegram("Komendy: /start /status /list /login")
        except Exception as e:
            print(f"Update error: {e}")
            await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(main())
