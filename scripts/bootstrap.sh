#!/bin/bash
# Vinted Market Panel — Bootstrap (wklej na Hetzner)
# Ten skrypt pobiera i uruchamia pełną instalację
set -e
echo "🚀 Vinted Panel — instalacja..."

# Pobierz główny skrypt z base64
B64="__PLACEHOLDER__"
echo "$B64" | base64 -d | bash
