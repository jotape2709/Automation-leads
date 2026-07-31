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


ANGULOS = {
    "Diagnóstico Digital — R$ 49": "identificar prioridades simples para melhorar a jornada entre descoberta e contato",
    "Cartão Digital — R$ 49": "reunir apresentação, serviços e contatos em um material fácil de compartilhar",
    "Página de Links — R$ 59": "organizar os principais caminhos de contato em uma página objetiva",
    "Google Profissional — R$ 69": "deixar serviços e informações mais claros para quem encontra o negócio no Google",
    "Kit Social Inicial — R$ 69": "dar consistência às primeiras peças de comunicação",
    "Logo Essencial — R$ 79": "construir uma apresentação visual mais reconhecível e consistente",
    "Planilha Essencial — R$ 79": "organizar um controle operacional que hoje pode estar disperso",
    "Catálogo Digital — R$ 89": "organizar produtos ou serviços para consulta e contato pelo WhatsApp",
    "E-mail Profissional — R$ 89": "fortalecer a apresentação da empresa nos contatos por e-mail",
    "Landing Page Express — R$ 149": "centralizar serviços, diferenciais e contato em uma página própria",
    "Dashboard Express — R$ 149": "transformar dados operacionais em indicadores fáceis de acompanhar",
    "Automação Essencial — R$ 149": "reduzir uma tarefa repetitiva sem complicar a rotina",
    "Site Institucional — R$ 249": "estruturar uma presença própria com informações e contato bem organizados",
    "Presença Completa — R$ 249": "alinhar identidade, página, Google e comunicação em uma presença consistente",
}


def _prompt(
    lead: dict,
    tom: str = "Consultivo",
    servico: str = "Landing Page Express — R$ 149",
    observacao: str = "",
) -> str:
    nome = os.getenv("PROSPECTOR_NAME", "João Pedro")
    empresa_remetente = os.getenv("BUSINESS_NAME", "JPX Lab")
    dados = {
        "empresa": lead.get("Empresa"),
        "segmento": lead.get("Segmento"),
        "cidade": lead.get("Cidade"),
        "avaliacoes": lead.get("Avaliações"),
        "tipo_site": lead.get("Tipo Site"),
        "website": lead.get("Website"),
        "google_maps": lead.get("Google Maps"),
    }
    oportunidade = ANGULOS.get(servico, ANGULOS["Diagnóstico Digital — R$ 49"])
    return f"""
Você é um SDR consultivo da JPX Lab. Escreva uma primeira abordagem individual
para um pequeno negócio local. O objetivo é conquistar permissão para continuar,
e não vender ou fechar no primeiro contato.

Use somente estes dados: {json.dumps(dados, ensure_ascii=False, default=str)}
Observação manual confirmada: {observacao.strip() or "nenhuma"}
Remetente: {nome}, da {empresa_remetente}
Oferta selecionada: {servico}
Oportunidade que a oferta resolve: {oportunidade}
Tom: {tom}

Regras:
- escolha um único gancho factual;
- trate inferências como possibilidade;
- fale do benefício para o cliente final, sem jargão;
- não mencione preço no primeiro contato;
- escreva 45 a 75 palavras em 3 ou 4 blocos curtos;
- termine com uma pergunta simples pedindo permissão para enviar uma ideia;
- não use emojis, urgência falsa, elogio genérico, promessa de resultado,
  “gostaria de oferecer”, “sem compromisso” ou listas de serviços;
- não afirme ter acessado Instagram, fotos ou avaliações individuais.

Retorne JSON válido com exatamente:
{{"contexto":"gancho e justificativa em até 2 frases","mensagem":"texto final"}}
""".strip()


def mensagem_fallback(
    lead: dict,
    tom: str = "Consultivo",
    servico: str = "Landing Page Express — R$ 149",
    observacao: str = "",
) -> MensagemGerada:
    nome = os.getenv("PROSPECTOR_NAME", "João Pedro")
    marca = os.getenv("BUSINESS_NAME", "JPX Lab")
    empresa = str(lead.get("Empresa", "seu negócio"))
    segmento = str(lead.get("Segmento", "negócio local")).lower()
    cidade = str(lead.get("Cidade", "ABC Paulista"))
    tipo_site = str(lead.get("Tipo Site", "Não verificado"))
    avaliacoes = int(lead.get("Avaliações", 0) or 0)
    oportunidade = ANGULOS.get(servico, ANGULOS["Diagnóstico Digital — R$ 49"])

    if observacao.strip():
        gancho = observacao.strip().rstrip(".")
        abertura = f"Notei um ponto específico sobre a {empresa}: {gancho}."
    elif tipo_site == "Sem Site":
        gancho = "não há um site próprio registrado"
        abertura = (
            f"Vi a {empresa} no Google e não encontrei uma página própria "
            "reunindo as informações do negócio."
        )
    elif tipo_site == "Rede Social":
        gancho = "a presença digital está concentrada em rede social"
        abertura = f"Vi que a presença da {empresa} está concentrada em rede social."
    else:
        gancho = f"o negócio reúne {avaliacoes} avaliações no Google"
        abertura = (
            f"A {empresa} já possui uma presença relevante no Google, "
            f"com {avaliacoes} avaliações."
        )

    introducoes = {
        "Direto": f"Oi, tudo bem? Aqui é o {nome}, da {marca}.",
        "Conversacional": f"Oi! Tudo certo por aí? Sou o {nome}, da {marca}.",
        "Consultivo": f"Olá, tudo bem? Sou o {nome}, da {marca}.",
    }
    mensagem = (
        f"{introducoes.get(tom, introducoes['Consultivo'])}\n\n"
        f"{abertura}\n\n"
        f"Pensei em uma forma simples de {oportunidade}, facilitando o próximo "
        f"passo para quem procura {segmento} em {cidade}. "
        f"Posso te enviar uma ideia curta aplicada à {empresa}?"
    )
    return MensagemGerada(
        contexto=(
            f"Gancho usado: {gancho}. A oportunidade foi conectada à oferta "
            "sem presumir informações não fornecidas."
        ),
        mensagem=mensagem,
        provider="modelo local",
        model="fallback",
    )


def gerar_mensagem(
    lead: dict,
    provider: str,
    tom: str = "Consultivo",
    servico: str = "Landing Page Express — R$ 149",
    observacao: str = "",
) -> MensagemGerada:
    provider = provider.lower().strip()
    if provider == "openai":
        return _gerar_openai(lead, tom, servico, observacao)
    if provider == "gemini":
        return _gerar_gemini(lead, tom, servico, observacao)
    return mensagem_fallback(lead, tom, servico, observacao)


def _parse_json(texto: str) -> tuple[str, str]:
    limpo = texto.strip().removeprefix("```json").removesuffix("```").strip()
    objeto = json.loads(limpo)
    contexto = str(objeto.get("contexto", "")).strip()
    mensagem = str(objeto.get("mensagem", "")).strip()
    if not contexto or not mensagem:
        raise ValueError("A IA não retornou contexto e mensagem válidos.")
    return contexto, mensagem


def _gerar_openai(
    lead: dict, tom: str, servico: str, observacao: str
) -> MensagemGerada:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise ValueError("OPENAI_API_KEY não configurada no .env.")
    model = os.getenv("OPENAI_MODEL", "gpt-5.6-luna")
    payload = post_json(
        "https://api.openai.com/v1/responses",
        {
            "model": model,
            "input": _prompt(lead, tom, servico, observacao),
            "max_output_tokens": 500,
        },
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


def _gerar_gemini(
    lead: dict, tom: str, servico: str, observacao: str
) -> MensagemGerada:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise ValueError("GEMINI_API_KEY não configurada no .env.")
    model = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
    payload = post_json(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        {
            "contents": [
                {"parts": [{"text": _prompt(lead, tom, servico, observacao)}]}
            ],
            "generationConfig": {"responseMimeType": "application/json"},
        },
        {"x-goog-api-key": api_key, "Content-Type": "application/json"},
        timeout=60,
    )
    texto = payload["candidates"][0]["content"]["parts"][0]["text"]
    contexto, mensagem = _parse_json(texto)
    return MensagemGerada(contexto, mensagem, "Gemini", model)
