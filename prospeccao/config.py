from __future__ import annotations

import os
from pathlib import Path


def carregar_env(caminho: str | Path = ".env") -> None:
    """Carrega um .env simples sem sobrescrever variáveis já definidas."""
    arquivo = Path(caminho)
    if not arquivo.exists():
        return
    for linha in arquivo.read_text(encoding="utf-8").splitlines():
        limpa = linha.strip()
        if not limpa or limpa.startswith("#") or "=" not in limpa:
            continue
        chave, valor = limpa.split("=", 1)
        chave = chave.strip()
        valor = valor.strip().strip('"').strip("'")
        if chave:
            os.environ.setdefault(chave, valor)
