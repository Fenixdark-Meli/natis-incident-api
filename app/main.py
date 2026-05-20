from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes.analyze import router
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s — %(message)s")

app = FastAPI(
    title="NATIS Incident Analyzer",
    description="API para análise automática de incidentes críticos · IS Shipping Brasil · Mercado Livre",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://grid.adminml.com", "https://*.melioffice.com", "https://*.adminml.com"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(router)

@app.get("/ping")
async def ping():
    return "pong"

@app.get("/")
async def root():
    return {
        "service": "natis-incident-api",
        "version": "1.0.0",
        "description": "NATIS Incident Analyzer · IS Shipping Brasil",
        "endpoints": {
            "POST /api/v1/analyze": "Análise completa de incidente",
            "GET /api/v1/analyze/{ticket}": "Análise via GET",
            "GET /api/v1/health": "Health check",
            "GET /docs": "Swagger UI",
        }
    }
