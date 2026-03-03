"""
Test which Kafka partition each symbol maps to.

Option 1 (offline) — pure Python murmur2, same algorithm librdkafka uses.
Option 2 (live)    — actually produce to Kafka and read back the real partition
                     from the delivery report. Requires Docker running.
"""

SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]
NUM_PARTITIONS = 3
TOPIC = "binance.trades"


# ---------------------------------------------------------------------------
# Option 1 — offline murmur2 (no Kafka needed)
# ---------------------------------------------------------------------------

def murmur2(data: bytes) -> int:
    """Kafka's murmur2 hash — matches librdkafka's default partitioner."""
    length = len(data)
    seed   = 0x9747b28c
    m      = 0x5bd1e995
    r      = 24
    h      = (seed ^ length) & 0xffffffff

    for i in range(length // 4):
        i4 = i * 4
        k  = (data[i4]
              | (data[i4 + 1] << 8)
              | (data[i4 + 2] << 16)
              | (data[i4 + 3] << 24)) & 0xffffffff
        k = (k * m) & 0xffffffff
        k ^= k >> r
        k = (k * m) & 0xffffffff
        h = (h * m) & 0xffffffff
        h ^= k

    tail = length % 4
    if tail >= 3:
        h ^= (data[length - 3] & 0xff) << 16
    if tail >= 2:
        h ^= (data[length - 2] & 0xff) << 8
    if tail >= 1:
        h ^= (data[length - 1] & 0xff)
        h  = (h * m) & 0xffffffff

    h ^= h >> 13
    h  = (h * m) & 0xffffffff
    h ^= h >> 15
    return h


def partition_for(symbol: str, num_partitions: int) -> int:
    return (murmur2(symbol.encode("utf-8")) & 0x7fffffff) % num_partitions


print("=" * 40)
print("Option 1 — offline murmur2 estimate")
print("=" * 40)
seen = {}
for sym in SYMBOLS:
    p = partition_for(sym, NUM_PARTITIONS)
    collision = f"  ⚠ collides with {seen[p]}" if p in seen else ""
    seen[p] = sym
    print(f"  {sym:12s} → partition {p}{collision}")

all_partitions = set(seen.keys())
used = len(all_partitions)
print(f"\n  {used}/{NUM_PARTITIONS} partitions used — {'even split' if used == NUM_PARTITIONS else 'COLLISION DETECTED'}")


# ---------------------------------------------------------------------------
# Option 2 — live test via confluent_kafka delivery report
# ---------------------------------------------------------------------------

print()
print("=" * 40)
print("Option 2 — live Kafka delivery report")
print("=" * 40)

try:
    from confluent_kafka import Producer

    results = {}

    def _on_delivery(err, msg):
        if err:
            print(f"  ERROR: {err}")
        else:
            sym = msg.key().decode()
            results[sym] = msg.partition()

    p = Producer({"bootstrap.servers": "localhost:9092"})

    for sym in SYMBOLS:
        p.produce(
            topic=TOPIC,
            key=sym.encode("utf-8"),
            value=b"test",
            callback=_on_delivery,
        )

    p.flush(timeout=5)

    if results:
        seen2 = {}
        for sym, part in results.items():
            collision = f"  ⚠ collides with {seen2[part]}" if part in seen2 else ""
            seen2[part] = sym
            print(f"  {sym:12s} → partition {part}{collision}")

        used2 = len(set(seen2.keys()))
        print(f"\n  {used2}/{NUM_PARTITIONS} partitions used — {'even split' if used2 == NUM_PARTITIONS else 'COLLISION DETECTED'}")
    else:
        print("  No delivery reports received — is Docker running?")

except Exception as e:
    print(f"  Kafka unavailable ({e})")
    print("  Start Docker first: cd binance-pipeline/docker && docker compose up -d")
