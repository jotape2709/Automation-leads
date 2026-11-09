#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

echo ""
echo "  ======================================================================"
echo "   JPX LAB • AUTOMATION LEADS & CRM v3.2 (Rust + Python + Cofre AEAD)"
echo "  ======================================================================"
echo ""

if [ -x "./target/release/jpx-crm" ]; then
    exec ./target/release/jpx-crm serve "$@"
fi

if command -v cargo >/dev/null 2>&1; then
    echo "  ⚙ Compilando binário nativo otimizado em Rust (--release)..."
    cargo build --release
    exec ./target/release/jpx-crm serve "$@"
fi

if [ -x "./.venv/bin/python" ]; then
    exec ./.venv/bin/python app.py "$@"
fi

exec python3 app.py "$@"
