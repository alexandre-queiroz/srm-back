# ADR 0001 — Controle de Concorrência: Optimistic Locking vs Fila de Processamento

- **Status:** Aceito
- **Data:** 2026-05-12

## Contexto

A liquidação de um lote é uma operação atômica e financeiramente crítica. Em um cenário de múltiplos operadores simultâneos, duas requisições poderiam tentar liquidar o mesmo lote ao mesmo tempo, resultando em inconsistência de dados ou dupla liquidação.

## Decisão

Utilizamos **Optimistic Locking** via coluna `lotes.version` (incrementada a cada atualização). Antes de confirmar a liquidação, a aplicação verifica se a versão do registro não foi alterada desde a leitura. Se houver conflito, a operação retorna erro e o cliente pode fazer retry.

## Alternativa Considerada

**Fila de processamento síncrona** (ex: Redis + worker dedicado) serializa todas as liquidações por design — apenas um worker processa por vez, eliminando conflitos. É a abordagem indicada para alto volume concorrente.

## Trade-off

| Critério | Optimistic Locking | Fila de Processamento |
|---|---|---|
| Complexidade | Baixa — só uma coluna no banco | Alta — Redis, worker, gerenciamento de fila |
| Infraestrutura adicional | Nenhuma | Redis + serviço worker |
| Conflitos frequentes | Penaliza (retry custoso) | Lida bem |
| Conflitos raros | Ideal | Over-engineering |
| Escalabilidade | Limitada | Alta |

## Justificativa

Lotes são criados por operador humano e confirmados manualmente. Conflito simultâneo no mesmo lote é um edge case, não a regra de operação. Adicionar fila sem evidência de necessidade seria over-engineering para o volume atual.

## Caminho de Evolução para Alta Escala

Em um cenário de **1 milhão de transações/minuto**, optimistic locking se torna um gargalo — o volume de retries sob contenção degrada a throughput. A evolução natural seria:

1. **Fila por cedente** — cada cedente tem sua própria fila, paralelismo sem conflito entre lotes de cedentes distintos
2. **Workers stateless** — múltiplos workers consomem a fila, escalados horizontalmente
3. **Consistência eventual** — o status do lote é atualizado de forma assíncrona; o operador recebe confirmação via webhook ou polling
4. **Sharding do banco** — particionamento por cedente ou por data para distribuir carga de escrita
5. **Cache de parâmetros** — `product_types`, `system_params` e `exchange_rates` são lidos em cada liquidação; em alto volume, um cache (Redis) elimina round-trips desnecessários ao banco

Esta evolução será discutida na call de alinhamento de arquitetura em 2026-05-13.
