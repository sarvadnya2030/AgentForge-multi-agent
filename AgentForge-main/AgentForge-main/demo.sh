#!/usr/bin/env bash
# Visual demo: bash demo.sh   -> opens http://localhost:4141, paste a prompt, press Start.
cd "$(dirname "$0")" && source venv/bin/activate
pkill -f live_server.py 2>/dev/null
LOG=/tmp/agentforge_demo.log; : > $LOG
python live-dashboard/live_server.py $LOG 4141 &
sleep 2; (xdg-open http://localhost:4141 >/dev/null 2>&1 || true)
echo "Dashboard: http://localhost:4141  (Ctrl+C to stop)"
echo 'Suggested prompt: Build a todo app: FastAPI backend with in-memory storage (GET/POST/DELETE /todos) and one single-page HTML UI served at / that lists, adds and deletes todos with fetch(). Include 3 pytest tests.'
wait
