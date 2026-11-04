
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import engine
from app.models import Base
from app.routes.auth import router as auth_router
from app.routes.properties import router as properties_router
from app.routes.documents import router as documents_router
from app.routes.intelligence import router as intelligence_router
from app.routes.sources import router as sources_router
from app.ingestion.scheduler import start_scheduler, stop_scheduler
from app.middleware.rate_limit import RateLimitMiddleware, default_rate_limiter


@asynccontextmanager
async def lifespan(app: FastAPI):
    import asyncio
    from app.services.live_events import broker
    broker.set_loop(asyncio.get_running_loop())

    # Background ingestion is a production concern.
    # Do not start it when the application is being tested.
    import sys

    running_under_pytest = "pytest" in sys.modules

    if not running_under_pytest:
        start_scheduler()

    yield

    if not running_under_pytest:
        stop_scheduler()
       # How this applies to your Lifespan code:
# Think of FastAPI as a manager running a restaurant:

# FastAPI calls your lifespan function to open the restaurant.

# Your code sets up the database and scheduler.

# It hits yield. At this exact moment, your function says: "Alright, startup tasks are done. I'm going to take a nap here. FastAPI, you go run the restaurant web server."

# FastAPI runs the server for hours or days.

# When you press Ctrl+C to shut down, FastAPI wakes up your paused function right at that yield line, and says: "Okay, time to close up shop!" Then it runs the rest of the code (stop_scheduler()).

# So yield is triggered normally by the flow of execution, but it acts like a checkpoint or pause button rather than an exit door.


Base.metadata.create_all(engine)

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RateLimitMiddleware)

app.include_router(properties_router)
app.include_router(auth_router)
app.include_router(documents_router)
app.include_router(intelligence_router)
app.include_router(sources_router)


@app.get("/")
def root():
    return {
        "message": "Foreclosure Intelligence API",
        "architecture": "document-centric RAG",
        "endpoints": {
            "documents": "/documents",
            "retrieve": "/documents/retrieve",
            "rag": "/documents/rag",
            "extract": "/documents/{id}/extract",
            "deal": "/properties/{id}/deal",
            "evidence": "/properties/{id}/evidence",
            "health_live": "/health/live",
            "health_ready": "/health/ready",
        },
    }


@app.get("/health/live", tags=["health"])
def health_live():
    return {"status": "live"}


@app.get("/health/ready", tags=["health"])
def health_ready():
    from fastapi import HTTPException
    from sqlalchemy import text

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ready", "database": "connected"}
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Database connection failed: {exc}",
        )


@app.get("/system/metrics", tags=["system"])
def get_system_metrics():
    from app.services.cache import cache
    return {
        "status": "operational",
        "cache": cache.get_stats(),
        "rate_limiter": default_rate_limiter.get_stats(),
    }




