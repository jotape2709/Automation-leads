from __future__ import annotations

import json
import os
from dataclasses import dataclass

from prospeccao.http import post_json


@dataclass(frozen=True)
class MensagemGerada:
    contexto: str
    mensagem: str
    provider: str
    model: str


def _prompt(lead: dict) -> str:
    nome = os.getenv("PROSPECTOR_NAME", "João Pedro")
    empresa_remetente = os.getenv("BUSINESS_NAME", "JPX Lab")
    portfolio = os.getenv("PORTFOLIO_URL", "https://jpxlab.com.br")
    dados = {
        "empresa": lead.get("Empresa"),
        "segmento": lead.get("Segmento"),
        "cidade": lead.get("Cidade"),
        "avaliacoes": lead.get("Avaliações"),
        "tipo_site": lead.get("Tipo Site"),
        "website": lead.get("Website"),
        "google_maps": lead.get("Google Maps"),
    }
    return f"""
Você cria uma primeira abordagem comercial individual, respeitosa e não invasiva.
Use SOMENTE os dados fornecidos. Não invente fatos, elogios, prêmios, problemas ou
informações observadas em páginas que não foram efetivamente fornecidas.

Dados do lead: {json.dumps(dados, ensure_ascii=False, default=str)}
Remetente: {nome}, da {empresa_remetente}
Serviços: sites e landing pages, automações, integrações, design e dados.
Portfólio: {portfolio}

Retorne JSON válido com exatamente duas chaves:
- "contexto": resumo factual de uma frase sobre a oportunidade;
- "mensagem": WhatsApp em português brasileiro, 55 a 90 palavras.

A mensagem deve: apresentar o remetente; citar naturalmente empresa, segmento ou
cidade; explicar uma oportunidade concreta sem atacar o negócio; pedir permissão
para mostrar uma ideia; ter no máximo um link; não usar urgência falsa, promessa de
resultado, texto genérico de spam ou mais de um emoji.
""".strip()


def mensagem_fallback(lead: dict) -> MensagemGerada:
    nome = os.getenv("PROSPECTOR_NAME", "João Pedro")
    marca = os.getenv("BUSINESS_NAME", "JPX Lab")
    portfolio = os.getenv("PORTFOLIO_URL", "https://jpxlab.com.br")
    empresa = str(lead.get("Empresa", "seu negócio"))
    segmento = str(lead.get("Segmento", "negócio local")).lower()
    cidade = str(lead.get("Cidade", "ABC Paulista"))
    tipo_site = str(lead.get("Tipo Site", "Não verificado"))
    oportunidade = (
        "uma presença digital própria para facilitar que clientes encontrem serviços e contatos"
        if tipo_site == "Sem Site"
        else "organizar melhor a presença digital e transformar visitas em contatos"
    )
    mensagem = (
        f"Olá! Sou {nome}, da {marca}. Encontrei a {empresa} ao pesquisar {segmento} "
        f"em {cidade}. Trabalho com sites e automações para negócios locais e pensei em "
        f"{oportunidade}. Posso te mostrar, sem compromisso, uma ideia rápida e específica "
        f"para a {empresa}? Meu portfólio: {portfolio}"
    )
    return MensagemGerada(
        contexto=f"{empresa} é um negócio de {segmento} em {cidade}, classificado como {tipo_site}.",
        mensagem=mensagem,
        provider="modelo local",
        model="fallback",
    )


def gerar_mensagem(lead: dict, provider: str) -> MensagemGerada:
    provider = provider.lower().strip()
    if provider == "openai":
        return _gerar_openai(lead)
    if provider == "gemini":
        return _gerar_gemini(lead)
    return mensagem_fallback(lead)


def _parse_json(texto: str) -> tuple[str, str]:
    limpo = texto.strip().removeprefix("```json").removesuffix("```").strip()
    objeto = json.loads(limpo)
    contexto = str(objeto.get("contexto", "")).strip()
    mensagem = str(objeto.get("mensagem", "")).strip()
    if not contexto or not mensagem:
        raise ValueError("A IA não retornou contexto e mensagem válidos.")
    return contexto, mensagem


def _gerar_openai(lead: dict) -> MensagemGerada:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise ValueError("OPENAI_API_KEY não configurada no .env.")
    model = os.getenv("OPENAI_MODEL", "gpt-5.6-luna")
    payload = post_json(
        "https://api.openai.com/v1/responses",
        {"model": model, "input": _prompt(lead), "max_output_tokens": 500},
        {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        timeout=60,
    )
    textos = [
        item.get("text", "")
        for saida in payload.get("output", [])
        for item in saida.get("content", [])
        if item.get("type") == "output_text"
    ]
    contexto, mensagem = _parse_json("".join(textos))
    return MensagemGerada(contexto, mensagem, "OpenAI", model)


def _gerar_gemini(lead: dict) -> MensagemGerada:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise ValueError("GEMINI_API_KEY não configurada no .env.")
    model = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
    payload = post_json(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        {
            "contents": [{"parts": [{"text": _prompt(lead)}]}],
            "generationConfig": {"responseMimeType": "application/json"},
        },
        {"x-goog-api-key": api_key, "Content-Type": "application/json"},
        timeout=60,
    )
    texto = payload["candidates"][0]["content"]["parts"][0]["text"]
    contexto, mensagem = _parse_json(texto)
    return MensagemGerada(contexto, mensagem, "Gemini", model)
