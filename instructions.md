# Pipeline Instructions

## Prerequisites
- Docker Desktop running
- Python 3.10+
- Java 11 or 17 (required by PySpark — `java -version` to check)
- **Windows only:** set `HADOOP_HOME` to a folder containing `winutils.exe` and `hadoop.dll`

---

## 1 — Setup (once)

```bash
cp binance-pipeline/.env.example binance-pipeline/.env
cd binance-pipeline && pip install -r requirements.txt
```

---

## 2 — Start Docker (Kafka + TimescaleDB + Grafana)

```bash
cd binance-pipeline/docker
docker compose up -d
```

Wait ~15 seconds, then verify:

```bash
docker compose ps
```

All containers should show `running` (kafka-init will show `exited 0`).

---

## 3 — Start the 3 Pipeline Processes

Open **3 separate terminals**, all from `binance-pipeline/`:

**Terminal 1 — Ingestion (Binance WebSocket → Kafka)**
```bash
cd binance-pipeline
python -m ingestion.ws_consumer
```

**Terminal 2 — Consumer (Kafka → TimescaleDB raw tables)**
```bash
cd binance-pipeline
python -m consumer.worker
```

**Terminal 3 — Spark Streaming (Kafka → metrics tables)**
```bash
cd binance-pipeline
python -m spark.streaming_job
```

Spark takes ~20 seconds to start.

---

## 4 — Test Each Part

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

## 5 — Receive Email Alerts

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

## 6 — Run on a Subset (demo)

To reduce volume and see data evolve quickly, edit `binance-pipeline/.env`:

```env
SYMBOLS=BTCUSDT
CONSUMER_BATCH_SIZE=20
CONSUMER_FLUSH_INTERVAL=1.0
```

Then restart the 3 processes. DB rows will appear every ~1 second.

---

## 6 — Stop

`Ctrl+C` in each terminal, then:

```bash
cd binance-pipeline/docker
docker compose down
```
