from __future__ import annotations

import os
import re
import zipfile
from pathlib import Path
from typing import BinaryIO

import pandas as pd

from index import calcular_score, classificar_prioridade, classificar_site, exportar_excel

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


def explicar_score(row: dict | pd.Series) -> list[dict[str, object]]:
    """Retorna a decomposição transparente do Score comercial do lead."""
    tipo = str(row.get("Tipo Site", "Sem Site"))
    avaliacoes = int(row.get("Avaliações", 0) or 0)
    telefone = str(row.get("Telefone", ""))
    itens = []
    if tipo == "Sem Site":
        itens.append({"fator": "Ausência de site próprio", "pontos": 50, "ativo": True})
    elif tipo == "Rede Social":
        itens.append({"fator": "Presença apenas em rede social/bio", "pontos": 40, "ativo": True})
    else:
        itens.append({"fator": "Já possui site próprio", "pontos": 0, "ativo": False})

    itens.append({
        "fator": "Volume relevante de avaliações (80+)",
        "pontos": 20 if avaliacoes >= 80 else 0,
        "ativo": avaliacoes >= 80,
    })
    tem_tel = bool(telefone and telefone != "Não informado")
    itens.append({
        "fator": "Telefone comercial identificado",
        "pontos": 10 if tem_tel else 0,
        "ativo": tem_tel,
    })
    return itens


def filtrar_elegiveis(
    df: pd.DataFrame,
    prioridades: list[str],
    tipos_site: list[str],
    cidades: list[str],
    busca: str = "",
    ordenar: str = "score",
) -> pd.DataFrame:
    # Cópia evita que os operadores &= alterem a coluna original do DataFrame.
    filtro = df["WhatsApp elegível"].copy()
    prioridades_limpas = [
        p for p in prioridades if p and p.lower() not in {"todas", "todos", "all"}
    ]
    tipos_limpos = [
        t for t in tipos_site if t and t.lower() not in {"todas", "todos", "all"}
    ]
    cidades_limpas = [
        c for c in cidades if c and c.lower() not in {"todas", "todos", "all"}
    ]

    if prioridades_limpas:
        filtro &= df["Prioridade"].isin(prioridades_limpas)
    if tipos_limpos:
        filtro &= df["Tipo Site"].isin(tipos_limpos)
    if cidades_limpas:
        filtro &= df["Cidade"].isin(cidades_limpas)

    if busca and busca.strip():
        termo = busca.strip().casefold()
        match_empresa = df["Empresa"].astype(str).str.casefold().str.contains(termo, regex=False, na=False)
        match_segmento = df["Segmento"].astype(str).str.casefold().str.contains(termo, regex=False, na=False)
        match_cidade = df["Cidade"].astype(str).str.casefold().str.contains(termo, regex=False, na=False)
        match_tel = df["Telefone"].astype(str).str.casefold().str.contains(termo, regex=False, na=False)
        filtro &= (match_empresa | match_segmento | match_cidade | match_tel)

    resultado = df.loc[filtro]
    ordenar_chave = (ordenar or "score").lower().strip()
    if ordenar_chave == "avaliacoes":
        return resultado.sort_values(["Avaliações", "Score"], ascending=[False, False])
    if ordenar_chave == "empresa":
        return resultado.sort_values(["Empresa", "Score"], ascending=[True, False])
    return resultado.sort_values(["Score", "Avaliações"], ascending=[False, False])


def adicionar_lead_manual(
    caminho: str | Path,
    empresa: str,
    segmento: str,
    cidade: str,
    telefone: str,
    avaliacoes: int = 50,
    website: str = "",
    google_maps: str = "",
) -> dict:
    empresa_limpa = " ".join(str(empresa or "").split())[:160]
    segmento_limpo = " ".join(str(segmento or "Negócio Local").split())[:100]
    cidade_limpa = " ".join(str(cidade or "Santo André").split())[:100]
    telefone_limpo = " ".join(str(telefone or "").split())[:40]
    website_limpo = " ".join(str(website or "").split())[:300]
    maps_limpo = " ".join(str(google_maps or "").split())[:300]

    if not empresa_limpa:
        raise ValueError("Informe o nome da empresa.")
    if not normalizar_telefone_br(telefone_limpo):
        raise ValueError(
            "Informe um celular brasileiro válido com DDD e 9 dígitos (ex.: (11) 99999-9999)."
        )

    avaliacoes_int = max(int(avaliacoes or 0), 0)
    tipo_site = classificar_site(website_limpo)
    score = calcular_score(tipo_site, avaliacoes_int, telefone_limpo)
    prioridade = classificar_prioridade(score)

    novo_registro = {
        "Segmento": segmento_limpo,
        "Empresa": empresa_limpa,
        "Cidade": cidade_limpa,
        "Telefone": telefone_limpo,
        "Avaliações": avaliacoes_int,
        "Tipo Site": tipo_site,
        "Website": website_limpo,
        "Google Maps": maps_limpo or "https://www.google.com/maps",
        "Score": score,
        "Prioridade": prioridade,
    }

    destino = Path(caminho)
    if destino.exists():
        _validar_workbook(destino)
        df_atual = pd.read_excel(destino, sheet_name="Leads", engine="openpyxl")
        df_novo = pd.concat([pd.DataFrame([novo_registro]), df_atual], ignore_index=True)
    else:
        df_novo = pd.DataFrame([novo_registro])

    exportar_excel(df_novo, destino)
    return novo_registro
