from __future__ import annotations

import re
import os
import zipfile
from pathlib import Path
from typing import BinaryIO

import pandas as pd

COLUNAS_OBRIGATORIAS = {
    "Segmento", "Empresa", "Cidade", "Telefone", "Avaliações",
    "Tipo Site", "Google Maps", "Score", "Prioridade",
}


def _limite_inteiro(nome: str, padrao: int) -> int:
    try:
        valor = int(os.getenv(nome, str(padrao)))
    except ValueError as exc:
        raise ValueError(f"{nome} deve ser um número inteiro.") from exc
    if valor <= 0:
        raise ValueError(f"{nome} deve ser maior que zero.")
    return valor


def _validar_workbook(origem: str | Path | BinaryIO) -> None:
    limite_arquivo = _limite_inteiro("MAX_WORKBOOK_MB", 25) * 1024 * 1024
    limite_expandido = (
        _limite_inteiro("MAX_WORKBOOK_UNCOMPRESSED_MB", 150) * 1024 * 1024
    )
    posicao = None
    if hasattr(origem, "tell"):
        posicao = origem.tell()
    if isinstance(origem, (str, Path)):
        caminho = Path(origem)
        if caminho.suffix.lower() != ".xlsx":
            raise ValueError("A base deve estar no formato .xlsx.")
        if caminho.stat().st_size > limite_arquivo:
            raise ValueError("A planilha excede o limite de tamanho configurado.")
    try:
        with zipfile.ZipFile(origem) as arquivo:
            total = 0
            for item in arquivo.infolist():
                if item.flag_bits & 0x1:
                    raise ValueError("Planilhas protegidas por senha não são aceitas.")
                total += item.file_size
                if total > limite_expandido:
                    raise ValueError("O conteúdo expandido da planilha excede o limite.")
                if item.compress_size and item.file_size / item.compress_size > 250:
                    raise ValueError("A planilha apresenta taxa de compressão insegura.")
    except zipfile.BadZipFile as exc:
        raise ValueError("Arquivo .xlsx inválido ou corrompido.") from exc
    finally:
        if posicao is not None:
            origem.seek(posicao)


def carregar_leads(origem: str | Path | BinaryIO) -> pd.DataFrame:
    _validar_workbook(origem)
    df = pd.read_excel(origem, sheet_name="Leads", engine="openpyxl")
    limite_linhas = _limite_inteiro("MAX_LEADS_ROWS", 50000)
    if len(df) > limite_linhas:
        raise ValueError("A planilha excede o limite de leads configurado.")
    ausentes = sorted(COLUNAS_OBRIGATORIAS - set(df.columns))
    if ausentes:
        raise ValueError(f"Colunas ausentes na aba Leads: {', '.join(ausentes)}")
    df = df.copy()
    df["Telefone E164"] = df["Telefone"].map(normalizar_telefone_br)
    df["WhatsApp elegível"] = df["Telefone E164"].map(bool)
    return df


def normalizar_telefone_br(valor: object) -> str | None:
    digitos = re.sub(r"\D", "", str(valor or ""))
    if digitos.startswith("55") and len(digitos) in (12, 13):
        digitos = digitos[2:]
    # WhatsApp prospectivo: somente celulares brasileiros com DDD + 9 dígitos.
    if len(digitos) != 11 or digitos[2] != "9":
        return None
    return f"55{digitos}"


def filtrar_elegiveis(
    df: pd.DataFrame,
    prioridades: list[str],
    tipos_site: list[str],
    cidades: list[str],
) -> pd.DataFrame:
    # Cópia evita que os operadores &= alterem a coluna original do DataFrame.
    filtro = df["WhatsApp elegível"].copy()
    if prioridades:
        filtro &= df["Prioridade"].isin(prioridades)
    if tipos_site:
        filtro &= df["Tipo Site"].isin(tipos_site)
    if cidades:
        filtro &= df["Cidade"].isin(cidades)
    return df.loc[filtro].sort_values(["Score", "Avaliações"], ascending=False)
