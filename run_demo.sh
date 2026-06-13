#!/bin/bash

echo "🚚 Resetting container proxy tunnels..."
# 1. Clear out any ghost threads holding onto our ports
pkill -f streamlit
pkill -f python

echo "📦 Verifying project context..."
# 2. Force the correct root directory path location
cd ~/workspace

echo "🚀 Booting Next-Gen Delivery Risk Dashboard..."
# 3. Fire up Streamlit on port 3000 to trick Replit's native fallback proxy
python3 -m streamlit run scripts/src/app.py --server.port 3000 --server.address 0.0.0.0 --server.headless true