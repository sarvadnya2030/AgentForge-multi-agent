#!/usr/bin/env python3
"""Parallel multi-agent demo. Planner -> 4 agents IN PARALLEL (Gemini + NIM) -> integrator runs tests.
Usage: python parallel_demo.py ["project idea"]"""
import asyncio, json, os, re, subprocess, sys, time
from pathlib import Path
import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")
GKEY, NKEY = os.environ["GOOGLE_API_KEY"], os.environ["NVIDIA_API_KEY"]
T0 = time.time()
OUT = Path(__file__).parent / "workspace" / f"parallel_{int(T0)}"
C = {"gemini": "\033[96m", "nim": "\033[92m", "orch": "\033[93m", "end": "\033[0m"}


def log(who, msg):
    c = C.get(who.split(":")[0], "")
    print(f"{c}[{time.time()-T0:5.1f}s] {who:<14}{C['end']} {msg}", flush=True)


async def llm(provider, prompt, who):
    log(who, f"-> calling {provider}")
    async with httpx.AsyncClient(timeout=120) as h:
        if provider == "gemini":
            r = await h.post(
                "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent",
                headers={"x-goog-api-key": GKEY},
                json={"contents": [{"parts": [{"text": prompt}]}]})
            r.raise_for_status()
            return r.json()["candidates"][0]["content"]["parts"][0]["text"]
        r = await h.post(
            "https://integrate.api.nvidia.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {NKEY}"},
            json={"model": "nvidia/nemotron-3.5-bolt-e4b", "max_tokens": 3000,
                  "messages": [{"role": "user", "content": prompt}]})
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]


def code(text):  # strip ``` fences
    m = re.search(r"```(?:\w+)?\n(.*?)```", text, re.S)
    return (m.group(1) if m else text).strip() + "\n"


async def agent(name, provider, path, contract, job):
    who = f"{provider}:{name}"
    t = time.time()
    raw = await llm(provider, f"You are the {name} agent. Shared contract (follow EXACTLY):\n{contract}\n\n"
                              f"Write ONLY the file `{path}`. {job}\nReturn just the file content in one code block.", who)
    f = OUT / path
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(code(raw))
    log(who, f"done: wrote {path} ({len(code(raw).splitlines())} lines, {time.time()-t:.1f}s)")


async def main():
    idea = sys.argv[1] if len(sys.argv) > 1 else "a URL shortener with click stats"
    log("orch", f"project: {idea}")
    contract = await llm("gemini", (
        f"Project: {idea}. Python FastAPI, in-memory. Write a SHORT API contract (max 20 lines): "
        "exact files app.py (FastAPI `app`, JSON endpoints), static/index.html (served at / by app.py), "
        "tests/test_app.py (pytest + fastapi TestClient, imports `from app import app`), README.md. "
        "List endpoints with request/response JSON shapes AND the exact HTTP status code each returns (POST create = 201). No code."), "gemini:planner")
    log("orch", "contract ready -> launching 4 agents IN PARALLEL")
    (OUT).mkdir(parents=True, exist_ok=True)
    await asyncio.gather(
        agent("backend", "gemini", "app.py", contract, "Include serving static/index.html at GET / (FileResponse)."),
        agent("frontend", "nim", "static/index.html", contract, "Single self-contained HTML page with inline JS using fetch()."),
        agent("tester", "gemini", "tests/test_app.py", contract, "4 tests. Use ONLY `from app import app` and `from fastapi.testclient import TestClient` (client = TestClient(app)). Import NOTHING else from app. This is FastAPI, NOT Flask. Test only via HTTP calls and the exact status codes in the contract."),
        agent("docs", "nim", "README.md", contract, "Short README with run instructions."),
    )
    log("orch", "all parallel agents finished -> integrator runs tests")
    for attempt in (1, 2, 3):
        r = subprocess.run([sys.executable, "-m", "pytest", "-q", "tests"], cwd=OUT, capture_output=True, text=True)
        log("orch", f"pytest attempt {attempt}: " + (r.stdout.strip().splitlines() or ["?"])[-1])
        if r.returncode == 0:
            break
        if attempt < 3:  # up to 2 repair passes by the debugger agent
            src = (OUT / "app.py").read_text()
            fix = await llm("nim", f"Tests failed:\n{r.stdout[-1500:]}\n\napp.py:\n{src}\n\n"
                                   "Fix app.py ONLY. Return the full file in one code block.", "nim:debugger")
            (OUT / "app.py").write_text(code(fix))
            log("nim:debugger", "patched app.py")
    log("orch", f"DONE in {time.time()-T0:.1f}s -> {OUT}")
    print(f"Run it: cd {OUT} && uvicorn app:app --port 8800")


asyncio.run(main())
