# AgentForge Demo - Setup (10 minutes, do it BEFORE the presentation)

You need: a computer with **Python 3.10 or newer** and **internet**. That's all.
Check Python: open a terminal and type `python --version` (on Mac/Linux use `python3`).
No Python? Install from https://www.python.org/downloads/ (Windows: tick **"Add Python to PATH"**).

## 1. Open a terminal inside this folder
- **Windows:** open the folder, click the address bar, type `cmd`, press Enter.
- **Mac/Linux:** open Terminal, then `cd` into this folder.

## 2. Install (one time)
**Windows**
```
python -m venv venv
venv\Scripts\activate
pip install -r requirements-demo.txt
```
**Mac / Linux**
```
python3 -m venv venv
source venv/bin/activate
pip install -r requirements-demo.txt
```

## 3. Add the two API keys (one time)
1. Copy `env.example.txt` and rename the copy to `.env` (just `.env`, nothing before the dot).
2. Open `.env` in Notepad and paste your Gemini key and your NVIDIA key after the `=` signs. Save.

## 4. Run the demo
Every time, first activate (Windows: `venv\Scripts\activate`, Mac/Linux: `source venv/bin/activate`), then:

**Demo 1 - Notes app** (about 25 seconds)
```
python parallel_demo.py "a notes app with tags and search"
```
**Demo 2 - Habit tracker** (about 25 seconds)
```
python parallel_demo.py "a habit tracker with daily check-ins and streaks"
```

### What to point at on screen
- **Cyan = Gemini agents, green = NVIDIA NIM agents.**
- The planner goes first. Then **4 agents start at the same second** (backend, tester, frontend, docs). That is the parallel multi-agent part.
- Each file appears as its agent finishes. Then the integrator runs the tests; if they fail, the debugger agent fixes the code and the tests run again.
- The last line says `DONE ok=True`.

## 5. Show the finished app
The last line prints a folder. Open a second terminal (activate again), then:
```
cd <that folder>
python -m uvicorn app:app --port 8800
```
Open **http://localhost:8800** in the browser.

## If something goes wrong (backup plan - works with no internet and no keys)
The folder `ready_demos` has two finished, tested apps. Run one of them:
```
cd ready_demos/notes
python -m uvicorn app:app --port 8800
```
(or `cd ready_demos/habit`). Open http://localhost:8800. Say: "this is a build from an earlier run."

| Problem | Fix |
|---|---|
| `python` not found | Use `python3`, or reinstall Python with "Add to PATH" ticked |
| `KeyError: GOOGLE_API_KEY` | The `.env` file is missing or named wrong (must be exactly `.env`) |
| Run shows `ok=False` | Run the same command once more (AI output varies), or use the backup plan |
| Port 8800 busy | Use `--port 8801` and open that address |
