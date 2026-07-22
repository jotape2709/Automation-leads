"""Coleta de leads locais pela API oficial do Google Places.

Este módulo preserva o comportamento do script original, mas nunca mantém
segredos no código e não executa chamadas externas ao ser importado.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import pandas as pd
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


def coletar_leads(api_key: str, min_avaliacoes: int = 50, max_avaliacoes: int = 250) -> pd.DataFrame:
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

    for termo in TERMOS_PESQUISA:
        print(f"\nSegmento: {termo}")
        for cidade in CIDADES:
            payload = {"textQuery": f"{termo} em {cidade}", "languageCode": "pt-BR"}
            try:
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
            time.sleep(0.5)

    df = pd.DataFrame(dados)
    if not df.empty:
        df = df.sort_values(by=["Score", "Avaliações"], ascending=False)
    return df


def exportar_excel(df: pd.DataFrame, arquivo: str | Path) -> Path:
    destino = Path(arquivo)
    with pd.ExcelWriter(destino, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Leads", index=False)
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
    arquivo = os.getenv("LEADS_FILE", "Leads_ABC_Paulista.xlsx")
    print("🚀 Iniciando coleta")
    df = coletar_leads(api_key)
    destino = exportar_excel(df, arquivo)
    print(f"\n✅ {len(df)} leads exportados para: {destino}")


if __name__ == "__main__":
    main()
