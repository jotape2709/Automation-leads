"""Coleta de leads locais pela API oficial do Google Places.

Este módulo preserva o comportamento do script original, mas nunca mantém
segredos no código e não executa chamadas externas ao ser importado.
"""

from __future__ import annotations

import os
import re
import time
from pathlib import Path

import pandas as pd
from pandas.api.types import is_object_dtype, is_string_dtype
from openpyxl.styles import Font, PatternFill

from prospeccao.config import carregar_env
from prospeccao.http import post_json

carregar_env()

TERMOS_PESQUISA = [
    "Barbearia", "Clínica de Estética", "Studio de Beleza",
    "Designer de Sobrancelhas", "Psicólogo", "Nutricionista",
    "Fisioterapia", "Pet Shop", "Clínica Veterinária",
    "Escola de Idiomas", "Advogado", "Arquitetura", "Marcenaria",
    "Vidraçaria", "Marmoraria",
]

CIDADES = [
    "São Bernardo do Campo, SP", "Diadema, SP", "Santo André, SP",
    "São Caetano do Sul, SP",
]

URL_API = "https://places.googleapis.com/v1/places:searchText"
DOMINIOS_SOCIAIS = [
    "instagram.com", "facebook.com", "linktr.ee", "bio.site",
    "beacons.ai", "taplink.cc", "wa.me", "tiktok.com", "youtube.com",
    "x.com", "twitter.com",
]


def classificar_site(url: str | None) -> str:
    if not url:
        return "Sem Site"
    url_normalizada = url.lower()
    if any(dominio in url_normalizada for dominio in DOMINIOS_SOCIAIS):
        return "Rede Social"
    return "Site Próprio"


def calcular_score(site_tipo: str, avaliacoes: int, telefone: str) -> int:
    score = 50 if site_tipo == "Sem Site" else 40 if site_tipo == "Rede Social" else 0
    if avaliacoes >= 80:
        score += 20
    if telefone and telefone != "Não informado":
        score += 10
    return score


def classificar_prioridade(score: int) -> str:
    if score >= 60:
        return "Alta"
    if score >= 40:
        return "Média"
    return "Baixa"


def _inteiro_positivo(nome: str, padrao: int) -> int:
    try:
        valor = int(os.getenv(nome, str(padrao)))
    except ValueError as exc:
        raise ValueError(f"{nome} deve ser um número inteiro.") from exc
    if valor <= 0:
        raise ValueError(f"{nome} deve ser maior que zero.")
    return valor


def _intervalo_seguro() -> float:
    try:
        valor = float(os.getenv("PLACES_REQUEST_INTERVAL_SECONDS", "0.75"))
    except ValueError as exc:
        raise ValueError(
            "PLACES_REQUEST_INTERVAL_SECONDS deve ser um número."
        ) from exc
    if not 0.5 <= valor <= 30:
        raise ValueError(
            "PLACES_REQUEST_INTERVAL_SECONDS deve estar entre 0.5 e 30."
        )
    return valor


def coletar_leads(
    api_key: str,
    min_avaliacoes: int = 50,
    max_avaliacoes: int = 250,
    max_requisicoes: int = 60,
    intervalo: float = 0.75,
) -> pd.DataFrame:
    if not api_key.startswith("AIza") or not re.fullmatch(
        r"[0-9A-Za-z_-]{35,50}", api_key
    ):
        raise ValueError("GOOGLE_PLACES_API_KEY possui formato inválido.")
    if max_requisicoes <= 0:
        raise ValueError("max_requisicoes deve ser maior que zero.")
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": (
            "places.displayName,places.shortFormattedAddress,"
            "places.nationalPhoneNumber,places.websiteUri,"
            "places.userRatingCount,places.googleMapsUri"
        ),
    }
    dados: list[dict] = []
    empresas_processadas: set[tuple[str, str]] = set()
    requisicoes = 0

    for termo in TERMOS_PESQUISA:
        print(f"\nSegmento: {termo}")
        for cidade in CIDADES:
            if requisicoes >= max_requisicoes:
                break
            payload = {
                "textQuery": f"{termo} em {cidade}",
                "languageCode": "pt-BR",
                "maxResultCount": 20,
            }
            try:
                requisicoes += 1
                resposta = post_json(URL_API, payload, headers, timeout=30)
                for local in resposta.get("places", []):
                    nome = local.get("displayName", {}).get("text", "Sem Nome")
                    cidade_nome = cidade.split(",")[0]
                    chave = (nome.casefold().strip(), cidade_nome.casefold())
                    if chave in empresas_processadas:
                        continue
                    empresas_processadas.add(chave)

                    avaliacoes = int(local.get("userRatingCount", 0) or 0)
                    if not min_avaliacoes <= avaliacoes <= max_avaliacoes:
                        continue
                    telefone = local.get("nationalPhoneNumber", "Não informado")
                    website = local.get("websiteUri")
                    tipo_site = classificar_site(website)
                    score = calcular_score(tipo_site, avaliacoes, telefone)
                    dados.append({
                        "Segmento": termo,
                        "Empresa": nome,
                        "Cidade": cidade_nome,
                        "Telefone": telefone,
                        "Avaliações": avaliacoes,
                        "Tipo Site": tipo_site,
                        "Website": website or "",
                        "Google Maps": local.get("googleMapsUri", ""),
                        "Score": score,
                        "Prioridade": classificar_prioridade(score),
                    })
            except RuntimeError as exc:
                print(f"Erro em {cidade}: {exc}")
            time.sleep(intervalo)
        if requisicoes >= max_requisicoes:
            break

    df = pd.DataFrame(dados)
    if not df.empty:
        df = df.sort_values(by=["Score", "Avaliações"], ascending=False)
    return df


def _neutralizar_formula(valor):
    if isinstance(valor, str) and valor.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + valor
    return valor


def exportar_excel(df: pd.DataFrame, arquivo: str | Path) -> Path:
    destino = Path(arquivo)
    destino.parent.mkdir(parents=True, exist_ok=True)
    exportacao = df.copy()
    for coluna in exportacao.columns:
        if is_object_dtype(exportacao[coluna]) or is_string_dtype(exportacao[coluna]):
            exportacao[coluna] = exportacao[coluna].map(_neutralizar_formula)
    with pd.ExcelWriter(destino, engine="openpyxl") as writer:
        exportacao.to_excel(writer, sheet_name="Leads", index=False)
        aba = writer.book["Leads"]
        cabecalho = PatternFill(start_color="D9EAD3", end_color="D9EAD3", fill_type="solid")
        for cell in aba[1]:
            cell.fill = cabecalho
            cell.font = Font(bold=True)
        aba.freeze_panes = "A2"
        aba.auto_filter.ref = aba.dimensions
    return destino


def main() -> None:
    api_key = os.getenv("GOOGLE_PLACES_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("Configure GOOGLE_PLACES_API_KEY no arquivo .env antes da coleta.")
    if os.getenv("GOOGLE_PLACES_ENABLED", "0").strip() != "1":
        raise SystemExit(
            "Defina GOOGLE_PLACES_ENABLED=1 após revisar cotas, cobrança e "
            "restrições da chave no Google Cloud."
        )
    max_requisicoes = _inteiro_positivo("MAX_PLACES_REQUESTS", 60)
    intervalo = _intervalo_seguro()
    arquivo = os.getenv("LEADS_FILE", "Leads_ABC_Paulista.xlsx")
    print(f"🚀 Iniciando coleta com limite de {max_requisicoes} requisições")
    df = coletar_leads(
        api_key,
        max_requisicoes=max_requisicoes,
        intervalo=intervalo,
    )
    destino = exportar_excel(df, arquivo)
    print(f"\n✅ {len(df)} leads exportados para: {destino}")


if __name__ == "__main__":
    main()
