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


@app.post("/api/fetch/{query_id}")
async def fetch_now(query_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(SearchQuery).where(SearchQuery.id == query_id)
    )
    q = result.scalar_one_or_none()
    if not q:
        raise HTTPException(status_code=404, detail="Query not found")

    try:
        from vinted_scraper import VintedScraper
        scraper = VintedScraper("https://www.vinted.com")
        params = _parse_vinted_url(q.url)
        items = scraper.search(params)

        new_count = 0
        for item_data in items:
            existing = await db.execute(
                select(Item).where(Item.vinted_id == str(item_data.id))
            )
            if existing.scalar_one_or_none():
                continue

            new_item = Item(
                vinted_id=str(item_data.id),
                title=getattr(item_data, "title", ""),
                price=float(getattr(item_data, "price", 0)),
                currency=getattr(item_data, "currency", "EUR"),
                brand=getattr(item_data, "brand_title", None),
                size=getattr(item_data, "size_title", None),
                color=getattr(item_data, "color", None),
                condition=getattr(item_data, "disposition", None),
                url=f"https://www.vinted.com/items/{item_data.id}",
                image_url=getattr(item_data, "photo", None),
                seller_username=getattr(item_data, "user", None) and getattr(item_data.user, "login", None) if hasattr(item_data, "user") else None,
                search_query=q.url,
            )
            db.add(new_item)

            ph = PriceHistory(
                vinted_id=str(item_data.id),
                price=float(getattr(item_data, "price", 0)),
            )
            db.add(ph)
            new_count += 1

        q.last_run = datetime.utcnow()
        await db.commit()
        return {"status": "fetched", "new_items": new_count, "total_found": len(items) if isinstance(items, list) else 0}

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


def _parse_vinted_url(url: str) -> dict:
    from urllib.parse import urlparse, parse_qs
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    result = {}
    if "search_text" in params:
        result["search_text"] = params["search_text"][0]
    if "catalog_ids[]" in params:
        result["catalog_ids"] = params["catalog_ids[]"][0]
    if "brand_ids[]" in params:
        result["brand_ids"] = params["brand_ids[]"][0]
    if "price_from" in params:
        result["price_from"] = params["price_from"][0]
    if "price_to" in params:
        result["price_to"] = params["price_to"][0]
    return result


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
