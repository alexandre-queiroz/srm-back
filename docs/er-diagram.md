# ER Diagram — SRM Credit Engine

```mermaid
erDiagram
    currencies {
        varchar(3)      code        PK
        varchar(50)     name
        varchar(5)      symbol
    }

    system_params {
        uuid            id          PK
        varchar(100)    key         UK
        numeric         value
        text            description
        timestamptz     updated_at
    }

    product_types {
        uuid            id          PK
        varchar(100)    name
        numeric         spread
        boolean         is_active
        timestamptz     updated_at
        timestamptz     created_at
    }

    exchange_rates {
        uuid            id              PK
        varchar(3)      from_currency   FK
        varchar(3)      to_currency     FK
        numeric         rate
        varchar(20)     source
        boolean         is_stale
        timestamptz     collected_at
        timestamptz     created_at
    }

    users {
        uuid            id              PK
        varchar(255)    email           UK
        varchar(255)    password_hash
        varchar(100)    name
        boolean         is_active
        timestamptz     created_at
    }

    companies {
        uuid            id              PK
        varchar(14)     cnpj            UK
        varchar(255)    social_reason
        varchar(255)    fantasy_name
        timestamptz     created_at
    }

    batches {
        uuid            id                  PK
        uuid            assignor_id         FK "companies"
        uuid            user_id             FK
        varchar(20)     status
        jsonb           rejection_reasons
        integer         version
        timestamptz     created_at
        timestamptz     updated_at
    }

    receivables {
        uuid            id                  PK
        uuid            xml_upload_id       FK "nullable"
        uuid            assignor_id         FK "companies"
        uuid            drawee_id           FK "companies"
        uuid            product_type_id     FK
        varchar(44)     invoice_key
        varchar(9)      invoice_number
        varchar(3)      series
        date            issued_at
        varchar(60)     installment_number
        numeric         products_value
        numeric         discount_value
        numeric         freight_value
        numeric         other_value
        numeric         face_value
        varchar(3)      currency_code       FK
        date            due_date
        text            xml_storage_url
        text            error_message
        varchar(20)     status
        timestamptz     created_at
    }

    xml_uploads {
        uuid            id                  PK
        uuid            user_id             FK
        varchar(255)    filename
        varchar(20)     status
        text            error_message
        text            xml_storage_url
        integer         receivables_created
        timestamptz     created_at
    }

    batch_items {
        uuid            batch_id        PK "FK"
        uuid            receivable_id   PK "FK"
    }

    transactions {
        uuid            id                      PK
        uuid            batch_id                FK
        uuid            receivable_id           FK "UK"
        numeric         face_value
        numeric         present_value
        integer         term_days
        numeric         spread_used
        numeric         base_rate_used
        varchar(3)      instrument_currency     FK
        varchar(3)      settlement_currency     FK
        uuid            exchange_rate_id        FK
        numeric         exchange_rate_used
        timestamptz     liquidated_at
        timestamptz     created_at
    }

    currencies        ||--o{ exchange_rates  : "from_currency"
    currencies        ||--o{ exchange_rates  : "to_currency"
    currencies        ||--o{ receivables     : "currency_code"
    currencies        ||--o{ transactions    : "instrument_currency"
    currencies        ||--o{ transactions    : "settlement_currency"
    companies         ||--o{ batches         : "assignor"
    companies         ||--o{ receivables     : "assignor"
    companies         ||--o{ receivables     : "drawee"
    users             ||--o{ batches         : "creates"
    batches           ||--o{ batch_items     : "groups"
    receivables       ||--o{ batch_items     : "included in"
    batches           ||--o{ transactions    : "generates"
    product_types     ||--o{ receivables     : "types"
    receivables       ||--|| transactions    : "liquidated as"
    exchange_rates    ||--o{ transactions    : "rate used"
    users             ||--o{ xml_uploads    : "uploads"
    xml_uploads       ||--o{ receivables   : "originates"
```

## Decisões de Modelagem

**`system_params`** armazena parâmetros globais como `monthly_base_rate` como registros chave-valor. Alterações não exigem redeploy.

**`product_types.spread`** é configurável em banco. O Strategy Pattern no código seleciona a regra por tipo, mas o valor do spread é sempre lido da tabela.

**`exchange_rates`** mantém histórico completo. `is_stale = true` sinaliza que a coleta falhou e o valor pode estar desatualizado. Operações cross-currency com taxa stale são bloqueadas.

**`transactions.exchange_rate_id + exchange_rate_used`** desnormalização intencional: `exchange_rate_id` garante rastreabilidade do registro histórico; `exchange_rate_used` congela o valor usado no cálculo para que o extrato nunca dependa de join para ser auditado — mesmo que o registro da taxa seja deletado ou corrigido no futuro.

**`batches.version`** habilita optimistic locking — previne que duas liquidações concorrentes do mesmo lote sejam processadas simultaneamente.

**`batches.rejection_reasons`** em JSONB permite retornar múltiplos motivos de recusa de forma estruturada sem normalização excessiva.

**`receivables`** existem de forma independente de lotes. Uma linha por duplicata — uma NF-e pode gerar múltiplas duplicatas com vencimentos distintos. A unicidade é garantida por `(invoice_key, installment_number)`.

**`receivables.assignor_id`** desnormalização intencional — o cedente está direto no recebível para evitar join obrigatório em toda listagem e extrato.

**`receivables.status`** ciclo de vida: `available` (elegível) → `in_batch` (bloqueado em solicitação pendente) → `anticipated` (liquidado). Rejeição de lote devolve para `available`.

**`receivables.xml_storage_url`** nullable — link ao XML original no R2 para auditoria. Preenchido apenas quando o upload é bem-sucedido.

**`xml_uploads`** lote de upload — um registro por ação do operador. `status = failed` indica que o XML era completamente ilegível (parse impossível). `receivables_created` permite auditoria rápida sem join.

**`receivables.xml_upload_id`** nullable — vincula o recebível ao lote de upload de origem. Ausente em recebíveis criados por outros canais futuros.

**`receivables.status = invalid`** recebível parseável mas com violação de regra de negócio (valor zero, CNPJ inválido, duplicata já existente). O campo `error_message` descreve o motivo. Recebíveis inválidos são visíveis ao operador mas nunca elegíveis para lotes de antecipação.

**`batch_items`** join table entre lotes e recebíveis. Desacopla a existência do recebível da solicitação de antecipação — suporta futuros canais de entrada sem XML.

**`companies`** unifica cedentes e sacados. O papel é inferido pela relação — `batches.assignor_id` e `receivables.assignor_id` indicam cedente; `receivables.drawee_id` indica sacado. O mesmo CNPJ pode exercer os dois papéis sem duplicidade de cadastro.
