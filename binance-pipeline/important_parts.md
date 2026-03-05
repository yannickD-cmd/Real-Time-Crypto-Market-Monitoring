# Critical Pipeline Steps

## 1. Stream Ingestion — "The 9 Streams"

Where symbols and stream types are declared (3 × 3 = 9 streams):
- `ingestion/config.py` lines 9–11

Where the single combined WebSocket URL is built and the connection is opened:
- `ingestion/ws_consumer.py` lines 59–64 — `_build_stream_url()`
- `ingestion/ws_consumer.py` lines 82–100 — `consume()` loop, listens to all 9 streams on one socket

---

## 2. Event Routing — Topic Assignment

Where the stream-to-topic mapping is defined:
- `ingestion/ws_consumer.py` lines 25–29 — `STREAM_TOPIC_MAP` dict

Where each incoming event is routed to the correct Kafka topic:
- `ingestion/ws_consumer.py` lines 67–70 — `_route_topic()`
- `ingestion/ws_consumer.py` lines 97–99 — called inside `consume()`, result passed to `producer.send()`

---

## 3. Partition Handling — Kafka Key

Where the symbol is used as the Kafka partition key:
- `ingestion/ws_consumer.py` line 97 — symbol extracted from event data
- `ingestion/kafka_producer.py` lines 35–43 — `send()`, symbol encoded as `key=`

This guarantees all events for the same symbol always hash to the same partition, preserving order.

---

## 4. PySpark Jobs — Stream Processing

Where the SparkSession is created:
- `spark/streaming_job.py` lines 171–187 — `_build_spark()`

Where the trade metrics streaming query is built (reads `binance.trades`, 1-min tumbling window):
- `spark/streaming_job.py` lines 194–278 — `_build_trade_query()`

Where the spread metrics streaming query is built (reads `binance.book_ticker`, 30-sec tumbling window):
- `spark/streaming_job.py` lines 285–334 — `_build_spread_query()`

Where results are written to TimescaleDB:
- `spark/streaming_job.py` lines 88–130 — `_write_trade_metrics()`
- `spark/streaming_job.py` lines 133–164 — `_write_spread_metrics()`

Where both queries are started and kept alive:
- `spark/streaming_job.py` lines 341–352 — `run()`

---

## 5. Alerting — Grafana Provisioned Rules

Where the two alert rules are defined (evaluated every 30s, fire after 1 minute sustained):
- `docker/grafana/provisioning/alerting/rules.yaml` lines 10–49 — **Volatility Alert**
  - Queries `trade_metrics` for rows where `volatility_alert = true` in the last 1 minute
  - Condition: count > 0 → fires
- `docker/grafana/provisioning/alerting/rules.yaml` lines 51–90 — **Spread Warning**
  - Queries `spread_metrics` for rows where `spread_warning = true` in the last 1 minute
  - Condition: count > 0 → fires

Where the alert flags are originally set (upstream, in PySpark):
- `spark/streaming_job.py` lines 251–268 — `volatility_alert` flag written to `trade_metrics`
- `spark/streaming_job.py` lines 321–325 — `spread_warning` flag written to `spread_metrics`

Where the contact point (email destination) is configured:
- `docker/grafana/provisioning/alerting/contact_points.yaml` lines 1–19 — `email-alerts` contact point, address read from `$GRAFANA_ALERT_EMAIL` env var

Where the notification routing policy is defined (grouping, timing):
- `docker/grafana/provisioning/alerting/notification_policies.yaml` lines 1–9
  - Grouped by `alertname` + `symbol`
  - Wait 30s before first send, repeat every 1h

---

## Flow Summary

```
Binance WS (9 streams)
    ↓ _build_stream_url()         ingestion/ws_consumer.py:59
Single combined WebSocket
    ↓ _route_topic()              ingestion/ws_consumer.py:67
binance.trades / binance.book_ticker
    ↓ key=symbol                  ingestion/kafka_producer.py:39
Kafka partitions (per symbol)
    ↓ _build_trade_query()        spark/streaming_job.py:194
    ↓ _build_spread_query()       spark/streaming_job.py:285
TimescaleDB (trade_metrics, spread_metrics)
    ↓ Grafana queries alert flags every 30s
    ↓ rules.yaml:10  volatility_alert → Volatility Alert rule
    ↓ rules.yaml:51  spread_warning   → Spread Warning rule
    ↓ contact_points.yaml:1  → email to $GRAFANA_ALERT_EMAIL
```
