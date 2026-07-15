#!/bin/bash
set -e;mkdir -p /opt/vinted-panel/{backend,frontend/{css,js},data}
apt-get update -qq;apt-get install -y -qq docker.io docker-compose-plugin curl ufw
systemctl enable docker;systemctl start docker
cat > /opt/vinted-panel/backend/requirements.txt << 'EOF'
fastapi==0.115.0
uvicorn[standard]==0.30.0
vinted_scraper==1.3.2
sqlalchemy==2.0.35
aiosqlite==0.20.0
apscheduler==3.10.4
python-multipart==0.0.9
httpx==0.27.0
pydantic==2.9.0
EOF
cat > /opt/vinted-panel/backend/database.py << 'EOF'
import os
from sqlalchemy.ext.asyncio import create_async_engine,AsyncSession,async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import Column,Integer,String,Float,DateTime,Text,Boolean
from datetime import datetime
DATABASE_URL=os.getenv("DATABASE_URL","sqlite+aiosqlite:///./data/vinted.db")
engine=create_async_engine(DATABASE_URL,echo=False)
async_session=async_sessionmaker(engine,class_=AsyncSession,expire_on_commit=False)
class Base(DeclarativeBase):pass
class Item(Base):
    __tablename__="items"
    id=Column(Integer,primary_key=True,autoincrement=True)
    vinted_id=Column(String,unique=True,index=True)
    title=Column(String);description=Column(Text,nullable=True)
    price=Column(Float);currency=Column(String,default="EUR")
    brand=Column(String,nullable=True);size=Column(String,nullable=True)
    color=Column(String,nullable=True);condition=Column(String,nullable=True)
    category=Column(String,nullable=True);url=Column(String)
    image_url=Column(String,nullable=True);seller_username=Column(String,nullable=True)
    country=Column(String,nullable=True);search_query=Column(String,index=True)
    created_at=Column(DateTime,default=datetime.utcnow)
class SearchQuery(Base):
    __tablename__="search_queries"
    id=Column(Integer,primary_key=True,autoincrement=True)
    name=Column(String);url=Column(String,unique=True)
    is_active=Column(Boolean,default=True);interval_minutes=Column(Integer,default=30)
    last_run=Column(DateTime,nullable=True);created_at=Column(DateTime,default=datetime.utcnow)
class PriceHistory(Base):
    __tablename__="price_history"
    id=Column(Integer,primary_key=True,autoincrement=True)
    vinted_id=Column(String,index=True);price=Column(Float)
    recorded_at=Column(DateTime,default=datetime.utcnow)
async def init_db():
    async with engine.begin() as conn:await conn.run_sync(Base.metadata.create_all)
async def get_db():
    async with async_session() as session:yield session
EOF
cat > /opt/vinted-panel/backend/main.py << 'EOF'
import os
from contextlib import asynccontextmanager
from datetime import datetime,timedelta
from typing import Optional
from fastapi import FastAPI,Depends,Query,HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse,JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select,func,desc
from database import init_db,get_db,Item,SearchQuery,PriceHistory
@asynccontextmanager
async def lifespan(app:FastAPI):await init_db();yield
app=FastAPI(title="Vinted Market Panel",version="1.0.0",lifespan=lifespan)
FRONTEND_DIR=os.path.join(os.path.dirname(__file__),"..","frontend")
app.mount("/static",StaticFiles(directory=FRONTEND_DIR),name="static")
@app.get("/")
async def index():return FileResponse(os.path.join(FRONTEND_DIR,"index.html"))
@app.get("/api/stats")
async def get_stats(db:AsyncSession=Depends(get_db)):
    t=(await db.execute(select(func.count(Item.id)))).scalar() or 0
    a=(await db.execute(select(func.avg(Item.price)))).scalar() or 0
    mn=(await db.execute(select(func.min(Item.price)))).scalar() or 0
    mx=(await db.execute(select(func.max(Item.price)))).scalar() or 0
    qc=(await db.execute(select(func.count(SearchQuery.id)))).scalar() or 0
    ac=(await db.execute(select(func.count(SearchQuery.id)).where(SearchQuery.is_active==True))).scalar() or 0
    br=(await db.execute(select(Item.brand,func.count(Item.id).label("c")).where(Item.brand.isnot(None)).group_by(Item.brand).order_by(desc("c")).limit(10))).all()
    return{"total_items":t,"avg_price":round(a,2),"min_price":round(mn,2),"max_price":round(mx,2),"total_queries":qc,"active_queries":ac,"top_brands":[{"brand":b[0],"count":b[1]} for b in br]}
@app.get("/api/items")
async def get_items(db:AsyncSession=Depends(get_db),search:Optional[str]=None,brand:Optional[str]=None,min_price:Optional[float]=None,max_price:Optional[float]=None,sort:str="newest",page:int=1,per_page:int=24):
    q=select(Item);cq=select(func.count(Item.id))
    if search:q=q.where(Item.title.ilike(f"%{search}%"));cq=cq.where(Item.title.ilike(f"%{search}%"))
    if brand:q=q.where(Item.brand==brand);cq=cq.where(Item.brand==brand)
    if min_price is not None:q=q.where(Item.price>=min_price);cq=cq.where(Item.price>=min_price)
    if max_price is not None:q=q.where(Item.price<=max_price);cq=cq.where(Item.price<=max_price)
    if sort=="price_asc":q=q.order_by(Item.price.asc())
    elif sort=="price_desc":q=q.order_by(Item.price.desc())
    else:q=q.order_by(Item.created_at.desc())
    total=(await db.execute(cq)).scalar() or 0
    q=q.offset((page-1)*per_page).limit(per_page)
    items=(await db.execute(q)).scalars().all()
    return{"items":[{"id":i.id,"vinted_id":i.vinted_id,"title":i.title,"price":i.price,"currency":i.currency,"brand":i.brand,"size":i.size,"color":i.color,"condition":i.condition,"category":i.category,"url":i.url,"image_url":i.image_url,"seller":i.seller_username,"country":i.country,"created_at":i.created_at.isoformat() if i.created_at else None} for i in items],"total":total,"page":page,"per_page":per_page,"pages":(total+per_page-1)//per_page}
@app.get("/api/price-trends")
async def get_price_trends(db:AsyncSession=Depends(get_db)):
    since=datetime.utcnow()-timedelta(days=30)
    r=(await db.execute(select(func.date(Item.created_at).label("d"),func.avg(Item.price).label("a"),func.count(Item.id).label("c")).where(Item.created_at>=since).group_by(func.date(Item.created_at)).order_by(func.date(Item.created_at)))).all()
    return{"trends":[{"date":str(x[0]),"avg_price":round(x[1],2),"count":x[2]} for x in r]}
@app.get("/api/brand-analysis")
async def get_brand_analysis(db:AsyncSession=Depends(get_db)):
    r=(await db.execute(select(Item.brand,func.count(Item.id).label("c"),func.avg(Item.price).label("a"),func.min(Item.price).label("mn"),func.max(Item.price).label("mx")).where(Item.brand.isnot(None)).group_by(Item.brand).having(func.count(Item.id)>=3).order_by(desc("c")).limit(50))).all()
    return{"brands":[{"brand":x[0],"count":x[1],"avg_price":round(x[2],2),"min_price":round(x[3],2),"max_price":round(x[4],2)} for x in r]}
@app.get("/api/queries")
async def get_queries(db:AsyncSession=Depends(get_db)):
    qs=(await db.execute(select(SearchQuery).order_by(SearchQuery.created_at.desc()))).scalars().all()
    return{"queries":[{"id":q.id,"name":q.name,"url":q.url,"is_active":q.is_active,"interval_minutes":q.interval_minutes,"last_run":q.last_run.isoformat() if q.last_run else None,"created_at":q.created_at.isoformat() if q.created_at else None} for q in qs]}
@app.post("/api/queries")
async def add_query(name:str=Query(...),url:str=Query(...),interval:int=Query(default=30),db:AsyncSession=Depends(get_db)):
    if (await db.execute(select(SearchQuery).where(SearchQuery.url==url))).scalar_one_or_none():raise HTTPException(400,"Exists")
    q=SearchQuery(name=name,url=url,interval_minutes=interval);db.add(q);await db.commit()
    return{"status":"ok","id":q.id}
@app.delete("/api/queries/{qid}")
async def delete_query(qid:int,db:AsyncSession=Depends(get_db)):
    q=(await db.execute(select(SearchQuery).where(SearchQuery.id==qid))).scalar_one_or_none()
    if not q:raise HTTPException(404);await db.delete(q);await db.commit();return{"status":"deleted"}
@app.post("/api/queries/{qid}/toggle")
async def toggle(qid:int,db:AsyncSession=Depends(get_db)):
    q=(await db.execute(select(SearchQuery).where(SearchQuery.id==qid))).scalar_one_or_none()
    if not q:raise HTTPException(404);q.is_active=not q.is_active;await db.commit();return{"is_active":q.is_active}
@app.post("/api/fetch/{qid}")
async def fetch_now(qid:int,db:AsyncSession=Depends(get_db)):
    q=(await db.execute(select(SearchQuery).where(SearchQuery.id==qid))).scalar_one_or_none()
    if not q:raise HTTPException(404)
    try:
        from vinted_scraper import VintedScraper
        from urllib.parse import urlparse,parse_qs
        s=VintedScraper("https://www.vinted.com")
        p=parse_qs(urlparse(q.url).query);sp={k:v[0] if len(v)==1 else v for k,v in p.items()}
        items=s.search(sp);nc=0
        for i in items:
            if (await db.execute(select(Item).where(Item.vinted_id==str(i.id)))).scalar_one_or_none():continue
            db.add(Item(vinted_id=str(i.id),title=getattr(i,"title",""),price=float(getattr(i,"price",0)),currency=getattr(i,"currency","EUR"),brand=getattr(i,"brand_title",None),size=getattr(i,"size_title",None),url=f"https://www.vinted.com/items/{i.id}",image_url=getattr(i,"photo",None),search_query=q.url))
            db.add(PriceHistory(vinted_id=str(i.id),price=float(getattr(i,"price",0))));nc+=1
        q.last_run=datetime.utcnow();await db.commit()
        return{"new_items":nc,"total_found":len(items) if isinstance(items,list) else 0}
    except Exception as e:return JSONResponse(500,{"error":str(e)})
if __name__=="__main__":
    import uvicorn;uvicorn.run(app,host="0.0.0.0",port=8080)
EOF
cat > /opt/vinted-panel/frontend/css/style.css << 'EOF'
:root{--bg:#0f0f13;--bg2:#1a1a24;--card:#222230;--hov:#2a2a3a;--acc:#7c5cff;--glow:rgba(124,92,255,.3);--t1:#e8e8f0;--t2:#9090a8;--t3:#606078;--brd:#2e2e40;--ok:#34d399;--wrn:#fbbf24;--err:#f87171;--grd:linear-gradient(135deg,#7c5cff,#5b8def)}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:var(--bg);color:var(--t1);min-height:100vh;-webkit-font-smoothing:antialiased}
.sidebar{position:fixed;top:0;left:0;width:260px;height:100vh;background:var(--bg2);border-right:1px solid var(--brd);display:flex;flex-direction:column;z-index:100;transition:transform .3s}
.sidebar-header{padding:24px 20px;border-bottom:1px solid var(--brd)}
.sidebar-header h1{font-size:18px;font-weight:700;background:var(--grd);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.sidebar-header p{font-size:12px;color:var(--t3);margin-top:4px}
.nav{flex:1;padding:12px 0}
.nav-item{display:flex;align-items:center;gap:12px;padding:12px 20px;cursor:pointer;transition:all .2s;color:var(--t2);font-size:14px;font-weight:500;border-left:3px solid transparent}
.nav-item:hover{background:var(--hov);color:var(--t1)}
.nav-item.active{color:var(--acc);border-left-color:var(--acc);background:rgba(124,92,255,.08)}
.nav-item svg{width:20px;height:20px;opacity:.7}
.nav-item.active svg{opacity:1}
.main{margin-left:260px;padding:24px;min-height:100vh}
.page{display:none}.page.active{display:block}
.page-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:24px;flex-wrap:wrap;gap:12px}
.page-header h2{font-size:24px;font-weight:700}
.stats-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:16px;margin-bottom:24px}
.stat-card{background:var(--card);border-radius:12px;padding:20px;border:1px solid var(--brd);transition:transform .2s,box-shadow .2s}
.stat-card:hover{transform:translateY(-2px);box-shadow:0 8px 24px rgba(0,0,0,.3)}
.stat-card .label{font-size:12px;color:var(--t3);text-transform:uppercase;letter-spacing:1px}
.stat-card .value{font-size:28px;font-weight:700;margin-top:8px}
.stat-card .value.accent{color:var(--acc)}.stat-card .value.green{color:var(--ok)}.stat-card .value.yellow{color:var(--wrn)}
.items-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:16px}
.item-card{background:var(--card);border-radius:12px;overflow:hidden;border:1px solid var(--brd);transition:transform .2s,box-shadow .2s;cursor:pointer;text-decoration:none;color:inherit}
.item-card:hover{transform:translateY(-3px);box-shadow:0 12px 32px rgba(0,0,0,.4)}
.item-card .image-wrap{width:100%;height:200px;background:var(--bg);display:flex;align-items:center;justify-content:center;overflow:hidden}
.item-card .image-wrap img{width:100%;height:100%;object-fit:cover}
.item-card .info{padding:16px}
.item-card .title{font-size:14px;font-weight:600;line-height:1.4;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.item-card .meta{display:flex;justify-content:space-between;align-items:center;margin-top:12px}
.item-card .price{font-size:18px;font-weight:700;color:var(--acc)}
.item-card .details{display:flex;gap:8px;flex-wrap:wrap;margin-top:8px}
.tag{font-size:11px;padding:3px 8px;border-radius:6px;background:rgba(124,92,255,.12);color:var(--acc)}
.tag.brand{background:rgba(52,211,153,.12);color:var(--ok)}.tag.size{background:rgba(251,191,36,.12);color:var(--wrn)}
.search-bar{display:flex;gap:12px;margin-bottom:24px;flex-wrap:wrap}
.search-input{flex:1;min-width:200px;padding:12px 16px;background:var(--card);border:1px solid var(--brd);border-radius:10px;color:var(--t1);font-size:14px;outline:none;transition:border-color .2s}
.search-input:focus{border-color:var(--acc)}.search-input::placeholder{color:var(--t3)}
.btn{padding:10px 20px;border-radius:10px;border:none;font-size:14px;font-weight:600;cursor:pointer;transition:all .2s;display:inline-flex;align-items:center;gap:8px}
.btn-primary{background:var(--grd);color:#fff;box-shadow:0 4px 12px var(--glow)}
.btn-primary:hover{transform:translateY(-1px)}.btn-secondary{background:var(--card);color:var(--t2);border:1px solid var(--brd)}
.btn-secondary:hover{background:var(--hov);color:var(--t1)}.btn-danger{background:rgba(248,113,113,.15);color:var(--err)}
.btn-danger:hover{background:rgba(248,113,113,.25)}.btn-sm{padding:6px 12px;font-size:12px;border-radius:8px}
.table-wrap{background:var(--card);border-radius:12px;border:1px solid var(--brd);overflow-x:auto}
table{width:100%;border-collapse:collapse}
th{padding:14px 16px;text-align:left;font-size:12px;color:var(--t3);text-transform:uppercase;letter-spacing:1px;border-bottom:1px solid var(--brd);background:var(--bg2)}
td{padding:12px 16px;border-bottom:1px solid var(--brd);font-size:14px}tr:hover td{background:var(--hov)}
.status-active{color:var(--ok)}.status-inactive{color:var(--err)}
.brand-bars{display:flex;flex-direction:column;gap:8px}
.brand-bar{display:flex;align-items:center;gap:12px;font-size:13px}
.brand-bar .name{width:140px;text-align:right;color:var(--t2);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.brand-bar .bar{flex:1;height:24px;background:var(--bg);border-radius:6px;overflow:hidden}
.brand-bar .bar-fill{height:100%;border-radius:6px;background:var(--grd);transition:width .5s;display:flex;align-items:center;padding-left:8px}
.brand-bar .count{font-weight:600;font-size:12px;color:#fff;min-width:30px}
.modal-overlay{display:none;position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,.7);z-index:200;align-items:center;justify-content:center;backdrop-filter:blur(4px)}
.modal-overlay.active{display:flex}
.modal{background:var(--bg2);border-radius:16px;padding:28px;width:90%;max-width:500px;border:1px solid var(--brd);box-shadow:0 24px 64px rgba(0,0,0,.5)}
.modal h3{font-size:18px;margin-bottom:20px}
.form-group{margin-bottom:16px}
.form-group label{display:block;font-size:12px;color:var(--t3);text-transform:uppercase;letter-spacing:1px;margin-bottom:6px}
.form-group input,.form-group select{width:100%;padding:10px 14px;background:var(--card);border:1px solid var(--brd);border-radius:8px;color:var(--t1);font-size:14px;outline:none}
.form-group input:focus{border-color:var(--acc)}
.modal-actions{display:flex;gap:12px;justify-content:flex-end;margin-top:24px}
.chart-container{background:var(--card);border-radius:12px;padding:20px;border:1px solid var(--brd);margin-bottom:24px}
.chart-container h3{font-size:14px;color:var(--t2);margin-bottom:16px}
.chart-canvas{width:100%;height:200px}
.empty-state{text-align:center;padding:60px 20px;color:var(--t3)}
.toast{position:fixed;bottom:24px;right:24px;padding:14px 20px;background:var(--card);border:1px solid var(--brd);border-radius:10px;font-size:14px;z-index:300;transform:translateY(100px);opacity:0;transition:all .3s;box-shadow:0 8px 24px rgba(0,0,0,.4)}
.toast.show{transform:translateY(0);opacity:1}.toast.success{border-color:var(--ok)}.toast.error{border-color:var(--err)}
.hamburger{display:none;position:fixed;top:16px;left:16px;z-index:150;background:var(--card);border:1px solid var(--brd);border-radius:8px;padding:8px;cursor:pointer;color:var(--t1)}
@media(max-width:768px){.sidebar{transform:translateX(-100%);width:280px}.sidebar.open{transform:translateX(0)}.main{margin-left:0;padding:16px;padding-top:56px}.hamburger{display:block}.stats-grid{grid-template-columns:repeat(2,1fr)}.items-grid{grid-template-columns:1fr}}
EOF
cat > /opt/vinted-panel/frontend/js/app.js << 'EOF'
const API='';let currentPage=1,totalPages=1,searchTimer=null
function showPage(n){document.querySelectorAll('.page').forEach(p=>p.classList.remove('active'));document.querySelectorAll('.nav-item').forEach(v=>v.classList.remove('active'));document.getElementById('page-'+n).classList.add('active');event.currentTarget.classList.add('active');if(innerWidth<768)toggleSidebar();if(n==='dashboard')loadDashboard();if(n==='items'){currentPage=1;loadItems()}if(n==='queries')loadQueries();if(n==='analysis')loadAnalysis()}
function toggleSidebar(){document.getElementById('sidebar').classList.toggle('open')}
async function loadDashboard(){try{const[s,t,b]=await Promise.all([fetch('/api/stats'),fetch('/api/price-trends'),fetch('/api/brand-analysis')]);renderStats(await s.json());renderTrendChart((await t.json()).trends);renderBrandBars((await b.json()).brands.slice(0,8))}catch(e){}}
function renderStats(s){document.getElementById('stats-grid').innerHTML=`<div class="stat-card"><div class="label">Przedmioty</div><div class="value accent">${s.total_items.toLocaleString()}</div></div><div class="stat-card"><div class="label">Śr. cena</div><div class="value green">${s.avg_price}€</div></div><div class="stat-card"><div class="label">Min</div><div class="value yellow">${s.min_price}€</div></div><div class="stat-card"><div class="label">Max</div><div class="value">${s.max_price}€</div></div><div class="stat-card"><div class="label">Aktywne</div><div class="value accent">${s.active_queries}</div></div><div class="stat-card"><div class="label">Wszystkie</div><div class="value">${s.total_queries}</div></div>`}
function renderTrendChart(t){const c=document.getElementById('trend-chart'),x=c.getContext('2d');c.width=c.offsetWidth*2;c.height=400;x.scale(2,2);const w=c.offsetWidth,h=200,p={top:20,right:20,bottom:40,left:60};x.clearRect(0,0,w,h);if(!t||!t.length){x.fillStyle='#606078';x.font='14px sans-serif';x.textAlign='center';x.fillText('Brak danych',w/2,h/2);return}const pr=t.map(v=>v.avg_price),ct=t.map(v=>v.count),mx=Math.max(...pr)*1.1,mn=Math.min(...pr)*.9,mc=Math.max(...ct)*1.1,cW=w-p.left-p.right,cH=h-p.top-p.bottom;x.strokeStyle='#2e2e40';x.lineWidth=.5;for(let i=0;i<=4;i++){const y=p.top+cH/4*i;x.beginPath();x.moveTo(p.left,y);x.lineTo(w-p.right,y);x.stroke();x.fillStyle='#606078';x.font='11px sans-serif';x.textAlign='right';x.fillText((mx-(mx-mn)*(i/4)).toFixed(0)+'€',p.left-8,y+4)}const bw=cW/t.length*.6;t.forEach((v,i)=>{const bx=p.left+cW/(t.length-1||1)*i-bw/2,bh=v.count/mc*cH;x.fillStyle='rgba(124,92,255,.15)';x.fillRect(bx,p.top+cH-bh,bw,bh)});x.beginPath();x.strokeStyle='#7c5cff';x.lineWidth=2;t.forEach((v,i)=>{const bx=p.left+cW/(t.length-1||1)*i,by=p.top+cH-((v.avg_price-mn)/(mx-mn))*cH;i?x.lineTo(bx,by):x.moveTo(bx,by)});x.stroke();t.forEach((v,i)=>{const bx=p.left+cW/(t.length-1||1)*i,by=p.top+cH-((v.avg_price-mn)/(mx-mn))*cH;x.beginPath();x.arc(bx,by,3,0,Math.PI*2);x.fillStyle='#7c5cff';x.fill()});x.fillStyle='#606078';x.font='10px sans-serif';x.textAlign='center';const step=Math.max(1,~~(t.length/8));t.forEach((v,i)=>{if(i%step===0||i===t.length-1){x.fillText(v.date.slice(5),p.left+cW/(t.length-1||1)*i,h-p.bottom+20)}})}
function renderBrandBars(b){const c=document.getElementById('brand-bars');if(!b.length){c.innerHTML='<div class="empty-state"><p>Brak danych</p></div>';return}const mx=Math.max(...b.map(v=>v.count));c.innerHTML=b.map(v=>`<div class="brand-bar"><span class="name">${v.brand}</span><div class="bar"><div class="bar-fill" style="width:${(v.count/mx*100).toFixed(1)}%"><span class="count">${v.count}</span></div></div><span style="min-width:50px;text-align:right;color:var(--acc);font-weight:600">${v.avg_price}€</span></div>`).join('')}
async function loadItems(reset=true){if(reset)currentPage=1;const s=document.getElementById('item-search').value,so=document.getElementById('item-sort').value;try{const r=await fetch(`/api/items?search=${encodeURIComponent(s)}&sort=${so}&page=${currentPage}&per_page=24`),d=await r.json();totalPages=d.pages;const g=document.getElementById('items-grid');if(reset)g.innerHTML='';if(!d.items.length&&reset){g.innerHTML='<div class="empty-state"><p>Brak przedmiotów. Dodaj wyszukiwanie i uruchom fetch.</p></div>';document.getElementById('load-more-btn').style.display='none';return}g.innerHTML+=d.items.map(i=>`<a class="item-card" href="${i.url}" target="_blank"><div class="image-wrap">${i.image_url?`<img src="${i.image_url}" loading="lazy">`:'<div style="color:var(--t3)">📷</div>'}</div><div class="info"><div class="title">${i.title||'-'}</div><div class="meta"><span class="price">${i.price} ${i.currency||'€'}</span></div><div class="details">${i.brand?`<span class="tag brand">${i.brand}</span>`:''}${i.size?`<span class="tag size">${i.size}</span>`:''}</div></div></a>`).join('');document.getElementById('load-more-btn').style.display=currentPage<totalPages?'inline-flex':'none'}catch(e){}}
function loadMore(){currentPage++;loadItems(false)}
function debounceSearch(){clearTimeout(searchTimer);searchTimer=setTimeout(()=>loadItems(),400)}
async function loadQueries(){try{const d=await(await fetch('/api/queries')).json(),t=document.getElementById('queries-table');if(!d.queries.length){t.innerHTML='<tr><td colspan="6" style="text-align:center;padding:40px;color:var(--t3)">Brak wyszukiwań</td></tr>';return}t.innerHTML=d.queries.map(q=>`<tr><td><strong>${q.name}</strong></td><td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:12px;color:var(--t3)">${q.url}</td><td><span class="${q.is_active?'status-active':'status-inactive'}">${q.is_active?'● Aktywne':'● Off'}</span></td><td>${q.interval_minutes}m</td><td>${q.last_run?new Date(q.last_run).toLocaleString('pl-PL'):'-'}</td><td><div style="display:flex;gap:6px"><button class="btn btn-primary btn-sm" onclick="fetchNow(${q.id})">⚡</button><button class="btn btn-secondary btn-sm" onclick="toggleQuery(${q.id})">🔄</button><button class="btn btn-danger btn-sm" onclick="deleteQuery(${q.id})">✕</button></div></td></tr>`).join('')}catch(e){}}
function showAddQueryModal(){document.getElementById('add-query-modal').classList.add('active')}
function closeModal(){document.getElementById('add-query-modal').classList.remove('active')}
async function addQuery(){const n=document.getElementById('q-name').value.trim(),u=document.getElementById('q-url').value.trim(),i=document.getElementById('q-interval').value;if(!n||!u){showToast('Wypełnij pola','error');return}try{const r=await fetch(`/api/queries?name=${encodeURIComponent(n)}&url=${encodeURIComponent(u)}&interval=${i}`,{method:'POST'});r.ok?(showToast('Dodano!'),closeModal(),loadQueries()):showToast((await r.json()).detail,'error')}catch(e){showToast('Błąd','error')}}
async function fetchNow(id){showToast('Pobieranie...');try{const d=await(await fetch(`/api/fetch/${id}`,{method:'POST'})).json();d.error?showToast(d.error,'error'):(showToast(`+${d.new_items}/${d.total_found}`),loadQueries())}catch(e){showToast('Błąd','error')}}
async function toggleQuery(id){await fetch(`/api/queries/${id}/toggle`,{method:'POST'});loadQueries()}
async function deleteQuery(id){if(!confirm('Usunąć?'))return;await fetch(`/api/queries/${id}`,{method:'DELETE'});showToast('Usunięto');loadQueries()}
async function loadAnalysis(){try{const d=await(await fetch('/api/brand-analysis')).json(),t=document.getElementById('brand-table');if(!d.brands.length){t.innerHTML='<tr><td colspan="5" style="text-align:center;padding:40px;color:var(--t3)">Brak danych</td></tr>';return}t.innerHTML=d.brands.map(b=>`<tr><td><strong>${b.brand}</strong></td><td>${b.count}</td><td style="color:var(--acc);font-weight:600">${b.avg_price}€</td><td style="color:var(--ok)">${b.min_price}€</td><td style="color:var(--wrn)">${b.max_price}€</td></tr>`).join('')}catch(e){}}
function showToast(m,t='success'){const e=document.getElementById('toast');e.textContent=m;e.className=`toast ${t} show`;setTimeout(()=>e.classList.remove('show'),3000)}
loadDashboard()
EOF
cat > /opt/vinted-panel/frontend/index.html << 'EOF'
<!DOCTYPE html><html lang="pl"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1,user-scalable=no"><meta name="theme-color" content="#0f0f13"><meta name="apple-mobile-web-app-capable" content="yes"><title>Vinted Panel</title><link rel="stylesheet" href="/static/css/style.css"></head><body>
<button class="hamburger" onclick="toggleSidebar()">☰</button>
<aside class="sidebar" id="sidebar"><div class="sidebar-header"><h1>📊 Vinted Panel</h1><p>Market Analysis</p></div><nav class="nav"><div class="nav-item active" onclick="showPage('dashboard')">📊 Dashboard</div><div class="nav-item" onclick="showPage('items')">📦 Przedmioty</div><div class="nav-item" onclick="showPage('queries')">🔍 Wyszukiwania</div><div class="nav-item" onclick="showPage('analysis')">📈 Analiza</div></nav></aside>
<main class="main">
<div class="page active" id="page-dashboard"><div class="page-header"><h2>Dashboard</h2></div><div class="stats-grid" id="stats-grid"></div><div class="chart-container"><h3>Trend cenowy (30 dni)</h3><canvas class="chart-canvas" id="trend-chart"></canvas></div><h3 style="margin-bottom:16px;color:var(--t2)">Top Marki</h3><div id="brand-bars" class="brand-bars"></div></div>
<div class="page" id="page-items"><div class="page-header"><h2>Przedmioty</h2></div><div class="search-bar"><input class="search-input" id="item-search" placeholder="Szukaj..." oninput="debounceSearch()"><select class="search-input" style="max-width:180px" id="item-sort" onchange="loadItems()"><option value="newest">Najnowsze</option><option value="price_asc">Cena ↑</option><option value="price_desc">Cena ↓</option></select></div><div class="items-grid" id="items-grid"></div><div style="text-align:center;margin-top:24px"><button class="btn btn-secondary" id="load-more-btn" onclick="loadMore()" style="display:none">Więcej</button></div></div>
<div class="page" id="page-queries"><div class="page-header"><h2>Wyszukiwania</h2><button class="btn btn-primary" onclick="showAddQueryModal()">+ Nowe</button></div><div class="table-wrap"><table><thead><tr><th>Nazwa</th><th>URL</th><th>Status</th><th>Co</th><th>Kiedy</th><th></th></tr></thead><tbody id="queries-table"></tbody></table></div></div>
<div class="page" id="page-analysis"><div class="page-header"><h2>Analiza Marek</h2></div><div class="table-wrap"><table><thead><tr><th>Marka</th><th>Ilość</th><th>Śr.</th><th>Min</th><th>Max</th></tr></thead><tbody id="brand-table"></tbody></table></div></div>
</main>
<div class="modal-overlay" id="add-query-modal"><div class="modal"><h3>+ Wyszukiwanie</h3><div class="form-group"><label>Nazwa</label><input id="q-name" placeholder="Nike Air Force"></div><div class="form-group"><label>URL Vinted</label><input id="q-url" placeholder="https://www.vinted.fr/catalog?search_text=nike"></div><div class="form-group"><label>Interwał (min)</label><input id="q-interval" type="number" value="30" min="5"></div><div class="modal-actions"><button class="btn btn-secondary" onclick="closeModal()">Anuluj</button><button class="btn btn-primary" onclick="addQuery()">Dodaj</button></div></div></div>
<div class="toast" id="toast"></div>
<script src="/static/js/app.js"></script></body></html>
EOF
cat > /opt/vinted-panel/frontend/manifest.json << 'EOF'
{"name":"Vinted Panel","short_name":"VP","start_url":"/","display":"standalone","background_color":"#0f0f13","theme_color":"#0f0f13"}
EOF
cat > /opt/vinted-panel/Dockerfile << 'EOF'
FROM python:3.11-slim
WORKDIR /app
RUN apt-get update&&apt-get install -y --no-install-recommends gcc curl&&rm -rf /var/lib/apt/lists/*
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./backend/
COPY frontend/ ./frontend/
RUN mkdir -p /app/data
EXPOSE 8080
CMD ["uvicorn","backend.main:app","--host","0.0.0.0","--port","8080"]
EOF
cat > /opt/vinted-panel/docker-compose.yml << 'EOF'
version: '3.8'
services:
  vinted-panel:
    build: .
    container_name: vinted-panel
    ports: ["8080:8080"]
    volumes: [vinted-data:/app/data]
    restart: unless-stopped
volumes:
  vinted-data:
EOF
cd /opt/vinted-panel&&docker compose build -q&&docker compose up -d
ufw allow 8080/tcp 2>/dev/null||true
IP=$(hostname -I|awk '{print $1}')
echo "";echo "✅ GOTOWE! Otwórz: http://$IP:8080"
