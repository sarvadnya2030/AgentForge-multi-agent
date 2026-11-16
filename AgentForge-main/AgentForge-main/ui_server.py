#!/usr/bin/env python3
"""Presentation UI for the parallel multi-agent demo.  Run: python ui_server.py  -> http://localhost:8080"""
import asyncio, json, os, socket, subprocess, sys
from pathlib import Path
import base64, hmac
from fastapi import FastAPI, Request
from fastapi.responses import Response
from fastapi.responses import FileResponse, StreamingResponse
import parallel_demo as pd

app = FastAPI()
ACCESS_CODE = os.environ.get("ACCESS_CODE", "")  # set on a public deploy: browser asks for it (any username)


@app.middleware("http")
async def gate(request: Request, call_next):
    if ACCESS_CODE:
        try:
            pw = base64.b64decode(request.headers.get("authorization", "")[6:]).decode().partition(":")[2]
        except Exception:
            pw = ""
        if not hmac.compare_digest(pw, ACCESS_CODE):
            return Response("Access code required", 401, {"WWW-Authenticate": 'Basic realm="AgentForge"'})
    return await call_next(request)
HERE = Path(__file__).parent
IS_VERCEL = bool(os.environ.get("VERCEL") or os.environ.get("RENDER"))  # hosted: no localhost preview
_lock = asyncio.Lock()  # one run at a time keeps the demo readable and API usage sane


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@app.get("/")
def index():
    return FileResponse(HERE / "ui" / "index.html")


@app.get("/api/health")
def health():
    return {"gemini_key": bool(pd.GKEY), "nim_key": bool(pd.NKEY), "vercel": IS_VERCEL}


@app.get("/api/run")
async def run(idea: str):
    q: asyncio.Queue = asyncio.Queue()

    async def worker():
        try:
            async with _lock:
                out = await pd.run(idea[:300], q.put_nowait)
            if not IS_VERCEL and (out / "app.py").exists():
                port = free_port()
                subprocess.Popen([sys.executable, "-m", "uvicorn", "app:app", "--port", str(port)],
                                 cwd=out, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                await asyncio.sleep(2)
                q.put_nowait({"type": "preview", "url": f"http://localhost:{port}"})
        except Exception as e:  # surface any failure in the UI instead of a silent hang
            q.put_nowait({"type": "error", "msg": f"{type(e).__name__}: {e}"})
        q.put_nowait(None)

    asyncio.create_task(worker())

    async def stream():
        while (e := await q.get()) is not None:
            yield f"data: {json.dumps(e)}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0" if os.environ.get("RENDER") else "127.0.0.1", port=int(os.environ.get("PORT", 8080)))
