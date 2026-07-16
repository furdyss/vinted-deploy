#!/bin/bash
# Vinted Bot - Start Script (for Termux)
echo "🤖 Vinted Bot - Instalacja..."

# Install dependencies
pkg update -y && pkg install python -y
pip install httpx aiosqlite

# Download bot
curl -sL https://raw.githubusercontent.com/furdyss/vinted-deploy/main/vinted_bot.py > vinted_bot.py

echo ""
echo "✅ Gotowe! Uruchamiam bota..."
echo ""

# Run bot
python3 vinted_bot.py
