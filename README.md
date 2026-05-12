# SRM Credit Engine — Backend

Motor de precificação e liquidação de recebíveis para a SRM Asset. Responsável pelo cálculo de deságio, gestão de câmbio, processamento de lotes e auditoria de transações.

---

## Requisitos Funcionais

### Autenticação
- Autenticação simples por usuário e senha (operadores internos da SRM)
- Um usuário autenticado opera para qualquer cedente sem restrição de acesso

### Gestão de Parâmetros
- Tabela de tipos de recebível com spread configurável (ex: Duplicata Mercantil 1.5% a.m., Cheque Pré-datado 2.5% a.m.)
- Tabela de taxa base configurável
- Nenhuma regra de precificação pode ser hardcoded — alterações de parâmetros não exigem redeploy

### Gestão de Câmbio
- Job diário que coleta a taxa USD/BRL de uma API primária com fallback para API secundária
- Taxa persistida com timestamp e marcação de fonte (primary, secondary)
- Se ambas as fontes falharem, a taxa existente é marcada como `stale`
- Operações cross-currency com taxa `stale` são bloqueadas com mensagem clara ao operador
- Histórico completo de taxas preservado para auditoria de extratos passados

### Motor de Precificação
- Strategy Pattern por tipo de recebível
- Fórmula: `VP = VF / (1 + TaxaBase + Spread) ^ Prazo`
- Para operações cross-currency (título BRL, liquidação USD): conversão cambial aplicada sobre o VP final
- Taxa de câmbio congelada no momento da liquidação e armazenada na transação (imutabilidade para auditoria)

### Gestão de Recebíveis
- Recebíveis existem de forma independente no sistema — não estão atrelados a um lote
- Entrada via upload de XMLs de notas fiscais; futuras integrações podem carregar títulos diretamente sem XML
- Cada linha representa uma duplicata (uma NF pode gerar múltiplas duplicatas com vencimentos distintos)
- Recebível carrega cedente e sacado diretamente — sem necessidade de join para identificar as partes
- Títulos com status `anticipated` nunca aparecem para seleção — filtrados na consulta
- Ciclo de vida: `available → in_lote → anticipated` (rejeição de lote devolve para `available`)

### Processamento de Lotes
- Lote é uma **solicitação de antecipação** — agrupa recebíveis que o operador quer liquidar
- Cada lote pertence a um único cedente
- Recebíveis de status `in_lote` ficam bloqueados para outros lotes enquanto a solicitação está pendente
- Preview do lote com VP calculado por duplicata antes da confirmação
- Ao confirmar, o lote entra em fila (`queued`) e a validação ocorre de forma **assíncrona** — o operador não fica bloqueado em tela
- A fila é implementada via polling no banco (worker consulta lotes com status `queued`) — sem infraestrutura adicional
- Lote é atômico: `approved` integralmente ou `rejected` integralmente
- Em caso de rejeição, todos os motivos são salvos no lote e os recebíveis voltam para `available` (exceto os já antecipados por outro lote)
- Ciclo de vida do lote: `pending → queued → approved | rejected`
- Liquidação com garantia ACID e optimistic locking para prevenir race conditions

### Extrato de Liquidação
- Consulta de transações liquidadas com filtros por período, cedente e moeda
- Agrupamento por cedente, sacado ou nenhum
- Paginação server-side
- Implementado com SQL otimizado ou Query Builder — sem ORM puro para relatórios

### Gerador de XMLs (ferramenta auxiliar)
- Script Python separado, fora da API
- Gera XMLs de notas fiscais fake conforme parâmetros informados (cedente, tipo, quantidade, faixa de valores, vencimentos)
- Substitui integração real com SEFAZ no escopo deste desafio

---

## Requisitos Não Funcionais

### Qualidade de Código
- Tipagem forte em todo o código (Pydantic obrigatório)
- Arquitetura em 3 camadas: Application → Business → Persistence
- Relatórios e consultas analíticas podem operar em 2 camadas (Application → Persistence)
- Princípios SOLID, DRY e KISS
- Tratamento de exceções global

### API
- RESTful com verbos HTTP e status codes semânticos
- Documentação OpenAPI/Swagger gerada automaticamente

### Persistência
- PostgreSQL como banco relacional
- Transações ACID em toda operação de liquidação
- Optimistic locking para prevenção de conflitos em liquidações concorrentes
- Chave de nota fiscal única e indexada

### Observabilidade
- Logs estruturados e tracing via OpenTelemetry exportado para Axiom
- Docker Compose local sobe apenas API + banco — sem Prometheus/Grafana localmente

### Ambiente
- Docker Compose para orquestração local (API + banco)
- `docker-compose.vps.yml` para o worker na VPS

### Versionamento
- Conventional Commits obrigatório
- Pull Requests para merge de features na branch principal
- Tags semânticas para marcação de versões (ex: `v1.0.0`)
- Interactive rebase para histórico limpo antes do merge
- Git hooks para lint e testes antes do commit

### CI/CD
- GitHub Actions executando lint e testes em todo PR

---

## Git Workflow

### Estratégia de branching: GitHub Flow

Este projeto adota **GitHub Flow** — uma estratégia trunk-based simplificada com uma única branch de longa duração (`main`).

```
main ──●──────────────────●──────────────────●──────────────────▶
       │                  ↑                  ↑
       └── feat/x ────────┘  └── fix/y ──────┘
```

**Por que GitHub Flow e não Git Flow?**

| Critério | Git Flow | GitHub Flow | Escolha |
|---|---|---|---|
| Branches de longa duração | `main` + `develop` + `release/*` + `hotfix/*` | apenas `main` | GitHub Flow — menos overhead |
| Frequência de deploy | releases agendadas | deploy contínuo | GitHub Flow — Vercel deploya a cada merge |
| Tamanho do time | times grandes com múltiplos releases paralelos | times pequenos ou entrega contínua | GitHub Flow — projeto de entrega única |
| Hotfix em produção | branch `hotfix/` dedicada | branch a partir da `main` | GitHub Flow — mesmo fluxo de qualquer feature |

Git Flow seria a escolha certa se o projeto tivesse múltiplos ambientes de release em paralelo (ex: `v1.x` em produção enquanto `v2.x` está em QA). Para este projeto — com deploy contínuo na Vercel e um único ambiente de produção — o overhead do Git Flow não se justifica.

### Convenções de nome de branch

| Prefixo | Uso |
|---|---|
| `feat/` | nova funcionalidade |
| `fix/` | correção de bug |
| `docs/` | documentação |
| `chore/` | configuração, CI, dependências |
| `refactor/` | refatoração sem mudança de comportamento |

### Fluxo de uma feature

```bash
# 1. Partir sempre da main atualizada
git checkout main && git pull

# 2. Criar branch
git checkout -b feat/exchange-rate-engine

# 3. Desenvolver com commits atômicos (Conventional Commits)
git commit -m "feat: add exchange rate model and migration"
git commit -m "feat: implement FX job with primary/fallback sources"
git commit -m "test: unit tests for FX service circuit breaker"

# 4. Rebase interativo antes do PR para histórico limpo
git rebase -i origin/main

# 5. Abrir PR — CI roda lint + testes automaticamente
gh pr create ...

# 6. Merge squash ou merge commit após aprovação
# 7. Taguear se for entrega de versão
git tag v1.0.0 && git push origin v1.0.0
```

### Simulação de gestão de crise

**Cenário:** um bug crítico foi mergeado na `main` inadvertidamente.

A abordagem segura é `git revert` — cria um commit que desfaz as mudanças sem reescrever o histórico, preservando rastreabilidade em produção.

```bash
# Identificar o commit problemático
git log --oneline main

# Reverter de forma segura (não destrói histórico)
git revert <commit-hash> --no-edit

# Fazer push direto na main (hotfix de emergência)
git push origin main

# Após correção real, cherry-pick do fix para branches em andamento
git cherry-pick <fix-commit-hash>
```

`git reset --hard` é evitado em branches públicas pois reescreve histórico e força outros desenvolvedores a rebases manuais. `revert` é sempre preferível em produção.

---

## Fora do Escopo

| Item                                 | Motivo                                                                  |
| ------------------------------------ | ----------------------------------------------------------------------- |
| IaC (Terraform, Kubernetes)          | Vercel + RDS gerenciado cobre o deploy sem complexidade adicional       |
| Multi-fundo                          | Não requerido pelo desafio — documentado em ADR                         |
| Limite de crédito por cedente/sacado | Não requerido pelo desafio — documentado em ADR                         |
| Score de risco por sacado            | Spread orientado por tipo de ativo conforme especificação               |
| Integração real SEFAZ                | Substituída pelo gerador de XMLs no escopo do desafio                   |
| Níveis de acesso por usuário         | Não requerido — documentado em ADR                                      |
| Integração BACEN                     | Substituída por controle interno de status da nota — documentado em ADR |
| Agrupamento por fundo no extrato     | Multi-fundo fora do escopo do prazo atual — implementar se houver tempo |

---

## Arquitetura de Deploy

### Ambiente atual (entrega do desafio)

```
Vercel (serverless)          Neon PostgreSQL
┌─────────────────┐          ┌──────────────┐
│  FastAPI API    │────────▶ │  PostgreSQL  │
│  Next.js Front  │          └──────────────┘
│  Cron: câmbio   │
└─────────────────┘
        │
        ▼
VPS (Docker)                 Axiom (cloud)
┌─────────────────┐          ┌──────────────┐
│  Worker lotes   │────────▶ │  Logs/Traces │
└─────────────────┘          └──────────────┘
```

### Caminho para produção com stack AWS

A SRM Asset opera sobre AWS. A evolução natural desta arquitetura para o ambiente deles seria:

| Componente | Entrega atual | AWS |
|---|---|---|
| API | Vercel serverless | Lambda + API Gateway (adapter Mangum) |
| Frontend | Vercel | CloudFront + S3 ou Amplify |
| Banco | Neon PostgreSQL | RDS PostgreSQL (Multi-AZ) |
| Worker de lotes | VPS / Docker | ECS Fargate |
| Job de câmbio | Vercel Cron | EventBridge Scheduler |
| Logs e Traces | Axiom | CloudWatch + X-Ray |
| Secrets | Variáveis de ambiente | AWS Secrets Manager |

A decisão de entregar na Vercel + Neon foi tomada pelo prazo e pela ausência de free tier permanente na AWS para RDS e ECS. A arquitetura do código é agnóstica ao ambiente de deploy — a migração para AWS não exige reescrita, apenas configuração de infraestrutura.

---

## Decisões Arquiteturais

As decisões que envolvem trade-offs de negócio e arquitetura estão documentadas em [`docs/adrs/`](./docs/adrs/).

> **Nota:** Em um projeto com múltiplos times, ADRs deveriam residir em uma fonte única de verdade (Confluence, Notion, repositório de documentação). O trade-off de mantê-los aqui é aceito dado o escopo reduzido do projeto.

---

## Arquitetura

- [Diagrama C4 — Context e Container](./docs/c4-diagrams.md) — atores, sistemas externos, containers e dependências

## Modelagem de Dados

- [Diagrama ER](./docs/er-diagram.md) — entidades, relacionamentos e decisões de modelagem
- [Schema DDL](./docs/schema.sql) — scripts para criação do banco (PostgreSQL 15+)

---

## Como rodar

### Pré-requisitos

- [Docker](https://docs.docker.com/get-docker/) e [Docker Compose](https://docs.docker.com/compose/install/)
- Python 3.12+ (apenas para rodar fora do Docker)

### 1. Configurar variáveis de ambiente

```bash
cp .env.example .env
```

Edite o `.env` se necessário. Para ambiente local, os valores padrão já funcionam.

### 2. Subir os containers

```bash
docker compose up -d
```

Isso sobe:
- `api` — FastAPI na porta `8000`
- `db` — PostgreSQL 16 na porta `5432`

### 3. Rodar as migrations

```bash
docker compose exec api alembic upgrade head
```

### 4. Rodar o seed

```bash
docker compose exec api python scripts/seed.py
```

O seed insere:
- 5 tipos de recebível (`product_types`) com spreads pré-configurados
- Parâmetro de taxa base (`base_rate_annual = 0.1375`)
- Usuário admin: `admin@srm.com.br` / `Admin@2026`

Para recriar os registros do zero:

```bash
docker compose exec api python scripts/seed.py --reset
```

### 5. Verificar

- API: http://localhost:8000/health
- Docs (Swagger): http://localhost:8000/docs

### Parar os containers

```bash
docker compose down
```

Para remover o volume do banco junto:

```bash
docker compose down -v
```

---

## Ambiente de produção

| Recurso | URL |
|---|---|
| API | https://srm-back-psi.vercel.app |
| Docs | https://srm-back-psi.vercel.app/docs |
| Banco | Neon PostgreSQL (sa-east-1) |

### Rodar seed em produção

```bash
# Exportar a DATABASE_URL do Neon antes de executar
export DATABASE_URL="postgresql://..."
python scripts/seed.py
```
