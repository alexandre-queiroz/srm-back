# ADR 0002 — ORM e Migrations: SQLAlchemy 2.0 (sync) + Alembic

- **Status:** Aceito
- **Data:** 2026-05-12

## Contexto

Precisávamos escolher a estratégia de acesso ao banco e gerenciamento de migrations para o projeto FastAPI.

## Decisão

**SQLAlchemy 2.0 (modo síncrono)** para ORM e queries, com **SQL nativo via `sqlalchemy.text()`** para relatórios e queries analíticas. **Alembic** para migrations versionadas.

## Alternativa Considerada

**SQLAlchemy 2.0 async (asyncpg)** — integração nativa com o event loop do FastAPI, sem uso de thread pool.

## Trade-off

| Critério | Sync | Async |
|---|---|---|
| Complexidade | Baixa | Alta |
| Gerenciamento de sessão | Simples | Context managers async em toda camada |
| Debug e rastreamento | Direto | Stack traces mais complexos |
| Performance no volume atual | Suficiente | Sem ganho prático |
| Fit com FastAPI | Via thread pool (automático) | Nativo |

## Justificativa

O volume esperado de operações não justifica a complexidade de async em toda a camada de persistência. FastAPI gerencia rotas síncronas via thread pool automaticamente — sem bloqueio do event loop. Async valeria a pena em sistemas com alta concorrência de I/O, o que não é o caso aqui.

A escolha reflete o princípio de não aumentar a complexidade sem evidência de necessidade.

## Migrations

O `docs/schema.sql` construído durante o design serve como referência. A migration `0001_initial_schema` reproduz esse schema via Alembic, garantindo versionamento rastreável e rollback seguro.
