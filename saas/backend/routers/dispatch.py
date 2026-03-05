import json
import os
import smtplib
import time
import uuid
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import List

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

load_dotenv()

router = APIRouter()

HISTORY_FILE = Path(__file__).parent.parent / "data" / "history.json"


def _load_history() -> list:
    if HISTORY_FILE.exists():
        return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
    return []


def _save_history(h: list) -> None:
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_FILE.write_text(json.dumps(h, indent=2), encoding="utf-8")


def _html(name: str, signal: str, message: str) -> str:
    return f"""<!DOCTYPE html>
<html><body style="margin:0;padding:0;background:#0D0D0D;font-family:Inter,Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#0D0D0D;padding:40px 0;">
    <tr><td align="center">
      <table width="560" cellpadding="0" cellspacing="0"
        style="background:#161616;border-radius:12px;border:1px solid rgba(255,255,255,0.07);overflow:hidden;">
        <tr>
          <td style="background:linear-gradient(135deg,#1a0a00,#0D0D0D);padding:32px;
                     border-bottom:1px solid rgba(249,115,22,0.3);">
            <span style="color:#F97316;font-size:12px;font-weight:600;
                         letter-spacing:2px;text-transform:uppercase;">Signal Alert</span>
            <h1 style="color:#fff;margin:8px 0 0;font-size:22px;font-weight:700;">{signal}</h1>
          </td>
        </tr>
        <tr>
          <td style="padding:32px;">
            <p style="color:#9CA3AF;margin:0 0 8px;font-size:14px;">Hi {name},</p>
            <p style="color:#fff;font-size:16px;line-height:1.6;margin:0 0 24px;
                      white-space:pre-wrap;">{message}</p>
            <hr style="border:none;border-top:1px solid rgba(255,255,255,0.07);margin:24px 0;"/>
            <p style="color:#6B7280;font-size:12px;margin:0;">
              You received this alert as a member of the community.<br/>
              Powered by your Crypto Signal Dashboard.
            </p>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body></html>"""


class Recipient(BaseModel):
    id: str
    name: str
    email: str


class DispatchRequest(BaseModel):
    recipients: List[Recipient]
    signal_name: str
    subject: str
    message: str


@router.post("/send")
def send_dispatch(req: DispatchRequest):
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_pass = os.getenv("SMTP_PASSWORD", "")
    from_name = os.getenv("FROM_NAME", "Crypto Signals")
    from_addr = os.getenv("FROM_EMAIL", smtp_user)

    if not smtp_user or not smtp_pass:
        raise HTTPException(500, "SMTP credentials not set in .env")

    sent, errors = [], []
    try:
        server = smtplib.SMTP(smtp_host, smtp_port, timeout=15)
        server.ehlo()
        server.starttls()
        server.login(smtp_user, smtp_pass)

        for r in req.recipients:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = req.subject
            msg["From"] = f"{from_name} <{from_addr}>"
            msg["To"] = r.email
            msg.attach(MIMEText(_html(r.name, req.signal_name, req.message), "html"))
            try:
                server.sendmail(from_addr, [r.email], msg.as_string())
                sent.append(r.email)
            except Exception as e:
                errors.append({"email": r.email, "error": str(e)})

        server.quit()
    except Exception as e:
        raise HTTPException(500, detail=str(e))

    history = _load_history()
    history.insert(0, {
        "id": str(uuid.uuid4()),
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "signal_name": req.signal_name,
        "subject": req.subject,
        "message": req.message,
        "sent_to": sent,
        "errors": errors,
        "count": len(sent),
    })
    _save_history(history[:200])
    return {"sent": len(sent), "errors": errors}


@router.get("/history")
def get_history():
    return _load_history()
