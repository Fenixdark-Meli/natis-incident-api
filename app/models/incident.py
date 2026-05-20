from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

class Severity(str, Enum):
    SEV1 = "SEV-1"
    SEV2 = "SEV-2"
    SEV3 = "SEV-3"
    SEV4 = "SEV-4"
    SEV5 = "SEV-5"
    UNKNOWN = "DESCONHECIDA"

class IncidentStatus(str, Enum):
    OPEN = "ABERTO"
    RESOLVED = "NORMALIZADO"
    INVESTIGATING = "INVESTIGANDO"
    UNKNOWN = "DESCONHECIDO"

class SourceData(BaseModel):
    jira: Optional[Dict[str, Any]] = None
    confluence: Optional[Dict[str, Any]] = None
    drive: Optional[Dict[str, Any]] = None
    slack: Optional[Dict[str, Any]] = None
    datadog: Optional[Dict[str, Any]] = None
    errors: List[str] = Field(default_factory=list)

class AnalyzeRequest(BaseModel):
    ticket: str = Field(..., description="SSHP-XXXXXX, IR-XXXXX ou CI-XXXXX")
    user_email: Optional[str] = "danillo.ferreira@mercadolivre.com"
    save_to_drive: bool = True
    save_to_grid: bool = True
    language: str = "pt-BR"

class AnalyzeResponse(BaseModel):
    ticket: str
    status: str = "success"
    report: str
    report_html: str
    sources_consulted: List[str]
    grid_url: Optional[str] = None
    drive_url: Optional[str] = None
    generated_at: str
    duration_seconds: float
    metadata: Dict[str, Any] = Field(default_factory=dict)
