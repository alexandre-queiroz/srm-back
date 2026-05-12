# AI Usage — SRM Credit Engine (Backend)

Este documento descreve como a IA (Claude) foi utilizada como co-piloto no desenvolvimento deste projeto, conforme exigido pela política de uso de IA da SRM Asset.

---

## Como a IA foi utilizada

A IA não foi utilizada para geração cega de código. O processo foi colaborativo e orientado por decisões técnicas tomadas em conjunto, com raciocínio explícito a cada etapa.

O fluxo de trabalho seguiu esta ordem:

1. **Leitura e interpretação do desafio** — a IA leu o case e resumiu os requisitos, identificando lacunas e ambiguidades que o documento não resolvia explicitamente (sacado único ou múltiplos? fundo único ou múltiplos? input manual ou em lote?).

2. **Clarificação de domínio de negócio** — antes de qualquer código, foram feitas perguntas sobre o negócio: o fluxo do usuário, o que é um lote, como funciona a antecipação, qual a relação entre cedente e sacado. Isso evitou uma modelagem errada desde o início.

3. **Definição de requisitos** — os requisitos funcionais e não funcionais foram construídos iterativamente com base nas respostas, não copiados do enunciado. Decisões como validação assíncrona de lotes, tabela de parâmetros configuráveis e histórico imutável de câmbio foram levantadas pela IA e validadas pelo autor.

4. **Modelagem de dados** — o schema foi construído coluna a coluna, com justificativa para cada decisão de design (desnormalização intencional, optimistic locking, constraints no banco).

5. **Scaffolding do projeto** — estrutura de pastas, modelos SQLAlchemy, schemas Pydantic e configuração de infraestrutura gerados com validação de importação automatizada.

6. **Decisões arquiteturais** — cada decisão relevante foi documentada em ADRs com trade-offs explícitos.

---

## Decisões onde o autor vetou a sugestão da IA

### 1. Tabelas separadas para `cedentes` e `sacados`

**Sugestão inicial da IA:** criar duas tabelas distintas — `cedentes` e `sacados` — por simplicidade e explicitidade de papel.

**Veto do autor:** o autor identificou que no domínio real de FIDCs, o mesmo CNPJ pode ser cedente em uma operação e sacado em outra. Manter duas tabelas criaria risco real de duplicidade de cadastro, dados divergentes para o mesmo CNPJ e inconsistência de auditoria.

**Decisão final:** tabela única `companies`. O papel de cada empresa é inferido pela relação — `batches.assignor_id` indica cedente, `receivables.drawee_id` indica sacado. A IA reconheceu a correção do argumento e refatorou o modelo.

**Impacto:** eliminação de risco de inconsistência de dados em produção. Modelo mais alinhado com a realidade do negócio.

---

### 2. Nomes de colunas em português no banco

**Situação:** durante a modelagem, as primeiras versões do schema e dos models SQLAlchemy usavam nomes em português (`cedente_id`, `valor_face`, `prazo_dias`, `moeda_titulo`, `nota_fiscal_key`, etc.), misturados com campos já em inglês (`created_at`, `is_stale`, `spread`).

**Veto do autor:** o autor identificou a inconsistência — o banco estava com dois idiomas misturados, o que é confuso para qualquer engenheiro que entre no projeto e não fala português.

**Decisão final:** padronização total em inglês no banco de dados e no código. Português ficou restrito à documentação (ADRs, README, comentários explicativos), que é destinada ao time.

**Impacto:** consistência total no schema. Convenção clara: código e banco em inglês, documentação de negócio em português.

---

### 3. Subir Prometheus e Grafana localmente ao invés de usar serviço externo

**Sugestão inicial da IA:** incluir Prometheus e Grafana no `docker-compose.yml` para observabilidade local, com um arquivo `infra/prometheus.yml` de configuração.

**Veto do autor:** o autor questionou a necessidade de hospedar infraestrutura de observabilidade quando existem serviços cloud prontos que aceitam OpenTelemetry diretamente. Subir Prometheus e Grafana localmente adiciona peso ao ambiente de desenvolvimento sem benefício real — e em produção exigiria hospedagem e manutenção desses serviços.

**Decisão final:** uso do **Axiom** como destino de logs e traces via OpenTelemetry. O `docker-compose.yml` ficou enxuto (apenas API + banco). O `app/core/observability.py` exporta traces diretamente para o endpoint OTLP do Axiom.

**Impacto:** ambiente local mais leve. Observabilidade de produção sem infraestrutura adicional para manter. Free tier do Axiom cobre o volume do projeto.

---

## Onde a IA economizou tempo

- **Scaffolding completo da estrutura de pastas** com 60+ arquivos criados e validados em minutos
- **Geração e validação dos models SQLAlchemy 2.0** com tipagem forte, constraints e relacionamentos
- **Schemas Pydantic** com separação clara de request/response e validadores
- **DDL completo** com indexes, constraints e seed data alinhados ao modelo de negócio
- **ADRs** com estrutura de trade-off para cada decisão arquitetural
- **Pesquisa de limites de planos** (Vercel Cron, Neon free tier) em tempo real durante o design de infraestrutura

## Onde a IA precisou de correção

- **Modelagem inicial de cedente/sacado** — sugeriu separação que não refletia o domínio real
- **Consistência de idioma no banco** — não sinalizou proativamente a mistura de português e inglês nas colunas
- **Over-engineering de observabilidade** — sugeriu infraestrutura local antes de considerar serviços gerenciados
- **Status do recebível** — primeira versão usava `pending/anticipated` sem o estado intermediário `in_batch`, que é necessário para bloquear o recebível durante o processamento do lote

---

## Análise crítica

A IA foi mais útil como **acelerador de implementação** do que como **arquiteto de domínio**. As decisões de negócio mais importantes — como o fluxo de antecipação, a unicidade de empresas e o processamento assíncrono de lotes — vieram do autor. A IA executou e documentou essas decisões com precisão.

O maior risco no uso de IA em projetos financeiros é aceitar sugestões de modelagem sem questionar o domínio. Neste projeto, o autor questionou ativamente, o que resultou em um modelo mais próximo da realidade operacional de um FIDC.
