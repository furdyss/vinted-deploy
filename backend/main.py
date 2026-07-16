import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Optional

from fastapi import FastAPI, Depends, Query, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, and_
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from backend.database import init_db, get_db, Item, SearchQuery, PriceHistory

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
    total = (await db.execute(select(func.count(Item.id)))).scalar() or 0
    avg_price = (await db.execute(select(func.avg(Item.price)))).scalar() or 0
    min_price = (await db.execute(select(func.min(Item.price)))).scalar() or 0
    max_price = (await db.execute(select(func.max(Item.price)))).scalar() or 0
    queries_count = (await db.execute(select(func.count(SearchQuery.id)))).scalar() or 0
    active_queries = (await db.execute(
        select(func.count(SearchQuery.id)).where(SearchQuery.is_active == True)
    )).scalar() or 0
    brands = (await db.execute(
        select(Item.brand, func.count(Item.id).label("cnt"))
        .where(Item.brand.isnot(None))
        .group_by(Item.brand)
        .order_by(desc("cnt"))
        .limit(10)
    )).all()

    return {
        "total_items": total,
        "avg_price": round(avg_price, 2),
        "min_price": round(min_price, 2),
        "max_price": round(max_price, 2),
        "total_queries": queries_count,
        "active_queries": active_queries,
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
                "interval_minutes": q.interval_minutes,
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
    db: AsyncSession = Depends(get_db),
):
    existing = await db.execute(
        select(SearchQuery).where(SearchQuery.url == url)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Query already exists")

    q = SearchQuery(name=name, url=url, interval_minutes=interval)
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



# ==================== BOT API ====================

@app.post("/api/bot/import")
async def bot_import(items: list, db: AsyncSession = Depends(get_db)):
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
    return {"queries": [{"id": q.id, "name": q.name, "url": q.url} for q in queries]}

@app.get("/api/bot/status")
async def bot_status():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
