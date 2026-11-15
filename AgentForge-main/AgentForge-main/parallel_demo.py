#!/usr/bin/env python3
"""Parallel multi-agent orchestrator. Planner -> 4 agents IN PARALLEL (Gemini + NIM) -> integrator runs tests.
CLI: python parallel_demo.py ["project idea"]      UI: python ui_server.py"""
import asyncio, os, re, subprocess, sys, time
from pathlib import Path
import httpx

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass
GKEY, NKEY = os.environ.get("GOOGLE_API_KEY", ""), os.environ.get("NVIDIA_API_KEY", "")
BASE = Path("/tmp") if os.environ.get("VERCEL") else Path(__file__).parent / "workspace"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent"
NIM_MODEL = "nvidia/nemotron-3.5-bolt-e4b"
C = {"gemini": "\033[96m", "nim": "\033[92m", "orch": "\033[93m", "end": "\033[0m"}


async def _call(provider, prompt):
    async with httpx.AsyncClient(timeout=90) as h:
        if provider == "gemini":
            r = await h.post(GEMINI_URL, headers={"x-goog-api-key": GKEY},
                             json={"contents": [{"parts": [{"text": prompt}]}]})
            r.raise_for_status()
            return r.json()["candidates"][0]["content"]["parts"][0]["text"]
        r = await h.post("https://integrate.api.nvidia.com/v1/chat/completions",
                         headers={"Authorization": f"Bearer {NKEY}"},
                         json={"model": NIM_MODEL, "max_tokens": 3000,
                               "messages": [{"role": "user", "content": prompt}]})
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]


def code(text):  # strip ``` fences (also when the closing fence is missing)
    t = text.strip()
    m = re.search(r"```[\w+-]*[ \t]*\n(.*?)(?:```|\Z)", t, re.S)
    return (m.group(1) if m else t).strip() + "\n"


async def run(idea, emit):
    """Runs the whole pipeline; emit(dict) is called for every visible step."""
    t0 = time.time()
    out = BASE / f"parallel_{int(t0)}"
    out.mkdir(parents=True, exist_ok=True)
    now = lambda: round(time.time() - t0, 2)

    async def llm(name, provider, prompt):
        """One agent call. Falls back to the other provider if this one fails."""
        emit({"type": "agent", "name": name, "provider": provider, "status": "start", "t": now()})
        try:
            text = await _call(provider, prompt)
        except Exception as e:
            other = "nim" if provider == "gemini" else "gemini"
            emit({"type": "agent", "name": name, "provider": provider, "status": "fallback",
                  "t": now(), "msg": f"{provider} failed ({type(e).__name__}) -> switching to {other}"})
            provider = other
            text = await _call(provider, prompt)
        emit({"type": "agent", "name": name, "provider": provider, "status": "done", "t": now()})
        return text

    async def worker(name, provider, path, contract, job):
        raw = await llm(name, provider, f"You are the {name} agent. Shared contract (follow EXACTLY):\n{contract}\n\n"
                                       f"Write ONLY the file `{path}`. {job}\nReturn just the file content in one code block.")
        f = out / path
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(code(raw))
        emit({"type": "file", "path": path, "content": code(raw), "by": name, "t": now()})

    emit({"type": "info", "msg": f"Project: {idea}", "t": now()})
    contract = await llm("planner", "gemini", (
        f"Project: {idea}. Python FastAPI, in-memory. Write a SHORT API contract (max 20 lines): "
        "exact files app.py (FastAPI `app`, JSON endpoints), static/index.html (served at / by app.py), "
        "tests/test_app.py (pytest + fastapi TestClient, imports `from app import app`), README.md. "
        "List endpoints with request/response JSON shapes AND the exact HTTP status code each returns (POST create = 201). No code."))
    emit({"type": "contract", "text": contract.strip(), "t": now()})
    emit({"type": "info", "msg": "Contract ready -> launching 4 agents IN PARALLEL", "t": now(), "parallel": True})
    await asyncio.gather(
        worker("backend", "gemini", "app.py", contract, "Include serving static/index.html at GET / (FileResponse)."),
        worker("frontend", "nim", "static/index.html", contract, "Single self-contained HTML page with inline JS using fetch()."),
        worker("tester", "gemini", "tests/test_app.py", contract, "4 tests. Use ONLY `from app import app` and `from fastapi.testclient import TestClient` (client = TestClient(app)). Import NOTHING else from app. This is FastAPI, NOT Flask. Test only via HTTP calls and the exact status codes in the contract."),
        worker("docs", "nim", "README.md", contract, "Short README with run instructions."),
    )
    emit({"type": "info", "msg": "All parallel agents finished -> integrator runs the tests", "t": now()})
    ok = False
    for attempt in (1, 2, 3):
        emit({"type": "agent", "name": "integrator", "provider": "local", "status": "start", "t": now()})
        r = await asyncio.to_thread(subprocess.run, [sys.executable, "-m", "pytest", "-q", "tests"],
                                    cwd=out, capture_output=True, text=True)
        ok = r.returncode == 0
        emit({"type": "agent", "name": "integrator", "provider": "local", "status": "done", "t": now()})
        emit({"type": "test", "attempt": attempt, "ok": ok, "t": now(),
              "summary": (r.stdout.strip().splitlines() or ["?"])[-1], "output": r.stdout[-1800:]})
        if ok or attempt == 3:
            break
        src = (out / "app.py").read_text()
        tests = (out / "tests/test_app.py").read_text()
        fix = await llm("debugger", "nim", f"Contract:\n{contract}\n\ntests/test_app.py:\n{tests}\n\n"
                                           f"Test failures:\n{r.stdout[-1500:]}\n\napp.py:\n{src}\n\n"
                                           "Fix app.py ONLY so every test passes and the contract is respected "
                                           "(the tests encode the intended behavior). Return the full file in one code block.")
        (out / "app.py").write_text(code(fix))
        emit({"type": "file", "path": "app.py", "content": code(fix), "by": "debugger", "t": now()})
    emit({"type": "done", "ok": ok, "secs": now(), "dir": str(out), "t": now()})
    return out


def cli_emit(e):
    who = f"{e.get('provider','orch')}:{e.get('name','')}" if e["type"] == "agent" else "orch"
    c = C.get(who.split(":")[0], "")
    msg = {"agent": lambda: e["status"] + (" - " + e["msg"] if e.get("msg") else ""),
           "file": lambda: f"wrote {e['path']} ({len(e['content'].splitlines())} lines)",
           "test": lambda: f"pytest attempt {e['attempt']}: {e['summary']}",
           "contract": lambda: "contract written", "info": lambda: e["msg"],
           "done": lambda: f"DONE ok={e['ok']} in {e['secs']}s -> {e['dir']}"}[e["type"]]()
    print(f"{c}[{e['t']:5.1f}s] {who:<16}{C['end']} {msg}", flush=True)


if __name__ == "__main__":
    asyncio.run(run(sys.argv[1] if len(sys.argv) > 1 else "a URL shortener with click stats", cli_emit))
