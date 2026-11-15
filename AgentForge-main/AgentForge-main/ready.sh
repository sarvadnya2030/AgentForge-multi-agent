#!/usr/bin/env bash
# LIVE (the real thing):   bash ready.sh live notes     |  bash ready.sh live habit
# BACKUP (verified build): bash ready.sh backup notes   |  bash ready.sh backup habit
cd "$(dirname "$0")" && source venv/bin/activate
case "$1:$2" in
  live:notes)  python parallel_demo.py "a notes app with tags and search" ;;
  live:habit)  python parallel_demo.py "a habit tracker with daily check-ins and streaks" ;;
  backup:*)    cd ready_demos/$2 && python -m pytest -q tests && (xdg-open http://localhost:8820 >/dev/null 2>&1 &) && uvicorn app:app --port 8820 ;;
  *) echo "usage: bash ready.sh live|backup notes|habit" ;;
esac
