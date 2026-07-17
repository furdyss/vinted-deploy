import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Optional

from fastapi import FastAPI, Depends, Query, HTTPException, Body
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, and_
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from backend.database import init_db, get_db, Item, SearchQuery, PriceHistory, WatchedSeller, SellerItem

scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    scheduler.start()
    yield
    scheduler.shutdown()


app = FastAPI(title="Vinted Market Panel", version="1.0.0", lifespan=lifespan)

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/")
async def index():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))


@app.get("/api/stats")
async def get_stats(db: AsyncSession = Depends(get_db)):
    from sqlalchemy import text as sa_text
    
    # Single query for item stats
    row = (await db.execute(
        select(
            func.count(Item.id).label("total"),
            func.avg(Item.price).label("avg"),
            func.min(Item.price).label("min"),
            func.max(Item.price).label("max"),
        )
    )).one()
    
    total = row.total or 0
    avg_price = round(row.avg or 0, 2)
    min_price = round(row.min or 0, 2)
    max_price = round(row.max or 0, 2)
    
    # Query stats
    qrow = (await db.execute(
        select(
            func.count(SearchQuery.id),
            func.count(SearchQuery.id).filter(SearchQuery.is_active == True),
        )
    )).one()
    
    # Top brands
    brands = (await db.execute(
        select(Item.brand, func.count(Item.id).label("cnt"))
        .where(Item.brand.isnot(None))
        .group_by(Item.brand)
        .order_by(desc("cnt"))
        .limit(10)
    )).all()

    return {
        "total_items": total,
        "avg_price": avg_price,
        "min_price": min_price,
        "max_price": max_price,
        "total_queries": qrow[0] or 0,
        "active_queries": qrow[1] or 0,
        "top_brands": [{"brand": b[0], "count": b[1]} for b in brands],
    }


@app.get("/api/items")
async def get_items(
    db: AsyncSession = Depends(get_db),
    search: Optional[str] = None,
    brand: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    sort: str = "newest",
    page: int = 1,
    per_page: int = 24,
):
    query = select(Item)
    count_query = select(func.count(Item.id))

    if search:
        query = query.where(Item.title.ilike(f"%{search}%"))
        count_query = count_query.where(Item.title.ilike(f"%{search}%"))
    if brand:
        query = query.where(Item.brand == brand)
        count_query = count_query.where(Item.brand == brand)
    if min_price is not None:
        query = query.where(Item.price >= min_price)
        count_query = count_query.where(Item.price >= min_price)
    if max_price is not None:
        query = query.where(Item.price <= max_price)
        count_query = count_query.where(Item.price <= max_price)

    if sort == "price_asc":
        query = query.order_by(Item.price.asc())
    elif sort == "price_desc":
        query = query.order_by(Item.price.desc())
    else:
        query = query.order_by(Item.created_at.desc())

    total = (await db.execute(count_query)).scalar() or 0
    query = query.offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    items = result.scalars().all()

    return {
        "items": [
            {
                "id": i.id,
                "vinted_id": i.vinted_id,
                "title": i.title,
                "price": i.price,
                "currency": i.currency,
                "brand": i.brand,
                "size": i.size,
                "color": i.color,
                "condition": i.condition,
                "category": i.category,
                "url": i.url,
                "image_url": i.image_url,
                "seller": i.seller_username,
                "country": i.country,
                "competitor_price": i.competitor_price,
                "created_at": i.created_at.isoformat() if i.created_at else None,
            }
            for i in items
        ],
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page,
    }


@app.get("/api/price-history/{vinted_id}")
async def get_price_history(vinted_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(PriceHistory)
        .where(PriceHistory.vinted_id == vinted_id)
        .order_by(PriceHistory.recorded_at.asc())
    )
    history = result.scalars().all()
    return {
        "vinted_id": vinted_id,
        "history": [
            {"price": h.price, "date": h.recorded_at.isoformat()}
            for h in history
        ],
    }


@app.get("/api/price-trends")
async def get_price_trends(db: AsyncSession = Depends(get_db)):
    days = 30
    since = datetime.utcnow() - timedelta(days=days)
    result = await db.execute(
        select(
            func.date(Item.created_at).label("day"),
            func.avg(Item.price).label("avg_price"),
            func.count(Item.id).label("count"),
        )
        .where(Item.created_at >= since)
        .group_by(func.date(Item.created_at))
        .order_by(func.date(Item.created_at))
    )
    rows = result.all()
    return {
        "trends": [
            {"date": str(r[0]), "avg_price": round(r[1], 2), "count": r[2]}
            for r in rows
        ]
    }


@app.get("/api/brand-analysis")
async def get_brand_analysis(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(
            Item.brand,
            func.count(Item.id).label("count"),
            func.avg(Item.price).label("avg_price"),
            func.min(Item.price).label("min_price"),
            func.max(Item.price).label("max_price"),
        )
        .where(Item.brand.isnot(None))
        .group_by(Item.brand)
        .having(func.count(Item.id) >= 3)
        .order_by(desc("count"))
        .limit(50)
    )
    rows = result.all()
    return {
        "brands": [
            {
                "brand": r[0],
                "count": r[1],
                "avg_price": round(r[2], 2),
                "min_price": round(r[3], 2),
                "max_price": round(r[4], 2),
            }
            for r in rows
        ]
    }


@app.get("/api/queries")
async def get_queries(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(SearchQuery).order_by(SearchQuery.created_at.desc())
    )
    queries = result.scalars().all()
    return {
        "queries": [
            {
                "id": q.id,
                "name": q.name,
                "url": q.url,
                "is_active": q.is_active,
                "interval_minutes": q.interval_minutes, "notify_empty": q.notify_empty,
                "target_price": q.target_price,
                "last_run": q.last_run.isoformat() if q.last_run else None,
                "created_at": q.created_at.isoformat() if q.created_at else None,
            }
            for q in queries
        ]
    }


@app.post("/api/queries")
async def add_query(
    name: str = Query(...),
    url: str = Query(...),
    interval: int = Query(default=30),
    target_price: float = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    existing = await db.execute(
        select(SearchQuery).where(SearchQuery.url == url)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Query already exists")

    q = SearchQuery(name=name, url=url, interval_minutes=interval, notify_empty=False, target_price=target_price)
    db.add(q)
    await db.commit()
    return {"status": "ok", "id": q.id}


@app.delete("/api/queries/{query_id}")
async def delete_query(query_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(SearchQuery).where(SearchQuery.id == query_id)
    )
    q = result.scalar_one_or_none()
    if not q:
        raise HTTPException(status_code=404, detail="Query not found")
    await db.delete(q)
    await db.commit()
    return {"status": "deleted"}


@app.post("/api/queries/{query_id}/toggle")
async def toggle_query(query_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(SearchQuery).where(SearchQuery.id == query_id)
    )
    q = result.scalar_one_or_none()
    if not q:
        raise HTTPException(status_code=404, detail="Query not found")
    q.is_active = not q.is_active
    await db.commit()
    return {"status": "toggled", "is_active": q.is_active}


@app.post("/api/fetch/{qid}")
async def fetch_now(qid:int,db:AsyncSession=Depends(get_db)):
    q=(await db.execute(select(SearchQuery).where(SearchQuery.id==qid))).scalar_one_or_none()
    if not q:raise HTTPException(404)
    try:
        import httpx,time as _time
        from urllib.parse import urlparse,parse_qs
        
        parsed=urlparse(q.url)
        base=f"{parsed.scheme}://{parsed.netloc}"
        
        domains_to_try=[base,"https://www.vinted.pl","https://www.vinted.fr","https://www.vinted.de"]
        last_error=None
        
        for domain in domains_to_try:
            try:
                headers={
                    "User-Agent":"Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1",
                    "Accept":"text/html,application/xhtml+xml",
                    "Accept-Language":"pl-PL,pl;q=0.9",
                }
                
                async with httpx.AsyncClient(follow_redirects=True,timeout=15,http2=True) as client:
                    resp=await client.get(domain,headers=headers)
                    cookies=dict(resp.cookies)
                    
                    _time.sleep(0.5)
                    
                    api_headers={
                        "User-Agent":headers["User-Agent"],
                        "Accept":"application/json",
                        "Accept-Language":"pl-PL,pl;q=0.9",
                        "Referer":f"{domain}/catalog",
                    }
                    
                    params=parse_qs(parsed.query)
                    api_params={k:v[0] if len(v)==1 else v for k,v in params.items()}
                    api_params["per_page"]="96"
                    api_params["order"]="newest_first"
                    
                    api_url=f"{domain}/api/v2/catalog/items"
                    resp=await client.get(api_url,params=api_params,headers=api_headers,cookies=cookies)
                    
                    if resp.status_code==200:
                        data=resp.json()
                        items_list=data.get("items",[])
                        nc=0
                        for item in items_list:
                            vid=str(item.get("id",""))
                            ex=await db.execute(select(Item).where(Item.vinted_id==vid))
                            if ex.scalar_one_or_none():continue
                            price_obj=item.get("price",{})
                            price_val=float(price_obj.get("amount",0)) if isinstance(price_obj,dict) else 0
                            currency_val=price_obj.get("currency_code","PLN") if isinstance(price_obj,dict) else "PLN"
                            user_obj=item.get("user",{})
                            seller=user_obj.get("login") if isinstance(user_obj,dict) else None
                            photo=None
                            photos=item.get("photo",{})
                            if isinstance(photos,dict):photo=photos.get("url") or photos.get("full_size_url")
                            db.add(Item(vinted_id=vid,title=item.get("title",""),price=price_val,currency=currency_val,brand=item.get("brand_title"),size=item.get("size_title"),color=item.get("color"),condition=item.get("status"),category=item.get("catalog_title"),url=f"{domain}/items/{vid}",image_url=photo,seller_username=seller,country=item.get("country"),search_query=q.url))
                            db.add(PriceHistory(vinted_id=vid,price=price_val))
                            nc+=1
                        q.last_run=datetime.utcnow()
                        await db.commit()
                        return{"new_items":nc,"total_found":len(items_list),"domain":domain}
                    else:
                        last_error=f"{domain}: {resp.status_code}"
                        continue
            except Exception as e:
                last_error=f"{domain}: {str(e)}"
                continue
        
        return JSONResponse(content={"error":"All domains blocked","tried":last_error},status_code=500)
    except Exception as e:
        import traceback
        return JSONResponse(content={"error":str(e),"trace":traceback.format_exc()[-300:]},status_code=500)




# ==================== VINTED LOGIN ====================

from pydantic import BaseModel

class VintedLoginRequest(BaseModel):
    email: str
    password: str

@app.post("/api/vinted/login")
async def vinted_login(req: VintedLoginRequest, db: AsyncSession = Depends(get_db)):
    """Login to Vinted and store session"""
    try:
        import httpx
        
        async with httpx.AsyncClient(follow_redirects=True, timeout=20) as client:
            # Step 1: Get main page for cookies and CSRF
            resp = await client.get("https://www.vinted.pl", headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "pl-PL,pl;q=0.9",
            })
            cookies = dict(resp.cookies)
            
            # Step 2: Login
            login_data = {
                "email": req.email,
                "password": req.password,
            }
            
            login_headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                "Accept": "application/json",
                "Content-Type": "application/json",
                "X-Requested-With": "XMLHttpRequest",
                "Referer": "https://www.vinted.pl",
            }
            
            resp = await client.post("https://www.vinted.pl/session", json=login_data, headers=login_headers, cookies=cookies)
            
            if resp.status_code == 200:
                data = resp.json()
                session_cookie = cookies.get("_vinted_fr_session", "")
                
                # Store in database
                from sqlalchemy import text
                await db.execute(text("CREATE TABLE IF NOT EXISTS vinted_session (id INTEGER PRIMARY KEY, email TEXT, cookie TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"))
                await db.execute(text("DELETE FROM vinted_session"))
                await db.execute(text("INSERT INTO vinted_session (email, cookie) VALUES (:email, :cookie)"), {"email": req.email, "cookie": session_cookie})
                await db.commit()
                
                return {"status": "ok", "message": "Zalogowano pomyślnie!"}
            else:
                return JSONResponse(content={"error": f"Logowanie nie powiodło się: {resp.status_code}"}, status_code=400)
                
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)

@app.get("/api/vinted/status")
async def vinted_status(db: AsyncSession = Depends(get_db)):
    """Check if Vinted session is active"""
    try:
        from sqlalchemy import text
        result = await db.execute(text("SELECT email FROM vinted_session LIMIT 1"))
        row = result.fetchone()
        if row:
            return {"status": "logged_in", "email": row[0]}
        return {"status": "not_logged_in"}
    except:
        return {"status": "not_logged_in"}

@app.post("/api/vinted/logout")
async def vinted_logout(db: AsyncSession = Depends(get_db)):
    """Logout from Vinted"""
    try:
        from sqlalchemy import text
        await db.execute(text("DELETE FROM vinted_session"))
        await db.commit()
        return {"status": "ok", "message": "Wylogowano"}
    except:
        return {"status": "ok"}


@app.post("/api/queries/{qid}/toggle-notify")
async def toggle_notify_empty(qid:int, db:AsyncSession=Depends(get_db)):
    q=(await db.execute(select(SearchQuery).where(SearchQuery.id==qid))).scalar_one_or_none()
    if not q:raise HTTPException(404)
    q.notify_empty = not q.notify_empty
    await db.commit()
    return{"notify_empty": q.notify_empty}


@app.post("/api/vinted/set-cookie")
async def set_cookie(data: dict, db: AsyncSession = Depends(get_db)):
    """Receive cookie from bot"""
    try:
        from sqlalchemy import text
        await db.execute(text("CREATE TABLE IF NOT EXISTS vinted_session (id INTEGER PRIMARY KEY, email TEXT, cookie TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"))
        await db.execute(text("DELETE FROM vinted_session"))
        await db.execute(text("INSERT INTO vinted_session (email, cookie) VALUES (:email, :cookie)"), {"email": data.get("email",""), "cookie": data.get("cookie","")})
        await db.commit()
        return {"status": "ok"}
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


@app.get("/api/brand-averages")
async def get_brand_averages(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(
            Item.brand,
            func.avg(Item.price).label("avg_price"),
            func.count(Item.id).label("count"),
        )
        .where(Item.brand.isnot(None))
        .group_by(Item.brand)
        .having(func.count(Item.id) >= 3)
    )
    rows = result.all()
    return {r[0]: {"avg": round(r[1], 2), "count": r[2]} for r in rows}


# ==================== WATCHED SELLERS ====================

@app.get("/api/sellers")
async def get_sellers(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(WatchedSeller).order_by(WatchedSeller.created_at.desc())
    )
    sellers = result.scalars().all()
    return {
        "sellers": [
            {
                "id": s.id,
                "username": s.username,
                "user_id": s.user_id,
                "profile_url": s.profile_url,
                "last_item_count": s.last_item_count,
                "is_active": s.is_active,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            }
            for s in sellers
        ]
    }

@app.post("/api/sellers")
async def add_seller(
    username: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    existing = await db.execute(
        select(WatchedSeller).where(WatchedSeller.username == username)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Sprzedawca już jest na liście")
    
    # Resolve user_id from Vinted API
    user_id = None
    item_count = 0
    try:
        import httpx
        async with httpx.AsyncClient(follow_redirects=True, timeout=10) as client:
            resp = await client.get(f"https://www.vinted.pl/api/v2/users/{username}",
                headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
            if resp.status_code == 200:
                data = resp.json().get("user", {})
                user_id = str(data.get("id", ""))
                item_count = data.get("item_count", 0) or 0
    except:
        pass
    
    s = WatchedSeller(
        username=username,
        user_id=user_id,
        profile_url=f"https://www.vinted.pl/member/{username}",
        last_item_count=item_count,
    )
    db.add(s)
    await db.commit()
    return {"status": "ok", "id": s.id, "user_id": user_id, "item_count": item_count}

@app.delete("/api/sellers/{seller_id}")
async def delete_seller(seller_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(WatchedSeller).where(WatchedSeller.id == seller_id))
    s = result.scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404)
    await db.delete(s)
    await db.commit()
    return {"status": "deleted"}

@app.post("/api/sellers/{seller_id}/toggle")
async def toggle_seller(seller_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(WatchedSeller).where(WatchedSeller.id == seller_id))
    s = result.scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404)
    s.is_active = not s.is_active
    await db.commit()
    return {"status": "toggled", "is_active": s.is_active}

@app.get("/api/bot/sellers")
async def bot_get_sellers(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(WatchedSeller).where(WatchedSeller.is_active == True)
    )
    sellers = result.scalars().all()
    return {"sellers": [{"id": s.id, "username": s.username, "user_id": s.user_id, "last_item_count": s.last_item_count} for s in sellers]}

@app.post("/api/bot/sellers/update")
async def bot_update_seller(data: dict, db: AsyncSession = Depends(get_db)):
    seller_id = data.get("seller_id")
    item_count = data.get("item_count", 0)
    user_id = data.get("user_id")
    result = await db.execute(select(WatchedSeller).where(WatchedSeller.id == seller_id))
    s = result.scalar_one_or_none()
    if s:
        s.last_item_count = item_count
        if user_id and user_id != "None":
            s.user_id = str(user_id)
        await db.commit()
    return {"status": "ok"}


@app.post("/api/items/{item_id}/compare")
async def set_competitor_price(
    item_id: int,
    competitor_price: float = Query(...),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Item).where(Item.id == item_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404)
    item.competitor_price = competitor_price
    await db.commit()
    return {"status": "ok", "competitor_price": competitor_price}


@app.get("/api/sellers/{seller_id}/items")
async def get_seller_items(seller_id: int, db: AsyncSession = Depends(get_db)):
    """Get seller's items from database (populated by bot)"""
    result = await db.execute(select(WatchedSeller).where(WatchedSeller.id == seller_id))
    seller = result.scalar_one_or_none()
    if not seller:
        raise HTTPException(status_code=404)
    
    items_result = await db.execute(
        select(SellerItem)
        .where(SellerItem.seller_id == seller_id)
        .order_by(SellerItem.is_available.desc(), SellerItem.last_checked.desc())
    )
    items = items_result.scalars().all()
    
    return {
        "seller": {"id": seller.id, "username": seller.username, "user_id": seller.user_id},
        "items": [
            {
                "id": i.id,
                "vinted_id": i.vinted_id,
                "title": i.title or "Sprzedane",
                "price": i.price,
                "previous_price": i.previous_price,
                "brand": i.brand,
                "photo": i.photo_url,
                "url": i.url or f"https://www.vinted.pl/items/{i.vinted_id}",
                "is_available": i.is_available,
                "first_seen": i.first_seen.isoformat() if i.first_seen else None,
                "last_checked": i.last_checked.isoformat() if i.last_checked else None,
            }
            for i in items
        ],
        "total": len([i for i in items if i.is_available]),
    }


@app.get("/api/sellers/{seller_id}/price-history")
async def get_seller_price_history(seller_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(SellerItem)
        .where(SellerItem.seller_id == seller_id)
        .where(SellerItem.is_available == True)
        .order_by(SellerItem.last_checked.desc())
    )
    items = result.scalars().all()
    return {
        "items": [
            {
                "vinted_id": i.vinted_id,
                "title": i.title,
                "price": i.price,
                "previous_price": i.previous_price,
                "photo_url": i.photo_url,
                "url": i.url,
                "brand": i.brand,
                "first_seen": i.first_seen.isoformat() if i.first_seen else None,
                "last_checked": i.last_checked.isoformat() if i.last_checked else None,
            }
            for i in items
        ]
    }

@app.get("/api/bot/seller-items/{seller_id}")
async def bot_get_seller_items(seller_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(SellerItem)
        .where(SellerItem.seller_id == seller_id)
        .where(SellerItem.is_available == True)
    )
    items = result.scalars().all()
    return {"items": [{"vinted_id": i.vinted_id, "price": i.price} for i in items]}

@app.post("/api/bot/seller-items/update")
async def bot_update_seller_item(data: dict, db: AsyncSession = Depends(get_db)):
    vinted_id = str(data.get("vinted_id", ""))
    seller_id = data.get("seller_id")
    title = data.get("title", "")
    price = float(data.get("price", 0))
    photo_url = data.get("photo_url")
    url = data.get("url", "")
    brand = data.get("brand")
    is_available = data.get("is_available", True)
    
    result = await db.execute(
        select(SellerItem).where(SellerItem.vinted_id == vinted_id).where(SellerItem.seller_id == seller_id)
    )
    item = result.scalar_one_or_none()
    
    if item:
        item.previous_price = item.price if item.price != price and price > 0 else item.previous_price
        if price > 0:
            item.price = price
        if title:
            item.title = title
        if photo_url:
            item.photo_url = photo_url
        item.is_available = is_available
        item.last_checked = datetime.utcnow()
    else:
        item = SellerItem(
            vinted_id=vinted_id, seller_id=seller_id, title=title,
            price=price, photo_url=photo_url, url=url, brand=brand,
            is_available=is_available
        )
        db.add(item)
    
    await db.commit()
    return {"status": "ok"}

# ==================== BOT API ====================

@app.post("/api/bot/import")
async def bot_import(items: list = Body(...), db: AsyncSession = Depends(get_db)):
    """Bot sends scraped items here"""
    nc = 0
    for item in items:
        vid = str(item.get("vinted_id", item.get("id", "")))
        if not vid:
            continue
        ex = await db.execute(select(Item).where(Item.vinted_id == vid))
        if ex.scalar_one_or_none():
            continue
        db.add(Item(
            vinted_id=vid,
            title=item.get("title", ""),
            price=float(item.get("price", 0)),
            currency="PLN",
            brand=item.get("brand"),
            size=item.get("size"),
            color=item.get("color"),
            condition=item.get("condition"),
            category=item.get("category"),
            url=item.get("url", ""),
            image_url=item.get("image_url"),
            seller_username=item.get("seller"),
            country=item.get("country"),
            search_query=item.get("query", ""),
        ))
        db.add(PriceHistory(vinted_id=vid, price=float(item.get("price", 0))))
        nc += 1
    await db.commit()
    return {"imported": nc}

@app.get("/api/bot/queries")
async def bot_get_queries(db: AsyncSession = Depends(get_db)):
    """Bot gets list of active queries to scrape"""
    result = await db.execute(
        select(SearchQuery).where(SearchQuery.is_active == True)
    )
    queries = result.scalars().all()
    return {"queries": [{"id": q.id, "name": q.name, "url": q.url, "target_price": q.target_price} for q in queries]}

@app.get("/api/bot/status")
async def bot_status():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
