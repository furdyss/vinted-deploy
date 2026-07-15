#!/bin/bash
# ============================================
# Vinted Market Panel — Hetzner Install Script
# ============================================
# Uruchom na świeżym VPS (Debian/Ubuntu):
#   curl -sL https://raw.githubusercontent.com/YOU/vinted-panel/main/scripts/install-hetzner.sh | bash
#
# Lub ręcznie:
#   chmod +x install-hetzner.sh && ./install-hetzner.sh
# ============================================

set -e

echo "🚀 Vinted Market Panel — Instalacja"
echo "====================================="

# 1. Update system
echo "📦 Aktualizacja systemu..."
apt-get update -qq && apt-get upgrade -y -qq

# 2. Install Docker
echo "🐳 Instalacja Docker..."
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker
    systemctl start docker
    echo "✅ Docker zainstalowany"
else
    echo "✅ Docker już jest"
fi

# 3. Install Docker Compose
echo "🔧 Instalacja Docker Compose..."
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    apt-get install -y -qq docker-compose-plugin
    echo "✅ Docker Compose zainstalowany"
else
    echo "✅ Docker Compose już jest"
fi

# 4. Install git
echo "📥 Instalacja git..."
apt-get install -y -qq git curl

# 5. Clone repo (or use uploaded files)
echo "📁 Przygotowanie projektu..."
INSTALL_DIR="/opt/vinted-panel"

if [ ! -d "$INSTALL_DIR" ]; then
    mkdir -p $INSTALL_DIR
fi

# Check if files exist in current dir
if [ -f "docker-compose.yml" ]; then
    cp -r . $INSTALL_DIR/
    echo "✅ Pliki skopiowane z bieżącego katalogu"
elif [ -d "/tmp/vinted-panel" ]; then
    cp -r /tmp/vinted-panel/* $INSTALL_DIR/
    echo "✅ Pliki skopiowane z /tmp"
else
    echo "⚠️  Umieść pliki projektu w $INSTALL_DIR"
    echo "   Skopiuj cały katalog vinted-panel do tego serwera"
    echo "   np: scp -r vinted-panel/ root@<IP>:/opt/"
    exit 1
fi

cd $INSTALL_DIR

# 6. Create data directory
mkdir -p data

# 7. Build and run
echo "🔨 Budowanie kontenera..."
docker compose build

echo "🚀 Uruchamianie..."
docker compose up -d

# 8. Check status
sleep 3
if docker compose ps | grep -q "Up"; then
    echo ""
    echo "============================================"
    echo "✅ Vinted Market Panel działa!"
    echo ""
    echo "📍 Panel:  http://$(hostname -I | awk '{print $1}'):8080"
    echo ""
    echo "📱 Na telefonie:"
    echo "   1. Otwórz http://$(hostname -I | awk '{print $1}'):8080"
    echo "   2. Chrome: ⋮ menu → 'Dodaj do ekranu głównego'"
    echo "   3. Safari: ikona分享 → 'Dodaj do ekranu początkowego'"
    echo ""
    echo "🔧 Zarządzanie:"
    echo "   docker compose logs -f        — podgląd logów"
    echo "   docker compose restart        — restart"
    echo "   docker compose down           — zatrzymanie"
    echo "   docker compose up -d          — uruchomienie"
    echo "============================================"
else
    echo "❌ Coś poszło nie tak. Sprawdź logi:"
    echo "   docker compose logs"
fi
