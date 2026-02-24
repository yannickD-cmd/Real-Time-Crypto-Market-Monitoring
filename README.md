# Real-Time Crypto Market Monitoring

A full end-to-end streaming pipeline that ingests live Binance market data, processes it with PySpark, stores it in TimescaleDB, and visualises it in Grafana with email alerting.

---

## Architecture

```
Binance WebSocket
      │  9 streams (BTC/ETH/BNB × trade/aggTrade/bookTicker)
      ▼
 Kafka Broker          ← decouples ingestion from storage
      │
      ├──▶ Consumer Worker   → TimescaleDB  (raw ticks)
      │
      └──▶ PySpark Streaming → TimescaleDB  (1-min VWAP, volatility, spread metrics)
                                    │
                               Grafana  (live dashboards + email alerts)
```

**4 phases:**

| Phase | What it does |
|-------|-------------|
| 1 — Ingestion | WebSocket → Kafka (live Binance events, <1s latency) |
| 2 — Buffering | Kafka → TimescaleDB raw tables (500-msg or 2s batches) |
| 3 — Stream Processing | Spark computes VWAP, volatility, spread per 1-min window |
| 4 — Visualisation | Grafana dashboards + email alerts on anomaly flags |

---

## Requirements

- [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- Python 3.11+
- Java 17+ (for PySpark)
- `winutils.exe` + `hadoop.dll` in `C:\Users\<you>\bin` (Windows only)

---

## Quick Start

### 1 — Clone and configure

```bash
git clone https://github.com/yannickD-cmd/Real-Time-Crypto-Market-Monitoring.git
cd Real-Time-Crypto-Market-Monitoring/binance-pipeline
cp .env.example .env
# Edit .env — fill in your SMTP credentials for email alerts
```

### 2 — Start Docker services

```bash
cd docker
docker compose up -d
```

This starts: **Kafka · ZooKeeper · Kafka-UI · TimescaleDB · Grafana**

### 3 — Start the Python pipeline (3 terminals)

**Terminal 1 — Binance → Kafka**
```bash
cd binance-pipeline
.venv-1/Scripts/python.exe -m ingestion.ws_consumer      # Windows
# python -m ingestion.ws_consumer                         # Linux/Mac
```

**Terminal 2 — Kafka → TimescaleDB (raw data)**
```bash
cd binance-pipeline
.venv-1/Scripts/python.exe -m consumer.worker
```

**Terminal 3 — Spark metrics (VWAP, volatility, spreads)**
```bash
cd binance-pipeline
.venv-1/Scripts/python.exe -m spark.streaming_job
```

### 4 — Open dashboards

| Tool | URL | Credentials |
|------|-----|-------------|
| **Grafana** — live dashboards | http://localhost:3000 | admin / admin |
| **Kafka-UI** — message browser | http://localhost:8080 | — |
| **Spark UI** — streaming progress | http://localhost:4040 | — |

---

## Dashboards

### Market Overview (`/d/market-overview`)
One row per symbol (BTC / ETH / BNB), each with:
- VWAP time-series (Volume-Weighted Average Price)
- Trade count per minute
- Average bid-ask spread

Auto-refreshes every **10 seconds**.

### Risk Monitor (`/d/risk-monitor`)
- **Stat panels**: Volatility Alerts / Volume Spikes / Spread Warnings — green = 0, red ≥ 1
- **Anomaly timeline**: stddev chart showing only windows where alert fired
- **Events table**: full list of anomaly events (time, symbol, type, VWAP, stddev)

---

## Alerting

Two alert rules evaluate every **30 seconds** and fire after **1 minute** of sustained condition:

| Rule | Fires when |
|------|-----------|
| `VolatilityAlert` | `price_stddev > 2.0` in any 1-min window |
| `SpreadWarning` | `avg_spread > 3 × min_spread` in any 30-sec window |

Notifications sent via email (configure SMTP in `.env`).

---

## Stopping

```bash
# Ctrl+C in each terminal, then:
cd binance-pipeline/docker
docker compose down
```

---

## Project Structure

```
binance-pipeline/
├── ingestion/          Phase 1 — WebSocket consumer + Kafka producer
├── consumer/           Phase 2 — Kafka consumer + TimescaleDB bulk writer
├── spark/              Phase 3 — PySpark Structured Streaming job
├── docker/
│   ├── docker-compose.yml
│   ├── init-db.sql
│   └── grafana/        Phase 4 — Grafana provisioning + dashboards
├── .env.example        Template — copy to .env and fill in credentials
├── requirements.txt
├── architecture.md     Full ASCII pipeline diagram
└── documentation.md    All design decisions explained
```
