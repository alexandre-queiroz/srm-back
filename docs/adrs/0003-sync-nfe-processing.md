# ADR 0003 — Processamento Síncrono de NF-e no Intake

**Status:** Aceito  
**Data:** 2026-05-12

## Contexto

O fluxo de ingestão de NF-e envolve parse do XML, upsert de empresas, upload para R2 e persistência de recebíveis. Em produção real, esse pipeline deveria incluir validação junto à SEFAZ (autenticidade da chave e situação da nota) e, dependendo do produto, consulta ao BACEN para verificação de restrições.

A arquitetura ideal para esse cenário seria:

```
POST /receivables/upload
  → salva o XML no R2
  → cria xml_uploads com status "pending"
  → enfileira job (SQS, RabbitMQ, ou polling no banco)
  → retorna 202 Accepted

Worker (background)
  → consome o job
  → valida na SEFAZ
  → processa duplicatas
  → atualiza xml_uploads para "processed" | "failed"
  → notifica via webhook ou polling do front
```

Esse modelo desacopla a latência das integrações externas do tempo de resposta da API e permite retry automático em caso de falha transitória.

## Alternativa considerada: BackgroundTasks do FastAPI

O FastAPI oferece `BackgroundTasks` — executa código após o response ser enviado, permitindo retornar `202 Accepted` imediatamente. Essa abordagem foi avaliada e **descartada** por incompatibilidade com o ambiente de deploy:

> O Vercel encerra a função serverless assim que o response HTTP é enviado. O `BackgroundTasks` depende do processo estar vivo para completar a execução — sem essa garantia, o processamento seria silenciosamente perdido em produção.

Esse padrão funcionaria em ambientes com processo persistente (uvicorn em VPS ou ECS), mas não em Vercel Functions.

## Decisão

Processar de forma **síncrona no request** com retorno `201 Created`:

1. **Serverless impõe o limite** — não há processo persistente no Vercel após o response; qualquer solução assíncrona exigiria infraestrutura externa (fila + worker)
2. **Ausência de integrações externas reais** — sem SEFAZ nem BACEN, não há latência imprevisível que justifique desacoplamento
3. **Worker já existe na VPS** — `lote_processor.py` e `docker-compose.vps.yml` demonstram que o padrão assíncrono é dominado; o intake de NF-e pode migrar para o mesmo worker quando houver validação real
4. **Modelo de dados pronto para evolução** — `xml_uploads.status` suporta `pending` sem migração destrutiva; `xml_upload_id` nos recebíveis garante rastreabilidade

## Caminho de evolução para produção real

```
POST /receivables/upload
  → salva XML no R2
  → cria xml_uploads com status "pending" → retorna 202 Accepted

VPS Worker (polling em xml_uploads WHERE status = 'pending')
  → valida chave na SEFAZ
  → verifica restrições no BACEN
  → processa duplicatas
  → atualiza status para "processed" | "failed"
  → dispara webhook notificando o operador do resultado
```

Esse modelo reutiliza o padrão já estabelecido para processamento de lotes e não exige infraestrutura adicional além do worker existente.

## Consequências

- `POST /receivables/upload` retorna `201` com resultado completo do processamento
- Latência do endpoint é proporcional ao número de duplicatas no XML — aceitável para notas com até ~50 parcelas
- A migração para `202 + worker` é não-destrutiva: adicionar `pending` ao check constraint de `xml_uploads.status` e mover a lógica de processamento para o worker são as únicas mudanças necessárias
