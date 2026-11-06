import os

from fastapi import FastAPI, HTTPException
from sqlalchemy import text
from app.database import Base, engine
import app.models
from app.routers.auth import router as auth_router
from app.routers.documents import router as documents_router
from app.routers.permissions import router as permissions_router
from app.routers.audit import router as audit_router
from app.routers.admin import router as admin_router
from fastapi.middleware.cors import CORSMiddleware

Base.metadata.create_all(bind=engine)
    
app = FastAPI(
    title="TrustVault API",
    description="Secure Document Sharing Platform",
    version="1.0.0"
)
cors_origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://localhost:5174,"
        "http://127.0.0.1:5173,http://127.0.0.1:5174"
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth_router)
app.include_router(documents_router)
app.include_router(permissions_router)
app.include_router(audit_router)
app.include_router(admin_router)

@app.get("/")
def home():
    return {
        "message": "Welcome to TrustVault",
        "status": "Running"
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "application": "TrustVault"
    }

@app.get("/db-health")
def database_health():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

        return {
            "database": "PostgreSQL",
            "status": "Connected"
        }

    except Exception as e:
        print("\nDATABASE ERROR:", repr(e))

        raise HTTPException(
            status_code=503,
            detail="Database connection failed"
        )