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

    async def analyze(self, req: AnalyzeRequest) -> AnalyzeResponse:
        start = time.time()
        ticket = req.ticket.strip().upper()
        logger.info(f"[NATIS] Iniciando análise: {ticket}")

        # ── Coleta dados de todas as fontes em paralelo ──
        sources, sources_consulted = await self._gather_sources(ticket)

        # ── Gera relatório via GenAI ──
        report_md = await self.report_gen.generate(ticket, sources, req.language)
        report_html = self._md_to_html(report_md, ticket)

        # ── Salva no Drive e Grid ──
        grid_url, drive_url = None, None
        save_tasks = []

        if req.save_to_drive:
            save_tasks.append(self.drive.save_report(ticket, report_md))
        if req.save_to_grid:
            save_tasks.append(self.grid.upload(ticket, report_html, req.user_email))

        if save_tasks:
            results = await asyncio.gather(*save_tasks, return_exceptions=True)
            idx = 0
            if req.save_to_drive:
                drive_url = results[idx] if not isinstance(results[idx], Exception) else None
                idx += 1
            if req.save_to_grid:
                grid_url = results[idx] if not isinstance(results[idx], Exception) else None

        duration = round(time.time() - start, 2)
        logger.info(f"[NATIS] Análise concluída: {ticket} em {duration}s")

        return AnalyzeResponse(
            ticket=ticket,
            status="success",
            report=report_md,
            report_html=report_html,
            sources_consulted=sources_consulted,
            grid_url=grid_url,
            drive_url=drive_url,
            generated_at=__import__('datetime').datetime.utcnow().isoformat() + "Z",
            duration_seconds=duration,
            metadata={"sources_found": len([s for s in sources_consulted if "❌" not in s])}
        )

    async def _gather_sources(self, ticket: str):
        sshp_num = ''.join(filter(str.isdigit, ticket))
        sshp_key = f"SSHP-{sshp_num}" if sshp_num else ticket
        issm_key = f"ISSM-{sshp_num}" if sshp_num else ticket

        tasks = [
            self.jira.get_issue(sshp_key),
            self.jira.search_related(sshp_num),
            self.confluence.search(sshp_num),
            self.confluence.search(issm_key),
            self.datadog.search_incidents(sshp_num),
            self.drive.search(sshp_num),
            self.drive.search(sshp_num, settings.DRIVE_NATIS_FOLDER),
            self.slack.search(sshp_key),
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        def safe(r, name):
            if isinstance(r, Exception):
                logger.warning(f"{name} error: {r}")
                return None, f"❌ {name}: {str(r)[:60]}"
            return r, f"✅ {name}"

        jira_issue, s0 = safe(results[0], "Jira · ticket principal")
        jira_related, s1 = safe(results[1], "Jira · tickets correlatos")
        confluence_issm, s2 = safe(results[2], "Confluence ISSM")
        confluence_issm2, s3 = safe(results[3], "Confluence ISSM correlato")
        dd_incidents, s4 = safe(results[4], "Datadog · bitácora")
        drive_recs, s5 = safe(results[5], "Drive · gravações")
        drive_natis, s6 = safe(results[6], "Drive · NATIS")
        slack_msgs, s7 = safe(results[7], "Slack · canal incidente")

        sources = SourceData(
            jira={
                "issue": jira_issue,
                "related": jira_related or []
            },
            confluence={
                "pages": (confluence_issm or []) + (confluence_issm2 or [])
            },
            datadog={"incidents": dd_incidents or []},
            drive={
                "recordings": drive_recs or [],
                "natis": drive_natis or []
            },
            slack={"messages": slack_msgs or []}
        )

        return sources, [s0, s1, s2, s3, s4, s5, s6, s7]

    def _md_to_html(self, md: str, ticket: str) -> str:
        import re
        h = md.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')
        h = re.sub(r'^## (.+)$', r'<h2>\1</h2>', h, flags=re.M)
        h = re.sub(r'^### (.+)$', r'<h3>\1</h3>', h, flags=re.M)
        h = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', h)
        h = re.sub(r'^[\-\*] (.+)$', r'<li>\1</li>', h, flags=re.M)
        h = re.sub(r'^(\d+)\. (.+)$', r'<li>\2</li>', h, flags=re.M)
        h = re.sub(r'^---$', r'<hr/>', h, flags=re.M)
        h = re.sub(r'^> (.+)$', r'<blockquote>\1</blockquote>', h, flags=re.M)
        h = h.replace('\n\n', '</p><p>').replace('\n', '<br/>')
        return f"""<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8"/>
<title>NATIS · {ticket}</title>
<style>
body{{font-family:system-ui,sans-serif;max-width:960px;margin:40px auto;padding:20px;color:#1a1a2e;line-height:1.7;background:#fff;}}
.header{{background:#FFE600;padding:14px 20px;border-radius:8px;margin-bottom:24px;}}
h2{{color:#1a1a2e;border-bottom:3px solid #FFE600;padding-bottom:6px;margin:24px 0 10px;}}
h3{{color:#333;margin:16px 0 6px;}}
blockquote{{border-left:4px solid #FFE600;padding:8px 14px;background:#fffce0;margin:10px 0;border-radius:0 6px 6px 0;}}
code{{background:#f0f0f0;padding:2px 6px;border-radius:3px;font-size:12px;}}
li{{margin:4px 0;}} table{{width:100%;border-collapse:collapse;}}
th{{background:#1a1a2e;color:#fff;padding:8px 12px;text-align:left;}}
td{{padding:7px 12px;border-bottom:1px solid #eee;}}
.footer{{margin-top:40px;padding-top:16px;border-top:2px solid #FFE600;font-size:12px;color:#666;}}
</style></head><body>
<div class="header">
  <strong style="font-size:18px;">⚙ NATIS · Relatório de Incidente · {ticket}</strong>
  <div style="font-size:12px;margin-top:4px;">IS Shipping Brasil · Mercado Livre · Gerado automaticamente</div>
</div>
<div>{h}</div>
<div class="footer">Gerado por NATIS Incident Analyzer · grid.adminml.com · IS Shipping Brasil</div>
</body></html>"""
