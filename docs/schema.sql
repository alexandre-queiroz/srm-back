-- =============================================================================
-- SRM Credit Engine — DDL
-- PostgreSQL 15+
-- =============================================================================

-- ---------------------------------------------------------------------------
-- Currencies
-- ---------------------------------------------------------------------------
CREATE TABLE currencies (
    code   VARCHAR(3)  PRIMARY KEY,
    name   VARCHAR(50) NOT NULL,
    symbol VARCHAR(5)  NOT NULL
);

-- ---------------------------------------------------------------------------
-- System parameters (base rate and other global parameters)
-- ---------------------------------------------------------------------------
CREATE TABLE system_params (
    id          UUID           PRIMARY KEY DEFAULT gen_random_uuid(),
    key         VARCHAR(100)   NOT NULL UNIQUE,
    value       NUMERIC(15, 8) NOT NULL,
    description TEXT,
    updated_at  TIMESTAMPTZ    NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- Product types (receivable types) — configurable spreads
-- ---------------------------------------------------------------------------
CREATE TABLE product_types (
    id         UUID           PRIMARY KEY DEFAULT gen_random_uuid(),
    name       VARCHAR(100)   NOT NULL,
    spread     NUMERIC(10, 8) NOT NULL,
    is_active  BOOLEAN        NOT NULL DEFAULT TRUE,
    updated_at TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ    NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- Exchange rates — immutable history
-- ---------------------------------------------------------------------------
CREATE TABLE exchange_rates (
    id            UUID           PRIMARY KEY DEFAULT gen_random_uuid(),
    from_currency VARCHAR(3)     NOT NULL REFERENCES currencies(code),
    to_currency   VARCHAR(3)     NOT NULL REFERENCES currencies(code),
    rate          NUMERIC(15, 8) NOT NULL,
    source        VARCHAR(20)    NOT NULL,   -- 'primary' | 'secondary'
    is_stale      BOOLEAN        NOT NULL DEFAULT FALSE,
    collected_at  TIMESTAMPTZ    NOT NULL,
    created_at    TIMESTAMPTZ    NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_exchange_rates_different_currencies
        CHECK (from_currency <> to_currency)
);

-- ---------------------------------------------------------------------------
-- Users (internal operators)
-- ---------------------------------------------------------------------------
CREATE TABLE users (
    id            UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    email         VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    name          VARCHAR(100) NOT NULL,
    is_active     BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- Companies — assignors and drawees share the same CNPJ registry
-- Role is inferred by relation: batches.assignor_id = assignor, receivables.drawee_id = drawee
-- ---------------------------------------------------------------------------
CREATE TABLE companies (
    id         UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    cnpj       VARCHAR(14)  NOT NULL UNIQUE,
    name       VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- Batches — always a single assignor; atomic (fully approved or rejected)
-- ---------------------------------------------------------------------------
CREATE TABLE batches (
    id                UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    assignor_id       UUID        NOT NULL REFERENCES companies(id),
    user_id           UUID        NOT NULL REFERENCES users(id),
    status            VARCHAR(20) NOT NULL DEFAULT 'pending',  -- pending | queued | approved | rejected
    rejection_reasons JSONB,
    version           INTEGER     NOT NULL DEFAULT 0,           -- optimistic locking
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_batches_status
        CHECK (status IN ('pending', 'queued', 'approved', 'rejected'))
);

-- ---------------------------------------------------------------------------
-- Receivables — one row per installment; exist independently of batches
-- ---------------------------------------------------------------------------
CREATE TABLE receivables (
    id                  UUID           PRIMARY KEY DEFAULT gen_random_uuid(),
    assignor_id         UUID           NOT NULL REFERENCES companies(id),
    drawee_id           UUID           NOT NULL REFERENCES companies(id),
    product_type_id     UUID           NOT NULL REFERENCES product_types(id),

    -- NF-e identification
    invoice_key         VARCHAR(44)    NOT NULL,
    invoice_number      VARCHAR(9)     NOT NULL,
    series              VARCHAR(3)     NOT NULL,
    issued_at           DATE           NOT NULL,
    installment_number  VARCHAR(60)    NOT NULL,

    -- NF-e financial values
    products_value      NUMERIC(20, 8) NOT NULL,
    discount_value      NUMERIC(20, 8) NOT NULL DEFAULT 0,
    freight_value       NUMERIC(20, 8) NOT NULL DEFAULT 0,
    other_value         NUMERIC(20, 8) NOT NULL DEFAULT 0,
    face_value          NUMERIC(20, 8) NOT NULL,  -- installment value (vDup)
    currency_code       VARCHAR(3)     NOT NULL REFERENCES currencies(code),
    due_date            DATE           NOT NULL,

    -- Audit
    xml_storage_url     TEXT,
    status              VARCHAR(20)    NOT NULL DEFAULT 'available',  -- available | in_batch | anticipated
    created_at          TIMESTAMPTZ    NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_receivables_installment
        UNIQUE (invoice_key, installment_number),
    CONSTRAINT chk_receivables_status
        CHECK (status IN ('available', 'in_batch', 'anticipated')),
    CONSTRAINT chk_receivables_face_value_positive
        CHECK (face_value > 0),
    CONSTRAINT chk_receivables_assignor_drawee_different
        CHECK (assignor_id <> drawee_id)
);

-- ---------------------------------------------------------------------------
-- Batch items — join between batches and receivables
-- ---------------------------------------------------------------------------
CREATE TABLE batch_items (
    batch_id      UUID NOT NULL REFERENCES batches(id),
    receivable_id UUID NOT NULL REFERENCES receivables(id),

    PRIMARY KEY (batch_id, receivable_id)
);

-- ---------------------------------------------------------------------------
-- Transactions — confirmed liquidations with immutable parameter snapshot
-- ---------------------------------------------------------------------------
CREATE TABLE transactions (
    id                   UUID           PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id             UUID           NOT NULL REFERENCES batches(id),
    receivable_id        UUID           NOT NULL UNIQUE REFERENCES receivables(id),
    face_value           NUMERIC(20, 8) NOT NULL,
    present_value        NUMERIC(20, 8) NOT NULL,
    term_days            INTEGER        NOT NULL,
    spread_used          NUMERIC(10, 8) NOT NULL,
    base_rate_used       NUMERIC(10, 8) NOT NULL,
    instrument_currency  VARCHAR(3)     NOT NULL REFERENCES currencies(code),
    settlement_currency  VARCHAR(3)     NOT NULL REFERENCES currencies(code),
    exchange_rate_id     UUID           REFERENCES exchange_rates(id),
    exchange_rate_used   NUMERIC(15, 8),
    liquidated_at        TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    created_at           TIMESTAMPTZ    NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_transactions_term_positive
        CHECK (term_days > 0),
    CONSTRAINT chk_transactions_present_value_positive
        CHECK (present_value > 0),
    CONSTRAINT chk_transactions_exchange_rate_consistency
        CHECK (
            (instrument_currency = settlement_currency)
            OR
            (instrument_currency <> settlement_currency
             AND exchange_rate_id IS NOT NULL
             AND exchange_rate_used IS NOT NULL)
        )
);

-- =============================================================================
-- Indexes
-- =============================================================================

CREATE INDEX idx_exchange_rates_lookup
    ON exchange_rates (from_currency, to_currency, collected_at DESC)
    WHERE is_stale = FALSE;

CREATE INDEX idx_companies_cnpj         ON companies (cnpj);

CREATE INDEX idx_batches_assignor_id    ON batches (assignor_id);
CREATE INDEX idx_batches_status         ON batches (status);

CREATE INDEX idx_receivables_assignor_id ON receivables (assignor_id);
CREATE INDEX idx_receivables_drawee_id   ON receivables (drawee_id);
CREATE INDEX idx_receivables_status      ON receivables (status);

CREATE INDEX idx_batch_items_receivable_id ON batch_items (receivable_id);

CREATE INDEX idx_transactions_batch_id      ON transactions (batch_id);
CREATE INDEX idx_transactions_liquidated_at ON transactions (liquidated_at DESC);
CREATE INDEX idx_transactions_settlement_currency ON transactions (settlement_currency);

-- =============================================================================
-- Seed data
-- =============================================================================

INSERT INTO currencies (code, name, symbol) VALUES
    ('BRL', 'Brazilian Real', 'R$'),
    ('USD', 'US Dollar',      '$');

INSERT INTO system_params (key, value, description) VALUES
    ('monthly_base_rate', 0.01000000, 'Monthly base rate used in present value calculation (1% p.m.)');

INSERT INTO product_types (name, spread) VALUES
    ('Duplicata Mercantil', 0.01500000),
    ('Cheque Pré-datado',   0.02500000);
