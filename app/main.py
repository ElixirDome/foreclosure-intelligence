
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import engine
from app.models import Base
from app.routes.auth import router as auth_router
from app.routes.properties import router as properties_router
from app.routes.documents import router as documents_router
from app.routes.intelligence import router as intelligence_router
from app.ingestion.scheduler import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Background ingestion is a production concern.
    # Do not start it when the application is being tested.
    import sys

    running_under_pytest = "pytest" in sys.modules

    if not running_under_pytest:
        start_scheduler()

    yield

    if not running_under_pytest:
        stop_scheduler()


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

app.include_router(properties_router)
app.include_router(auth_router)
app.include_router(documents_router)
app.include_router(intelligence_router)


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
        },
    }


