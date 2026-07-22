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


def _prompt(
    lead: dict,
    tom: str = "Consultivo",
    servico: str = "Site / landing page",
    observacao: str = "",
) -> str:
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
Você é um SDR consultivo da JPX Lab especializado em primeira abordagem para
pequenos negócios locais. Seu objetivo NÃO é vender no primeiro contato: é mostrar
que a mensagem foi pensada para aquele negócio e conquistar permissão para continuar.

REGRA DE VERACIDADE
Use somente os dados abaixo. Não diga que acessou Instagram, site, fotos, cardápio,
agenda ou avaliações individuais. Não invente elogios, problemas, resultados ou
características. Inferências devem ser apresentadas como possibilidade, nunca como fato.

Dados do lead: {json.dumps(dados, ensure_ascii=False, default=str)}
Observação manual confirmada pelo usuário: {observacao.strip() or "nenhuma"}
Remetente: {nome}, da {empresa_remetente}
Serviço escolhido para esta abordagem: {servico}
Tom escolhido: {tom}
Portfólio: {portfolio}

RACIOCÍNIO COMERCIAL
1. Escolha UM único gancho factual mais forte. Exemplos: ausência de site próprio;
   presença restrita a rede social; volume de avaliações que já gera prova social;
   contexto local da cidade; ou a observação manual.
2. Conecte esse gancho a UMA oportunidade coerente com o segmento e com o serviço.
3. Fale do benefício para o cliente final do lead, não de tecnologia.
4. Termine com uma pergunta fácil de responder, pedindo permissão para enviar uma
   ideia curta. Não peça reunião, orçamento ou decisão no primeiro contato.

ESTRUTURA OBRIGATÓRIA DA MENSAGEM
- 45 a 75 palavras, em português brasileiro natural;
- 3 ou 4 blocos curtos separados por linha em branco;
- abertura humana e breve, variando entre as mensagens;
- observação específica sobre o negócio;
- ideia concreta em linguagem simples;
- pergunta final de baixo atrito;
- sem link de portfólio no primeiro contato, a menos que a observação peça isso.

EVITE COMPLETAMENTE
"encontrei ao pesquisar", "gostaria de oferecer", "trabalho com sites e automações",
listas de serviços, jargão, urgência falsa, promessa de resultado, elogio genérico,
"sem compromisso", mais de um ponto de exclamação e qualquer emoji.

TOM
- Consultivo: diagnóstico leve, calmo e respeitoso.
- Direto: objetivo, frases curtas, sem introdução longa.
- Conversacional: próximo e natural, sem informalidade excessiva.

Retorne JSON válido com exatamente duas chaves:
- "contexto": em até 2 frases, informe o gancho usado e por que ele é pertinente;
- "mensagem": a mensagem pronta, preservando as quebras de linha.
""".strip()


def mensagem_fallback(
    lead: dict,
    tom: str = "Consultivo",
    servico: str = "Site / landing page",
    observacao: str = "",
) -> MensagemGerada:
    nome = os.getenv("PROSPECTOR_NAME", "João Pedro")
    marca = os.getenv("BUSINESS_NAME", "JPX Lab")
    empresa = str(lead.get("Empresa", "seu negócio"))
    segmento = str(lead.get("Segmento", "negócio local")).lower()
    cidade = str(lead.get("Cidade", "ABC Paulista"))
    tipo_site = str(lead.get("Tipo Site", "Não verificado"))
    avaliacoes = int(lead.get("Avaliações", 0) or 0)
    angulos = {
        "Site / landing page": "centralizar serviços, diferenciais e contato em uma página própria",
        "Automação de atendimento": "organizar o primeiro atendimento e reduzir perguntas repetidas no WhatsApp",
        "Identidade visual": "deixar a apresentação visual mais consistente nos pontos de contato",
        "Diagnóstico digital": "organizar a jornada entre a descoberta no Google e o contato pelo WhatsApp",
    }
    oportunidade = angulos.get(servico, angulos["Diagnóstico digital"])
    if observacao.strip():
        gancho = observacao.strip()
        abertura = f"Notei um ponto específico sobre a {empresa}: {gancho.rstrip('.')}."
    elif tipo_site == "Sem Site":
        gancho = "a empresa aparece no Google, mas não há um site próprio registrado"
        abertura = f"Vi a {empresa} no Google e não encontrei um site próprio reunindo as informações do negócio."
    elif tipo_site == "Rede Social":
        gancho = "a presença digital está concentrada em rede social"
        abertura = f"Vi que a presença digital da {empresa} está concentrada em rede social."
    else:
        gancho = f"o negócio já reúne {avaliacoes} avaliações no Google"
        abertura = f"A {empresa} já reúne uma presença relevante no Google, com {avaliacoes} avaliações."
    introducoes = {
        "Direto": f"Oi, tudo bem? Aqui é o {nome}, da {marca}.",
        "Conversacional": f"Oi! Tudo certo por aí? Sou o {nome}, da {marca}.",
        "Consultivo": f"Olá, tudo bem? Sou o {nome}, da {marca}.",
    }
    mensagem = (
        f"{introducoes.get(tom, introducoes['Consultivo'])}\n\n"
        f"{abertura}\n\n"
        f"Pensei em uma forma simples de {oportunidade}, facilitando o próximo passo para quem já procura "
        f"{segmento} em {cidade}. Posso te enviar uma ideia rápida aplicada à {empresa}?"
    )
    return MensagemGerada(
        contexto=f"Gancho usado: {gancho}. A oportunidade foi conectada a {servico.lower()} sem presumir informações não fornecidas.",
        mensagem=mensagem,
        provider="modelo local",
        model="fallback",
    )


def gerar_mensagem(
    lead: dict,
    provider: str,
    tom: str = "Consultivo",
    servico: str = "Site / landing page",
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


def _gerar_openai(lead: dict, tom: str, servico: str, observacao: str) -> MensagemGerada:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise ValueError("OPENAI_API_KEY não configurada no .env.")
    model = os.getenv("OPENAI_MODEL", "gpt-5.6-luna")
    payload = post_json(
        "https://api.openai.com/v1/responses",
        {"model": model, "input": _prompt(lead, tom, servico, observacao), "max_output_tokens": 500},
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


def _gerar_gemini(lead: dict, tom: str, servico: str, observacao: str) -> MensagemGerada:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise ValueError("GEMINI_API_KEY não configurada no .env.")
    model = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
    payload = post_json(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        {
            "contents": [{"parts": [{"text": _prompt(lead, tom, servico, observacao)}]}],
            "generationConfig": {"responseMimeType": "application/json"},
        },
        {"x-goog-api-key": api_key, "Content-Type": "application/json"},
        timeout=60,
    )
    texto = payload["candidates"][0]["content"]["parts"][0]["text"]
    contexto, mensagem = _parse_json(texto)
    return MensagemGerada(contexto, mensagem, "Gemini", model)
