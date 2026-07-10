#!/bin/bash
# Double-click me (Mac). Starts the tracker and opens it in your browser.
cd "$(dirname "$0")"
( sleep 1 && open "http://localhost:8000" ) &
python3 -m http.server 8000 2>/dev/null || python -m http.server 8000
