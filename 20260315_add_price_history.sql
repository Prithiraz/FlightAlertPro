-- Migration: price_history table
-- Records the cheapest price observed for a route during each search or worker poll.
-- Used by the /api/price-history endpoint to show price trends.

CREATE TABLE IF NOT EXISTS price_history (
    id          BIGSERIAL PRIMARY KEY,
    from_iata   CHAR(3)        NOT NULL,
    to_iata     CHAR(3)        NOT NULL,
    price       NUMERIC(10, 2) NOT NULL,
    currency    CHAR(3)        NOT NULL DEFAULT 'USD',
    source      VARCHAR(50)    NOT NULL DEFAULT 'search',  -- 'search' | 'worker' | 'manual'
    recorded_at TIMESTAMPTZ    NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_price_history_route
    ON price_history (from_iata, to_iata, currency, recorded_at DESC);
