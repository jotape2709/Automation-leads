from __future__ import annotations

import re
from pathlib import Path
from typing import BinaryIO

import pandas as pd

COLUNAS_OBRIGATORIAS = {
    "Segmento", "Empresa", "Cidade", "Telefone", "Avaliações",
    "Tipo Site", "Google Maps", "Score", "Prioridade",
}


def carregar_leads(origem: str | Path | BinaryIO) -> pd.DataFrame:
    df = pd.read_excel(origem, sheet_name="Leads", engine="openpyxl")
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
