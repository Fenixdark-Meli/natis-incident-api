# NATIS Incident Analyzer — Fury Backend

Backend para análise automática de incidentes críticos · IS Shipping Brasil · Mercado Livre

## Deploy rápido

```bash
# 1. Clone e entre na pasta
cd natis-incident-api

# 2. Configure os secrets no Fury
fury secrets set natis/atlassian-token "seu-token-atlassian"
fury secrets set natis/datadog-api-key "seu-dd-api-key"
fury secrets set natis/datadog-app-key "seu-dd-app-key"
fury secrets set natis/drive-token "seu-google-token"
fury secrets set natis/slack-token "xoxb-seu-slack-token"

# 3. Deploy
fury deploy

# 4. Pegue a URL
fury describe natis-incident-api | grep url
```

## Como usar

```bash
# Análise via curl
curl -X POST "https://natis-incident-api.melioffice.com/api/v1/analyze" \
  -H "Content-Type: application/json" \
  -H "X-User-Email: danillo.ferreira@mercadolivre.com" \
  -d '{"ticket": "SSHP-1438213", "save_to_drive": true, "save_to_grid": true}'

# Análise via GET (conveniência)
curl "https://natis-incident-api.melioffice.com/api/v1/analyze/SSHP-1440063"
```

## Fontes consultadas por análise

| Fonte | O que busca |
|-------|-------------|
| Jira | Ticket principal + tickets correlatos |
| Confluence ISSM | Páginas de documentação relacionadas |
| Drive (gravações) | Transcrições e gravações do war room |
| Slack | Mensagens do canal do incidente |
| Datadog | Bitácora IR e métricas |

## Estrutura do relatório gerado

1. 🔴 Identificação do Incidente
2. 📊 Resumo Executivo (para líderes)
3. 📈 Impacto Operacional
4. 🔬 Análise de Causa Raiz (5 Porquês)
5. ⟳ Linha do Tempo cronológica
6. 👥 Análise de Equipes e SLA de resposta
7. 🔗 Correlação de Incidentes (reincidências)
8. ✅ Action Items priorizados com responsável e prazo
9. 💡 Pontos de Melhoria estruturais
10. 📚 Lições Aprendidas
11. 🔗 Links e Referências

## Secrets necessários

| Secret | Onde gerar |
|--------|-----------|
| `natis/atlassian-token` | id.atlassian.com/manage-profile/security → API tokens |
| `natis/datadog-api-key` | app.datadoghq.com/organization-settings/api-keys |
| `natis/datadog-app-key` | app.datadoghq.com/organization-settings/application-keys |
| `natis/drive-token` | Google OAuth (escopo: drive.readonly + drive.file) |
| `natis/slack-token` | api.slack.com/apps → Bot Token |

## Desenvolvimento local

```bash
# Instala dependências
poetry install

# Roda local (precisa VPN para GenAI em local_prod)
cp .env.example .env
# Edite .env com suas credenciais
GENAI_SCOPE=local_prod python -m uvicorn app.main:app --reload

# Testa
curl http://localhost:8000/ping  # → pong
curl -X POST http://localhost:8000/api/v1/analyze \
  -H "Content-Type: application/json" \
  -d '{"ticket":"SSHP-1457458"}'
```
