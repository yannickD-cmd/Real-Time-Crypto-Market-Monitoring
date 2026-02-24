-- Enable the TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- ---------------------------------------------------------------------------
-- trades table
-- Stores both "trade" and "aggTrade" events from the binance.trades topic.
-- trade_id: field "t" for plain trades, "a" for aggTrade events.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS trades (
    event_time          TIMESTAMPTZ     NOT NULL,   -- field "T" (trade time ms → UTC)
    ingestion_timestamp TIMESTAMPTZ     NOT NULL,   -- stamped by ingestion layer
    symbol              TEXT            NOT NULL,   -- field "s"
    event_type          TEXT            NOT NULL,   -- "trade" or "aggTrade"
    trade_id            BIGINT          NOT NULL,   -- "t" for trade, "a" for aggTrade
    price               NUMERIC(20, 8)  NOT NULL,   -- field "p"
    quantity            NUMERIC(20, 8)  NOT NULL,   -- field "q"
    is_buyer_maker      BOOLEAN         NOT NULL,   -- field "m"
    -- aggTrade-only fields (NULL for plain trade events)
    first_trade_id      BIGINT,                     -- field "f"
    last_trade_id       BIGINT,                     -- field "l"
    -- TimescaleDB requires the partition column (event_time) to be part of
    -- any unique constraint so uniqueness can be enforced within each chunk.
    UNIQUE (event_time, symbol, trade_id)
);

-- Convert to a hypertable partitioned by event_time with 1-day chunks.
SELECT create_hypertable(
    'trades',
    'event_time',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE
);

-- Index for the most common access pattern: per-symbol time-range queries.
CREATE INDEX IF NOT EXISTS idx_trades_symbol_time
    ON trades (symbol, event_time DESC);

-- ---------------------------------------------------------------------------
-- book_ticker table
-- Stores bookTicker events from the binance.book_ticker topic.
-- update_id ("u") is the unique identifier per Binance exchange update.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS book_ticker (
    ingestion_timestamp TIMESTAMPTZ     NOT NULL,   -- hypertable time axis
    symbol              TEXT            NOT NULL,   -- field "s"
    update_id           BIGINT          NOT NULL,   -- field "u"
    best_bid_price      NUMERIC(20, 8)  NOT NULL,   -- field "b"
    best_bid_qty        NUMERIC(20, 8)  NOT NULL,   -- field "B"
    best_ask_price      NUMERIC(20, 8)  NOT NULL,   -- field "a"
    best_ask_qty        NUMERIC(20, 8)  NOT NULL,   -- field "A"
    -- TimescaleDB requires the partition column (ingestion_timestamp) to be
    -- part of any unique constraint.
    UNIQUE (ingestion_timestamp, symbol, update_id)
);

SELECT create_hypertable(
    'book_ticker',
    'ingestion_timestamp',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE
);

CREATE INDEX IF NOT EXISTS idx_book_ticker_symbol_time
    ON book_ticker (symbol, ingestion_timestamp DESC);
