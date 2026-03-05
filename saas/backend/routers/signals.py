import json
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

DATA_FILE = Path(__file__).parent.parent / "data" / "signals.json"

_DEFAULTS = [
    {"id": "sig-btc", "symbol": "BTCUSDT", "name": "Bitcoin",  "ticker": "BTC", "enabled": True, "threshold_vol": 2.0, "threshold_spread": 3.0, "color": "#F7931A"},
    {"id": "sig-eth", "symbol": "ETHUSDT", "name": "Ethereum", "ticker": "ETH", "enabled": True, "threshold_vol": 2.0, "threshold_spread": 3.0, "color": "#627EEA"},
    {"id": "sig-bnb", "symbol": "BNBUSDT", "name": "BNB",      "ticker": "BNB", "enabled": True, "threshold_vol": 2.0, "threshold_spread": 3.0, "color": "#F3BA2F"},
]


def _load() -> list:
    if DATA_FILE.exists():
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    return [dict(d) for d in _DEFAULTS]


def _save(data: list) -> None:
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


class SignalIn(BaseModel):
    symbol: str
    name: str
    ticker: str
    enabled: Optional[bool] = True
    threshold_vol: Optional[float] = 2.0
    threshold_spread: Optional[float] = 3.0
    color: Optional[str] = "#F97316"


class SignalPatch(BaseModel):
    enabled: Optional[bool] = None
    threshold_vol: Optional[float] = None
    threshold_spread: Optional[float] = None
    color: Optional[str] = None


@router.get("/")
def list_signals():
    return _load()


@router.post("/", status_code=201)
def add_signal(body: SignalIn):
    signals = _load()
    if any(s["symbol"].upper() == body.symbol.upper() for s in signals):
        raise HTTPException(409, "Symbol already exists")
    sig = {"id": str(uuid.uuid4()), **body.model_dump()}
    sig["symbol"] = sig["symbol"].upper()
    signals.append(sig)
    _save(signals)
    return sig


@router.patch("/{signal_id}")
def patch_signal(signal_id: str, body: SignalPatch):
    signals = _load()
    for s in signals:
        if s["id"] == signal_id:
            for k, v in body.model_dump(exclude_none=True).items():
                s[k] = v
            _save(signals)
            return s
    raise HTTPException(404, "Signal not found")


@router.delete("/{signal_id}")
def delete_signal(signal_id: str):
    signals = _load()
    filtered = [s for s in signals if s["id"] != signal_id]
    if len(filtered) == len(signals):
        raise HTTPException(404, "Signal not found")
    _save(filtered)
    return {"deleted": True}
