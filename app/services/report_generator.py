import anthropic
import json
import logging
from app.config import settings
from app.models.incident import SourceData

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Você é o NATIS Incident Analyzer — especialista sênior em gestão de incidentes críticos do IS Shipping Brasil, Mercado Livre.

Sua missão é gerar relatórios gerenciais de alta qualidade que combinam visão técnica profunda com clareza executiva.

PRINCÍPIOS DO RELATÓRIO:
• Linguagem direta, objetiva, sem jargão desnecessário
• Cada seção tem propósito claro: técnico OU gerencial
• Evidências sempre referenciadas (fonte: Jira, Confluence, Drive, Datadog, Slack)
• Recomendações acionáveis com responsável e prazo sugerido
• Tom construtivo — foco em melhoria, não em culpa

ESTRUTURA OBRIGATÓRIA:

## 🔴 IDENTIFICAÇÃO DO INCIDENTE
Tabela com: Ticket | Data | Severidade | Status | Área | Condutor | Duração | Sites afetados

## 📊 RESUMO EXECUTIVO
3-5 linhas para líderes. O que aconteceu, impacto real, como foi resolvido, o que precisa ser feito. Linguagem não-técnica.

## 📈 IMPACTO OPERACIONAL
- Quantitativo: sites afetados, tempo de impacto, estimativa de pacotes/etiquetas afetados
- Qualitativo: risco operacional, imagem, reincidência
- Comparativo com incidentes anteriores (se houver)

## 🔬 ANÁLISE DE CAUSA RAIZ
Técnico mas acessível. Use o modelo "5 Porquês" quando possível:
- Causa imediata (o que falhou)
- Causa raiz (por que falhou)  
- Causa sistêmica (por que a causa raiz existe)
- Evidências das fontes consultadas

## ⟳ LINHA DO TEMPO
Tabela cronológica com: Horário | Evento | Equipe | Fonte

## 👥 ANÁLISE DE EQUIPES
- Quem participou, quando entrou, qual foi a contribuição
- Destaque positivos (resposta rápida, boa comunicação) e pontos de melhoria
- SLA de resposta por equipe

## 🔗 CORRELAÇÃO DE INCIDENTES
- Este incidente é novo ou reincidência?
- Tickets relacionados encontrados
- Padrão identificado (se houver)

## ✅ ACTION ITEMS
Tabela com: # | Ação | Prioridade | Responsável | Prazo Sugerido | Impacto Esperado

## 💡 PONTOS DE MELHORIA
3 a 5 melhorias estruturais priorizadas com:
- Problema atual
- Solução proposta
- Benefício esperado
- Esforço estimado (baixo/médio/alto)

## 📚 LIÇÕES APRENDIDAS
O que este incidente ensina para o time e para a organização

## 🔗 LINKS E REFERÊNCIAS
Todos os links encontrados nas fontes consultadas

---

Se alguma fonte não retornou dados, mencione brevemente e prossiga com o que está disponível.
Ao final de cada seção técnica, adicione uma linha "**Em linguagem simples:**" com 1-2 frases explicando para um gestor não-técnico."""

class ReportGenerator:
    def __init__(self):
        self.client = None
        self._init_client()

    def _init_client(self):
        try:
            # Tenta Fury GenAI primeiro (produção)
            if settings.GENAI_SCOPE == "prod":
                try:
                    from fury_genai import Client as FuryClient
                    self.client = FuryClient()
                    self.use_fury = True
                    logger.info("Usando Fury GenAI (prod)")
                    return
                except ImportError:
                    logger.info("fury_genai não disponível — usando Anthropic SDK")
            
            # Fallback: Anthropic SDK direto
            if settings.ANTHROPIC_API_KEY:
                self.client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
                self.use_fury = False
                logger.info("Usando Anthropic SDK direto")
            else:
                logger.warning("Nenhuma credencial GenAI configurada")
                self.client = None
        except Exception as e:
            logger.error(f"Erro ao inicializar GenAI client: {e}")
            self.client = None

    async def generate(self, ticket: str, sources: SourceData, language: str = "pt-BR") -> str:
        if not self.client:
            return self._fallback_report(ticket, sources)

        context = self._build_context(ticket, sources)
        prompt = f"""Analise o incidente **{ticket}** com base nos dados coletados abaixo e gere o relatório completo.

DADOS COLETADOS DAS FONTES:
{context}

TICKET ANALISADO: {ticket}
IDIOMA: {language}

Gere o relatório gerencial completo seguindo a estrutura definida."""

        try:
            if hasattr(self, 'use_fury') and self.use_fury:
                # Fury GenAI
                response = self.client.complete(
                    model=settings.GENAI_MODEL,
                    system=SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=4096
                )
                return response.content[0].text if hasattr(response, 'content') else str(response)
            else:
                # Anthropic SDK
                response = self.client.messages.create(
                    model=settings.GENAI_MODEL,
                    max_tokens=4096,
                    system=SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": prompt}]
                )
                return response.content[0].text
        except Exception as e:
            logger.error(f"GenAI error: {e}")
            return self._fallback_report(ticket, sources)

    def _build_context(self, ticket: str, sources: SourceData) -> str:
        parts = []

        if sources.jira and sources.jira.get("issue"):
            issue = sources.jira["issue"]
            if not issue.get("error"):
                parts.append(f"""=== JIRA: {issue.get('key')} ===
Título: {issue.get('summary','')}
Status: {issue.get('status','')} | Prioridade: {issue.get('priority','')}
Reporter: {issue.get('reporter','')} | Criado: {issue.get('created','')}
Descrição: {str(issue.get('description',''))[:1000]}
Labels: {', '.join(issue.get('labels',[]))}
URL: {issue.get('url','')}""")

        if sources.jira and sources.jira.get("related"):
            related = sources.jira["related"][:5]
            if related:
                parts.append("=== JIRA CORRELATOS ===\n" + "\n".join([
                    f"• {r.get('key')}: {r.get('summary','')} [{r.get('status','')}] {r.get('url','')}"
                    for r in related
                ]))

        if sources.confluence and sources.confluence.get("pages"):
            pages = sources.confluence["pages"][:3]
            if pages:
                parts.append("=== CONFLUENCE ISSM ===\n" + "\n".join([
                    f"• {p.get('title','')}\n  URL: {p.get('url','')}\n  Trecho: {p.get('excerpt','')[:300]}"
                    for p in pages
                ]))

        if sources.datadog and sources.datadog.get("incidents"):
            incidents = sources.datadog["incidents"][:3]
            if incidents:
                parts.append("=== DATADOG INCIDENTS ===\n" + "\n".join([
                    f"• {i.get('title','')}: {i.get('status','')} | {i.get('url','')}"
                    for i in incidents
                ]))

        if sources.drive and sources.drive.get("recordings"):
            files = sources.drive["recordings"][:5]
            if files:
                parts.append("=== DRIVE GRAVAÇÕES/TRANSCRIÇÕES ===\n" + "\n".join([
                    f"• {f.get('name','')} [{f.get('type','')}] {f.get('url','')}"
                    for f in files
                ]))

        if sources.slack and sources.slack.get("messages"):
            msgs = sources.slack["messages"][:5]
            if msgs:
                parts.append("=== SLACK MENSAGENS ===\n" + "\n".join([
                    f"• [{m.get('channel','')}] {m.get('user','')}: {m.get('text','')[:200]}"
                    for m in msgs
                ]))

        return "\n\n".join(parts) if parts else "Nenhuma fonte retornou dados. Gere o relatório baseado no ticket informado e no conhecimento da plataforma NATIS."

    def _fallback_report(self, ticket: str, sources: SourceData) -> str:
        sources_found = []
        if sources.jira and sources.jira.get("issue") and not sources.jira["issue"].get("error"):
            issue = sources.jira["issue"]
            sources_found.append(f"**Jira:** {issue.get('key')} — {issue.get('summary','')} [{issue.get('status','')}]")
        if sources.confluence and sources.confluence.get("pages"):
            for p in sources.confluence["pages"][:2]:
                sources_found.append(f"**Confluence:** {p.get('title','')} — {p.get('url','')}")
        if sources.drive and sources.drive.get("recordings"):
            for f in sources.drive["recordings"][:2]:
                sources_found.append(f"**Drive:** {f.get('name','')} — {f.get('url','')}")

        src_text = "\n".join(sources_found) if sources_found else "Nenhuma fonte com dados disponíveis."

        return f"""## 🔴 IDENTIFICAÇÃO DO INCIDENTE

| Campo | Valor |
|-------|-------|
| Ticket | {ticket} |
| Status | Em análise |
| Gerado | {__import__('datetime').datetime.now().strftime('%d/%m/%Y %H:%M')} |

## 📊 RESUMO EXECUTIVO

Análise iniciada para o ticket **{ticket}**. O GenAI não está disponível no momento — relatório parcial gerado com dados das fontes consultadas.

## 🔗 DADOS ENCONTRADOS NAS FONTES

{src_text}

## 🔗 LINKS PARA CONSULTA

- Jira: https://mercadolibre.atlassian.net/browse/{ticket}
- Confluence ISSM: https://mercadolibre.atlassian.net/wiki/spaces/ISSM/
- Drive Gravações: https://drive.google.com/drive/folders/1N5h4IluBk3CTR2cpmQH0TQl_4_sQ3k1H
- Datadog: https://app.datadoghq.com/incidents/

---
*Para relatório completo, configure ANTHROPIC_API_KEY ou use GENAI_SCOPE=prod no Fury.*"""
