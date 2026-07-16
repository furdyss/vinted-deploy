import asyncio
import json
import httpx
from urllib.parse import urlparse, parse_qs

PANEL_URL = "http://169.58.23.67:8080"
BOT_TOKEN = "8970159364:AAH4VH26Y3_WfJwTQZOPjGF_3flA-Pnrk7g"
CHECK_INTERVAL = 300

USER_CHAT_ID = None

async def send_telegram(text):
    global USER_CHAT_ID
    if not USER_CHAT_ID: return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    async with httpx.AsyncClient() as client:
        await client.post(url, json={"chat_id": USER_CHAT_ID, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True})

async def get_updates(offset=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
    params = {"timeout": 30}
    if offset: params["offset"] = offset
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, params=params, timeout=35)
        return resp.json().get("result", [])

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
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{PANEL_URL}/api/bot/queries", timeout=10)
        return resp.json().get("queries", [])

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

async def scraper_loop():
    global USER_CHAT_ID
    while True:
        try:
            if not USER_CHAT_ID:
                await asyncio.sleep(5)
                continue
            queries = await get_queries()
            if not queries:
                await asyncio.sleep(CHECK_INTERVAL)
                continue
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
                        msg = f"🔍 <b>{q['name']}</b>\n📊 Nowe: {imported}\n\n"
                        for i in items[:5]:
                            msg += f"💰 <b>{i['price']} zł</b> | {i.get('title','')[:40]}\n   🔗 {i.get('url','')}\n\n"
                        if len(items) > 5: msg += f"... +{len(items)-5} w panelu"
                        await send_telegram(msg)
                    await asyncio.sleep(2)
                except Exception as e:
                    print(f"Error: {e}")
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
