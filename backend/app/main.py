from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
from app.routers import stocks, market, quant, ai, admin
from app.database import Base, engine
from app.config import settings

app = FastAPI(title="X2Stock API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(stocks.router)
app.include_router(market.router)
app.include_router(quant.router)
app.include_router(ai.router)
app.include_router(admin.router)

frontend_dist = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist")
if os.path.exists(frontend_dist):
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")

@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)
    if settings.SCHEDULER_ENABLED:
        from app.scheduler import start_scheduler
        start_scheduler()

@app.get("/api/health")
def health():
    return dict(status="ok", version="0.1.0")
