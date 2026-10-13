#!/bin/sh
cd "$(dirname "$0")"
python3 -m pip install -r requirements.txt
(sleep 2; (open http://127.0.0.1:5000 || xdg-open http://127.0.0.1:5000) >/dev/null 2>&1) &
python3 app.py
