from fastapi import APIRouter, HTTPException, Header
from typing import Optional
from app.models.incident import AnalyzeRequest, AnalyzeResponse
from app.services.analyzer import IncidentAnalyzer
import logging

router = APIRouter(prefix="/api/v1", tags=["analyze"])
logger = logging.getLogger(__name__)
analyzer = IncidentAnalyzer()

@router.post("/analyze", response_model=AnalyzeResponse, summary="Analisa um incidente completo")
async def analyze_incident(
    req: AnalyzeRequest,
    x_caller_id: Optional[str] = Header(None),   # Fury-injected
    x_user_email: Optional[str] = Header(None),
):
    """
    Analisa um incidente crítico consultando:
    - Jira (ticket + correlatos)
    - Confluence ISSM (documentação)
    - Drive (gravações + transcrições)
    - Slack (canal do incidente)
    - Datadog (bitácora IR)

    Retorna relatório gerencial completo em Markdown e HTML.
    """
    if x_user_email:
        req.user_email = x_user_email

    ticket = req.ticket.strip()
    if not ticket:
        raise HTTPException(status_code=400, detail="ticket é obrigatório")

    logger.info(f"[{x_caller_id or 'direct'}] Analisando: {ticket}")

    try:
        result = await analyzer.analyze(req)
        return result
    except Exception as e:
        logger.error(f"Analyze error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analyze/{ticket}", summary="Analisa via GET (conveniência)")
async def analyze_get(ticket: str, save_to_grid: bool = True, save_to_drive: bool = True):
    req = AnalyzeRequest(ticket=ticket, save_to_grid=save_to_grid, save_to_drive=save_to_drive)
    return await analyze_incident(req)


@router.get("/health")
async def health():
    return {"status": "ok", "service": "natis-incident-api", "version": "1.0.0"}
