import asyncio
import time
import logging
from typing import Dict, Any, List, Optional
from app.config import settings
from app.models.incident import AnalyzeRequest, AnalyzeResponse, SourceData
from app.services.sources.jira_client import JiraClient
from app.services.sources.confluence_client import ConfluenceClient
from app.services.sources.datadog_client import DatadogClient
from app.services.sources.drive_client import DriveClient
from app.services.sources.slack_client import SlackClient
from app.services.report_generator import ReportGenerator
from app.services.grid_client import GridClient
from app.services.transcription_service import TranscriptionService

logger = logging.getLogger(__name__)


class IncidentAnalyzer:
    def __init__(self):
        self.jira = JiraClient()
        self.confluence = ConfluenceClient()
        self.datadog = DatadogClient()
        self.drive = DriveClient()
        self.slack = SlackClient()
        self.report_gen = ReportGenerator()
        self.grid = GridClient()
        self.transcription = TranscriptionService()

    async def analyze(self, req: AnalyzeRequest) -> AnalyzeResponse:
        start = time.time()
        ticket = req.ticket.strip().upper()
        logger.info(f"[NATIS] Analisando: {ticket}")

        # 1. Busca dados em paralelo
        sources, sources_consulted = await self._gather_sources(ticket)

        # 2. Tenta transcrever gravação se encontrada
        transcription = await self._get_transcription(sources)

        # 3. Gera relatório
        report_md = await self.report_gen.generate(
            ticket, sources, req.language, transcription
        )
        report_html = self._md_to_html(report_md, ticket)

        # 4. Salva
        grid_url, drive_url = None, None
        tasks = []
        if req.save_to_drive:
            tasks.append(self.drive.save_report(ticket, report_md))
        if req.save_to_grid:
            tasks.append(self.grid.upload(ticket, report_html, req.user_email))

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            idx = 0
            if req.save_to_drive:
                drive_url = results[idx] if not isinstance(results[idx], Exception) else None
                idx += 1
            if req.save_to_grid:
                grid_url = results[idx] if not isinstance(results[idx], Exception) else None

        duration = round(time.time() - start, 2)
        logger.info(f"[NATIS] Concluído: {ticket} em {duration}s")

        return AnalyzeResponse(
            ticket=ticket, status="success",
            report=report_md, report_html=report_html,
            sources_consulted=sources_consulted,
            grid_url=grid_url, drive_url=drive_url,
            generated_at=__import__('datetime').datetime.utcnow().isoformat() + "Z",
            duration_seconds=duration,
            metadata={
                "sources_found": len([s for s in sources_consulted if "✅" in s]),
                "has_transcription": transcription is not None,
                "report_length": len(report_md)
            }
        )

    async def _get_transcription(self, sources: SourceData) -> Optional[str]:
        """Tenta transcrever gravação do war room"""
        if not sources.drive:
            return None
        recordings = sources.drive.get("recordings", [])
        for f in recordings:
            name = f.get("name", "").lower()
            if any(ext in name for ext in [".mp4", ".mp3", ".webm", ".m4a"]):
                logger.info(f"Transcrevendo: {f.get('name')}")
                result = await self.transcription.transcribe_from_drive(f.get("id", ""))
                if result:
                    return result
        return None

    async def _gather_sources(self, ticket: str):
        num = ''.join(filter(str.isdigit, ticket))
        sshp = f"SSHP-{num}" if num else ticket

        tasks = [
            self.jira.get_issue(sshp),
            self.jira.search_related(num),
            self.confluence.search(num),
            self.confluence.search(sshp),
            self.datadog.search_incidents(num),
            self.drive.search(num),
            self.drive.search(num, settings.DRIVE_NATIS_FOLDER),
            self.slack.search(sshp),
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        def safe(r, name):
            if isinstance(r, Exception):
                return None, f"❌ {name}: {str(r)[:50]}"
            return r, f"✅ {name}"

        ji, s0 = safe(results[0], "Jira · ticket")
        jr, s1 = safe(results[1], "Jira · correlatos")
        cf1, s2 = safe(results[2], "Confluence ISSM")
        cf2, s3 = safe(results[3], "Confluence correlato")
        dd, s4 = safe(results[4], "Datadog")
        dr1, s5 = safe(results[5], "Drive gravações")
        dr2, s6 = safe(results[6], "Drive NATIS")
        sl, s7 = safe(results[7], "Slack")

        sources = SourceData(
            jira={"issue": ji, "related": jr or []},
            confluence={"pages": (cf1 or []) + (cf2 or [])},
            datadog={"incidents": dd or []},
            drive={"recordings": dr1 or [], "natis": dr2 or []},
            slack={"messages": sl or []}
        )
        return sources, [s0, s1, s2, s3, s4, s5, s6, s7]

    def _md_to_html(self, md: str, ticket: str) -> str:
        import re, datetime
        h = md.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        h = re.sub(r'^## (.+)$', r'<h2>\1</h2>', h, flags=re.M)
        h = re.sub(r'^### (.+)$', r'<h3>\1</h3>', h, flags=re.M)
        h = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', h)
        h = re.sub(r'^[\-\*] (.+)$', r'<li>\1</li>', h, flags=re.M)
        h = re.sub(r'^\|(.+)\|$', lambda m: '<tr>' + ''.join(f'<td>{c.strip()}</td>' for c in m.group(1).split('|')) + '</tr>', h, flags=re.M)
        h = re.sub(r'^---$', '<hr/>', h, flags=re.M)
        return f"""<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="UTF-8"/>
<title>NATIS · {ticket}</title>
<style>
:root{{--yellow:#FFE600;--dark:#1a1a2e;--gray:#f5f5f5;}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;max-width:1000px;margin:0 auto;padding:24px;color:var(--dark);line-height:1.7;background:#fff;}}
.hdr{{background:var(--yellow);padding:16px 24px;border-radius:10px;margin-bottom:28px;display:flex;justify-content:space-between;align-items:center;}}
.hdr h1{{font-size:18px;margin:0;}}
.hdr small{{font-size:12px;color:#555;}}
h2{{border-bottom:3px solid var(--yellow);padding-bottom:6px;margin:28px 0 12px;font-size:16px;}}
h3{{color:#333;margin:16px 0 6px;font-size:14px;}}
li{{margin:4px 0;}}
table{{width:100%;border-collapse:collapse;margin:10px 0;}}
th{{background:var(--dark);color:#fff;padding:8px 12px;text-align:left;font-size:12px;}}
td{{padding:7px 12px;border-bottom:1px solid #eee;font-size:13px;}}
tr:hover td{{background:var(--gray);}}
blockquote{{border-left:4px solid var(--yellow);padding:8px 14px;background:#fffce0;margin:10px 0;border-radius:0 6px 6px 0;font-style:italic;}}
.footer{{margin-top:40px;padding:16px 24px;border-top:3px solid var(--yellow);font-size:11px;color:#666;display:flex;justify-content:space-between;}}
@media(max-width:600px){{body{{padding:12px;}}}}
</style></head><body>
<div class="hdr">
  <div>
    <h1>⚙ NATIS · Relatório de Incidente · {ticket}</h1>
    <small>IS Shipping Brasil · Mercado Livre · {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}</small>
  </div>
</div>
<div>{h}</div>
<div class="footer">
  <span>Gerado por NATIS Incident Analyzer · IS Shipping Brasil</span>
  <span>{datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}</span>
</div>
</body></html>"""
