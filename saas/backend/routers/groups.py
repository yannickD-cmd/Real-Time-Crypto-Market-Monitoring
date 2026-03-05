import json
import uuid
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

DATA_FILE = Path(__file__).parent.parent / "data" / "groups.json"


def _load() -> list:
    if DATA_FILE.exists():
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    return []


def _save(data: list) -> None:
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


class GroupIn(BaseModel):
    name: str
    color: Optional[str] = "#ff6207"


class GroupPatch(BaseModel):
    name: Optional[str] = None
    color: Optional[str] = None
    signal_ids: Optional[List[str]] = None
    member_ids: Optional[List[str]] = None


@router.get("/")
def list_groups():
    return _load()


@router.post("/", status_code=201)
def create_group(body: GroupIn):
    groups = _load()
    if any(g["name"].lower() == body.name.lower() for g in groups):
        raise HTTPException(409, "Group name already exists")
    group = {
        "id": str(uuid.uuid4()),
        "name": body.name,
        "color": body.color,
        "signal_ids": [],
        "member_ids": [],
    }
    groups.append(group)
    _save(groups)
    return group


@router.patch("/{group_id}")
def patch_group(group_id: str, body: GroupPatch):
    groups = _load()
    for g in groups:
        if g["id"] == group_id:
            for k, v in body.model_dump(exclude_none=True).items():
                g[k] = v
            _save(groups)
            return g
    raise HTTPException(404, "Group not found")


@router.delete("/{group_id}")
def delete_group(group_id: str):
    groups = _load()
    filtered = [g for g in groups if g["id"] != group_id]
    if len(filtered) == len(groups):
        raise HTTPException(404, "Group not found")
    _save(filtered)
    return {"deleted": True}


@router.post("/{group_id}/members/{member_id}")
def add_member_to_group(group_id: str, member_id: str):
    groups = _load()
    # Remove member from any other group first (exclusive membership)
    for g in groups:
        if member_id in g.get("member_ids", []):
            g["member_ids"] = [m for m in g["member_ids"] if m != member_id]
    for g in groups:
        if g["id"] == group_id:
            if member_id not in g.get("member_ids", []):
                g.setdefault("member_ids", []).append(member_id)
            _save(groups)
            return g
    raise HTTPException(404, "Group not found")


@router.delete("/{group_id}/members/{member_id}")
def remove_member_from_group(group_id: str, member_id: str):
    groups = _load()
    for g in groups:
        if g["id"] == group_id:
            g["member_ids"] = [m for m in g.get("member_ids", []) if m != member_id]
            _save(groups)
            return g
    raise HTTPException(404, "Group not found")


@router.post("/{group_id}/signals/{signal_id}")
def add_signal_to_group(group_id: str, signal_id: str):
    groups = _load()
    for g in groups:
        if g["id"] == group_id:
            if signal_id not in g.get("signal_ids", []):
                g.setdefault("signal_ids", []).append(signal_id)
            _save(groups)
            return g
    raise HTTPException(404, "Group not found")


@router.delete("/{group_id}/signals/{signal_id}")
def remove_signal_from_group(group_id: str, signal_id: str):
    groups = _load()
    for g in groups:
        if g["id"] == group_id:
            g["signal_ids"] = [s for s in g.get("signal_ids", []) if s != signal_id]
            _save(groups)
            return g
    raise HTTPException(404, "Group not found")
