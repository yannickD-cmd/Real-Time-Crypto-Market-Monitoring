# Pipeline Instructions

## Prerequisites
- Docker Desktop running

---

## 1 — Setup (once)

```bash
cp binance-pipeline/.env.example binance-pipeline/.env
```

---

## 2 — Start Everything

```bash
cd binance-pipeline/docker
docker compose up -d
```

Docker will start all services in the correct order and print a status message when ready:

```
========================================
  [OK] Step 1 — Kafka + TimescaleDB + Grafana   Ready
  [OK] Step 2 — Ingestion (Binance -> Kafka)    Started
  [OK] Step 3 — Consumer (Kafka -> TimescaleDB) Started
  [OK] Step 4 — Spark (Kafka -> Metrics)        Started
----------------------------------------
  Grafana:   http://localhost:3001  (admin / admin)
  Kafka UI:  http://localhost:8080
========================================
```

To see this message run:
```bash
docker compose logs ready
```

> **First run only:** Docker builds the Python image and downloads ~500MB of dependencies. Takes 3–5 minutes. Subsequent runs are instant.

---

## 3 — Verify Each Part

**Kafka — check messages are flowing:**
Open `http://localhost:8080` → Topics → `binance.trades` → Messages tab.

**TimescaleDB — check raw data is landing:**
```bash
psql -h localhost -p 5433 -U crypto -d crypto
```
```sql
SELECT event_time, symbol, price FROM trades ORDER BY event_time DESC LIMIT 5;
```

**TimescaleDB — check metrics are being computed (after ~60s):**
```sql
SELECT window_start, symbol, round(vwap::numeric,2) AS vwap, trade_count
FROM trade_metrics ORDER BY window_start DESC LIMIT 6;
```

**Grafana — check live dashboards:**
Open `http://localhost:3001` (admin / admin) → Dashboards → Market Overview.

---

## 4 — Receive Email Alerts

Open `binance-pipeline/.env` and fill in your email details:

```env
GRAFANA_ALERT_EMAIL=you@example.com
GF_SMTP_ENABLED=true
GF_SMTP_HOST=smtp.gmail.com:587
GF_SMTP_USER=you@gmail.com
GF_SMTP_PASSWORD=your_app_password
GF_SMTP_FROM_ADDRESS=you@gmail.com
```

> **Gmail:** go to Google Account → Security → App Passwords and generate a password for "Mail".
> Use that as `GF_SMTP_PASSWORD`, not your normal Gmail password.

Then restart Docker so Grafana picks up the new values:

```bash
cd binance-pipeline/docker
docker compose restart grafana
```

Alerts fire automatically when:
- `volatility_alert = true` is sustained for 1 minute (price stddev spike)
- `spread_warning = true` is sustained for 1 minute (bid-ask spread anomaly)

---

## 5 — Run on a Subset (demo)

To reduce volume and see data evolve quickly, edit `binance-pipeline/.env`:

```env
SYMBOLS=BTCUSDT
CONSUMER_BATCH_SIZE=20
CONSUMER_FLUSH_INTERVAL=1.0
```

Then restart:
```bash
docker compose restart ingestion consumer spark
```

DB rows will appear every ~1 second.

---

## 6 — Stop

```bash
cd binance-pipeline/docker
docker compose down
```
