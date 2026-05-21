import anthropic
import logging
from app.config import settings
from app.models.incident import SourceData

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Você é o NATIS Incident Analyzer — analista sênior de incidentes críticos do IS Shipping Brasil, Mercado Livre.

Gere relatórios gerenciais de alta qualidade seguindo rigorosamente esta estrutura:

---

## 🔴 IDENTIFICAÇÃO DO INCIDENTE
Tabela completa: Ticket | Data/Hora | Severidade | Status | Área | Condutor | Duração | Reincidência

## 📊 RESUMO EXECUTIVO *(para C-level e líderes — máx. 5 linhas)*
O que aconteceu → impacto real no negócio → como foi resolvido → o que precisa ser feito.
Linguagem não-técnica. Foco em impacto operacional e financeiro.

## 📈 IMPACTO OPERACIONAL
**Quantitativo:**
- Sites afetados e volume de etiquetas/pacotes impactados
- Tempo total de impacto e SLA afetado
- Estimativa de retrabalho operacional (horas × pessoas)

**Qualitativo:**
- Risco à experiência do cliente
- Imagem e confiabilidade da operação
- Reincidência: análise histórica

## 🔬 ANÁLISE DE CAUSA RAIZ *(Modelo 5 Porquês)*
**1. O que falhou?** (causa imediata)
**2. Por que falhou?** (causa raiz técnica)
**3. Por que a causa raiz existe?** (falha sistêmica / processo)
**4. Por que não foi prevenido?** (falha de controle)
**5. Por que não foi detectado antes?** (falha de monitoramento)
> Evidências: cite as fontes consultadas (Jira, Confluence, Drive, Slack, Datadog)

## ⟳ LINHA DO TEMPO DETALHADA
| Horário | Evento | Equipe | Impacto | Fonte |

## 👥 ANÁLISE DE EQUIPES E RESPOSTA
Para cada equipe: entrada | SLA resposta | ações tomadas | efetividade
**Destaque:** pontos positivos e oportunidades de melhoria na coordenação

## 🔗 CORRELAÇÃO E HISTÓRICO
- Este incidente é reincidência? Compare com histórico
- Tickets filhos e relacionados
- Padrão identificado? Tendência?

## ✅ ACTION ITEMS PRIORIZADOS
| # | Ação | Prioridade | Responsável | Prazo | Impacto Esperado |
Prioridades: 🔴 CRÍTICO | 🟠 URGENTE | 🟡 ALTA | 🟢 MÉDIA

## 💡 PONTOS DE MELHORIA ESTRUTURAL
Para cada melhoria:
- **Problema atual** → **Solução proposta** → **Benefício esperado** → **Esforço** (baixo/médio/alto) → **ROI estimado**

Mínimo 5 melhorias cobrindo: processo, tecnologia, comunicação, prevenção, detecção

## 📚 LIÇÕES APRENDIDAS
3-5 lições concretas e acionáveis para o time e para a organização

## 🎯 INDICADORES DE ACOMPANHAMENTO
KPIs para monitorar os action items e prevenir reincidência

## 🔗 LINKS E REFERÊNCIAS
Todos os links encontrados nas fontes consultadas

---

**Regras obrigatórias:**
- Após cada seção técnica: **💬 Em linguagem simples:** (1-2 frases para gestores)
- Evidências sempre com fonte citada
- Tom construtivo — foco em melhoria, não em culpa
- Se dados não disponíveis, informe e use o que tem
- Seja específico com números, horários e nomes quando disponíveis"""


class ReportGenerator:
    def __init__(self):
        self.client = None
        self.use_fury = False
        self._init_client()

    def _init_client(self):
        try:
            if settings.GENAI_SCOPE == "prod":
                try:
                    from fury_genai import Client as FuryClient
                    self.client = FuryClient()
                    self.use_fury = True
                    logger.info("GenAI: Fury prod")
                    return
                except ImportError:
                    pass

            if settings.ANTHROPIC_API_KEY:
                self.client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
                logger.info("GenAI: Anthropic SDK")
            else:
                logger.warning("Sem credencial GenAI")
        except Exception as e:
            logger.error(f"GenAI init error: {e}")

    async def generate(self, ticket: str, sources: SourceData, language: str = "pt-BR",
                      transcription: str = None) -> str:
        if not self.client:
            return self._fallback_report(ticket, sources)

        context = self._build_context(ticket, sources, transcription)

        prompt = f"""Analise o incidente **{ticket}** com base em todos os dados coletados.

DADOS COLETADOS DAS FONTES:
{context}

IDIOMA DO RELATÓRIO: {language}
TICKET: {ticket}

Gere o relatório gerencial completo seguindo rigorosamente a estrutura definida.
Seja preciso, use todos os dados disponíveis e cite as fontes."""

        try:
            if self.use_fury:
                resp = self.client.complete(
                    model=settings.GENAI_MODEL,
                    system=SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=6000
                )
                return resp.content[0].text if hasattr(resp, 'content') else str(resp)
            else:
                resp = self.client.messages.create(
                    model=settings.GENAI_MODEL,
                    max_tokens=6000,
                    system=SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": prompt}]
                )
                return resp.content[0].text
        except Exception as e:
            logger.error(f"GenAI error: {e}")
            return self._fallback_report(ticket, sources)

    def _build_context(self, ticket: str, sources: SourceData, transcription: str = None) -> str:
        parts = []

        if sources.jira:
            issue = sources.jira.get("issue", {})
            if issue and not issue.get("error"):
                parts.append(f"""=== JIRA: {issue.get('key')} ===
Título: {issue.get('summary')}
Status: {issue.get('status')} | Prioridade: {issue.get('priority')}
Reporter: {issue.get('reporter')} | Criado: {issue.get('created')}
Labels: {', '.join(issue.get('labels', []))}
URL: {issue.get('url')}""")

            related = sources.jira.get("related", [])
            if related:
                parts.append("=== JIRA CORRELATOS ===\n" + "\n".join([
                    f"• {r.get('key')}: {r.get('summary')} [{r.get('status')}]"
                    for r in related[:5]
                ]))

        if sources.confluence and sources.confluence.get("pages"):
            parts.append("=== CONFLUENCE ISSM ===\n" + "\n".join([
                f"• {p.get('title')}\n  URL: {p.get('url')}\n  Trecho: {p.get('excerpt','')[:300]}"
                for p in sources.confluence["pages"][:3]
            ]))

        if sources.datadog and sources.datadog.get("incidents"):
            parts.append("=== DATADOG INCIDENTS ===\n" + "\n".join([
                f"• {i.get('title')} [{i.get('status')}] {i.get('url')}"
                for i in sources.datadog["incidents"][:3]
            ]))

        if sources.drive and sources.drive.get("recordings"):
            files = sources.drive["recordings"]
            parts.append("=== DRIVE (Gravações/Transcrições) ===\n" + "\n".join([
                f"• {f.get('name')} [{f.get('type')}] {f.get('url')}"
                for f in files[:5]
            ]))

        if sources.slack and sources.slack.get("messages"):
            parts.append("=== SLACK ===\n" + "\n".join([
                f"• [{m.get('channel')}] {m.get('user')}: {m.get('text','')[:200]}"
                for m in sources.slack["messages"][:5]
            ]))

        if transcription:
            parts.append(f"""=== TRANSCRIÇÃO DA GRAVAÇÃO (War Room) ===
{transcription[:4000]}
... (transcrição completa disponível no Drive)""")

        return "\n\n".join(parts) if parts else "Fontes consultadas não retornaram dados."

    def _fallback_report(self, ticket: str, sources: SourceData) -> str:
        from datetime import datetime
        return f"""## 🔴 IDENTIFICAÇÃO
| Campo | Valor |
|-------|-------|
| Ticket | **{ticket}** |
| Gerado | {datetime.now().strftime('%d/%m/%Y %H:%M')} |
| Status | Análise parcial — GenAI não configurado |

## ⚠️ Configuração necessária
Para análise completa com IA, configure `ANTHROPIC_API_KEY` ou use `GENAI_SCOPE=prod` no Fury.

## 🔗 LINKS PARA CONSULTA MANUAL
- Jira: https://mercadolibre.atlassian.net/browse/{ticket}
- Confluence: https://mercadolibre.atlassian.net/wiki/spaces/ISSM/
- Datadog: https://app.datadoghq.com/incidents/
- Drive: https://drive.google.com/drive/folders/1N5h4IluBk3CTR2cpmQH0TQl_4_sQ3k1H"""
