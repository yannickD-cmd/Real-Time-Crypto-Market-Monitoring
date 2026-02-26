import csv
import io
import json
import uuid
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

router = APIRouter()

DATA_FILE = Path(__file__).parent.parent / "data" / "members.json"


def _load() -> list:
    if DATA_FILE.exists():
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    return []


def _save(data: list) -> None:
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


class MemberIn(BaseModel):
    name: str
    email: str
    tags: Optional[List[str]] = []


@router.get("/")
def list_members():
    return _load()


@router.post("/", status_code=201)
def add_member(body: MemberIn):
    members = _load()
    if any(m["email"].lower() == body.email.lower() for m in members):
        raise HTTPException(409, "Email already exists")
    member = {"id": str(uuid.uuid4()), **body.model_dump()}
    members.append(member)
    _save(members)
    return member


@router.delete("/{member_id}")
def delete_member(member_id: str):
    members = _load()
    filtered = [m for m in members if m["id"] != member_id]
    if len(filtered) == len(members):
        raise HTTPException(404, "Member not found")
    _save(filtered)
    return {"deleted": True}


@router.post("/import-csv")
async def import_csv(file: UploadFile = File(...)):
    raw = await file.read()
    text = raw.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))

    members = _load()
    existing = {m["email"].lower() for m in members}
    added = skipped = 0

    for row in reader:
        norm = {k.lower().strip(): (v or "").strip() for k, v in row.items() if k}
        email = (
            norm.get("email") or norm.get("e-mail") or norm.get("mail") or ""
        ).lower()
        name = (
            norm.get("name") or norm.get("full name") or norm.get("full_name")
            or norm.get("username") or norm.get("display name") or ""
        )

        if not email or email in existing:
            skipped += 1
            continue

        members.append({
            "id": str(uuid.uuid4()),
            "name": name or email.split("@")[0],
            "email": email,
            "tags": [],
        })
        existing.add(email)
        added += 1

    _save(members)
    return {"imported": added, "skipped": skipped, "total": len(members)}
