# C4 Diagrams — SRM Credit Engine

Documentação arquitetural nos níveis de Context e Container seguindo o modelo C4 (Simon Brown).

---

## Nível 1 — System Context

Mostra quem interage com o sistema e quais sistemas externos ele depende. Sem detalhes de tecnologia.

```mermaid
C4Context
  title System Context — SRM Credit Engine

  Person(operador, "Operador", "Colaborador interno da SRM Asset. Faz upload de NF-e, gerencia lotes de antecipação e consulta extratos de liquidação.")

  System(srm, "SRM Credit Engine", "Precifica e liquida recebíveis (duplicatas) de cedentes. Suporta operações em BRL e USD com deságio calculado por tipo de ativo e taxa de câmbio vigente.")

  System_Ext(api_fx_primary, "API de Câmbio Primária", "Fornece cotação USD/BRL em tempo real. Fonte preferencial para o job diário de câmbio.")
  System_Ext(api_fx_secondary, "API de Câmbio Secundária", "Fallback automático quando a fonte primária está indisponível.")
  System_Ext(axiom, "Axiom", "Plataforma de observabilidade cloud. Recebe logs estruturados e distributed traces via OTLP.")
  System_Ext(r2, "Cloudflare R2", "Object storage compatível com S3. Armazena os XMLs de NF-e enviados pelos operadores para auditoria.")

  Rel(operador, srm, "Upload de NF-e, gestão de lotes, consulta de extrato", "HTTPS")
  Rel(srm, api_fx_primary, "Coleta cotação USD/BRL diariamente", "HTTPS/REST")
  Rel(srm, api_fx_secondary, "Fallback de cotação quando primária falha", "HTTPS/REST")
  Rel(srm, axiom, "Envia logs estruturados e traces distribuídos", "OTLP/HTTPS")
  Rel(srm, r2, "Persiste XMLs de NF-e para auditoria", "S3 API/HTTPS")

  UpdateLayoutConfig($c4ShapeInRow="3", $c4BoundaryInRow="1")
```

---

## Nível 2 — Container

Detalha os processos e datastores que compõem o sistema, a stack tecnológica de cada um e como se comunicam.

```mermaid
C4Container
  title Container Diagram — SRM Credit Engine

  Person(operador, "Operador", "Colaborador interno da SRM Asset")

  System_Boundary(srm_boundary, "SRM Credit Engine") {
    Container(frontend, "Frontend", "Next.js · Vercel", "Painel do operador: upload de NF-e, simulação de lotes com VP em tempo real, grid de transações com filtros dinâmicos.")

    Container(api, "REST API", "FastAPI · Python 3.12 · Vercel Serverless", "Autenticação JWT, ingestão de NF-e, motor de precificação (Strategy Pattern), gestão de recebíveis e lotes. OpenAPI/Swagger automático.")

    Container(worker, "Worker de Lotes", "Python · Docker · VPS", "Polling de lotes em status queued. Valida, precifica com taxa vigente e persiste transações atomicamente. Optimistic locking via campo version.")

    Container(cron, "Job de Câmbio", "Vercel Cron · FastAPI handler", "Executa diariamente. Coleta cotação USD/BRL com fallback automático. Marca taxa como stale se ambas as fontes falharem.")

    ContainerDb(db, "Banco de Dados", "PostgreSQL 16 · Neon (sa-east-1)", "Fonte única de verdade. Armazena recebíveis, lotes, transações, histórico de taxas de câmbio e parâmetros configuráveis do sistema.")
  }

  System_Ext(api_fx_primary, "API de Câmbio Primária", "AwesomeAPI / BCB")
  System_Ext(api_fx_secondary, "API de Câmbio Secundária", "Fallback")
  System_Ext(axiom, "Axiom", "Observabilidade OTLP")
  System_Ext(r2, "Cloudflare R2", "Object Storage")

  Rel(operador, frontend, "Acessa via browser", "HTTPS")
  Rel(frontend, api, "Chamadas REST autenticadas", "HTTPS / JSON")
  Rel(api, db, "Lê e persiste recebíveis, lotes, transações", "SQL / TLS")
  Rel(api, r2, "Upload e download de XMLs de NF-e", "S3 API / HTTPS")
  Rel(api, axiom, "Traces e logs via OpenTelemetry", "OTLP / HTTPS")
  Rel(cron, api, "Dispara job de cotação diariamente", "HTTPS / interno Vercel")
  Rel(cron, api_fx_primary, "GET cotação USD/BRL", "HTTPS / REST")
  Rel(cron, api_fx_secondary, "GET cotação USD/BRL (fallback)", "HTTPS / REST")
  Rel(worker, db, "Polling de lotes queued · persiste transações", "SQL / TLS")
  Rel(worker, axiom, "Traces e logs via OpenTelemetry", "OTLP / HTTPS")

  UpdateLayoutConfig($c4ShapeInRow="3", $c4BoundaryInRow="1")
```

---

## Decisões de arquitetura representadas nos diagramas

**Vercel Serverless para API e Frontend** — elimina gestão de servidor para o escopo do desafio. A API é stateless por design, compatível com execução serverless. Documentado no README (seção Arquitetura de Deploy).

**VPS com Docker para o Worker** — lotes exigem processamento com estado e polling contínuo, incompatível com o modelo de execução efêmera da Vercel. Worker vive fora do perímetro serverless com acesso direto ao banco. Ver [ADR-0003](./adrs/0003-sync-nfe-processing.md).

**Neon PostgreSQL** — PostgreSQL gerenciado com branching de banco para ambientes, sem custo de RDS. Mesma interface do PostgreSQL convencional — sem lock-in de API proprietária.

**Cloudflare R2** — zero egress fees vs. S3. API S3-compatível permite troca sem reescrita de código. XMLs são imutáveis após upload — R2 é append-only na prática.

**Axiom para observabilidade** — evita infraestrutura local de Prometheus/Grafana. Free tier cobre o volume do projeto. Aceita OTLP nativamente sem agent intermediário. Ver [AI_USAGE.md](../AI_USAGE.md) (seção de decisões vetadas).

**Job de câmbio como handler da API com Vercel Cron** — para o escopo atual, o cron da Vercel dispara um endpoint protegido da própria API. Em produção AWS, seria substituído por EventBridge Scheduler + Lambda dedicada, sem impacto no código do handler.
