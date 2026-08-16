from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path


PADROES = {
    "Google API key": re.compile(r"AIza[0-9A-Za-z_-]{30,}"),
    "OpenAI API key": re.compile(r"sk-(?:proj-)?[0-9A-Za-z_-]{20,}"),
    "GitHub token": re.compile(r"(?:gh[pousr]_[0-9A-Za-z]{30,}|github_pat_[0-9A-Za-z_]{40,})"),
    "AWS access key": re.compile(r"AKIA[0-9A-Z]{16}"),
    "Private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "Assigned credential": re.compile(
        r"(?im)^(?:[A-Z0-9_]*(?:API_KEY|TOKEN|SECRET|PASSWORD))[ \t]*="
        r"[ \t]*[^\s#]{8,}[ \t]*$"
    ),
}

EXTENSOES_BLOQUEADAS = {
    ".xlsx", ".xls", ".csv", ".parquet", ".db", ".sqlite", ".sqlite3",
    ".pem", ".key", ".p12", ".pfx", ".log",
}


def arquivos_do_repositorio(raiz: Path) -> list[Path]:
    try:
        resultado = subprocess.run(
            ["git", "ls-files", "-z"],
            cwd=raiz,
            check=True,
            capture_output=True,
        )
        caminhos = resultado.stdout.decode().split("\0")
        return [raiz / caminho for caminho in caminhos if caminho]
    except (FileNotFoundError, subprocess.CalledProcessError):
        return [
            caminho for caminho in raiz.rglob("*")
            if caminho.is_file() and ".git" not in caminho.parts
        ]


def analisar(raiz: Path) -> list[str]:
    problemas = []
    for caminho in arquivos_do_repositorio(raiz):
        relativo = caminho.relative_to(raiz)
        nome = relativo.name.lower()
        if nome == ".env" or caminho.suffix.lower() in EXTENSOES_BLOQUEADAS:
            problemas.append(f"arquivo sensível rastreado: {relativo}")
        if "credentials" in nome or "service-account" in nome:
            problemas.append(f"arquivo de credencial rastreado: {relativo}")
        try:
            conteudo = caminho.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for rotulo, padrao in PADROES.items():
            for ocorrencia in padrao.finditer(conteudo):
                linha = conteudo.count("\n", 0, ocorrencia.start()) + 1
                problemas.append(f"{rotulo}: {relativo}:{linha}")
    return sorted(set(problemas))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    problemas = analisar(args.root.resolve())
    if problemas:
        for problema in problemas:
            print(problema)
        return 1
    print("Nenhum segredo ou arquivo sensível rastreado.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
