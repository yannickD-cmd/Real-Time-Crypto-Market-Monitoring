from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import ws, members, signals, dispatch

app = FastAPI(title="Crypto Signal Dispatcher", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ws.router, tags=["WebSocket"])
app.include_router(members.router, prefix="/api/members", tags=["Members"])
app.include_router(signals.router, prefix="/api/signals", tags=["Signals"])
app.include_router(dispatch.router, prefix="/api/dispatch", tags=["Dispatch"])


@app.get("/")
def root():
    return {"status": "ok", "service": "Crypto Signal Dispatcher"}
