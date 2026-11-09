"""Gerador de base demonstrativa para o CRM Comercial da JPX Lab.

Permite testar e demonstrar toda a plataforma (fila, filtros, Kanban,
follow-ups, gerador de abordagem e métricas de receita) sem exigir chaves de API.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from index import calcular_score, classificar_prioridade, classificar_site, exportar_excel
from prospeccao.history import Historico

LEADS_DEMO = [
    {
        "Segmento": "Barbearia",
        "Empresa": "Barbearia Dom Imperial",
        "Cidade": "Santo André",
        "Telefone": "(11) 98765-4321",
        "Avaliações": 142,
        "Website": "",
        "Google Maps": "https://www.google.com/maps/place/Barbearia+Dom+Imperial",
    },
    {
        "Segmento": "Clínica de Estética",
        "Empresa": "Studio Lumina Estética Avançada",
        "Cidade": "São Bernardo do Campo",
        "Telefone": "(11) 97654-3210",
        "Avaliações": 198,
        "Website": "https://instagram.com/studiolumina.sbc",
        "Google Maps": "https://www.google.com/maps/place/Studio+Lumina",
    },
    {
        "Segmento": "Marcenaria",
        "Empresa": "Marcenaria Arte & Nobre Planejados",
        "Cidade": "São Caetano do Sul",
        "Telefone": "(11) 96543-2109",
        "Avaliações": 96,
        "Website": "",
        "Google Maps": "https://www.google.com/maps/place/Marcenaria+Arte+Nobre",
    },
    {
        "Segmento": "Clínica Veterinária",
        "Empresa": "VetCare Centro Veterinário 24h",
        "Cidade": "Diadema",
        "Telefone": "(11) 95432-1098",
        "Avaliações": 215,
        "Website": "",
        "Google Maps": "https://www.google.com/maps/place/VetCare+Diadema",
    },
    {
        "Segmento": "Fisioterapia",
        "Empresa": "Instituto Movimento & Coluna",
        "Cidade": "Santo André",
        "Telefone": "(11) 94321-0987",
        "Avaliações": 118,
        "Website": "https://linktr.ee/institutomovimento",
        "Google Maps": "https://www.google.com/maps/place/Instituto+Movimento",
    },
    {
        "Segmento": "Marmoraria",
        "Empresa": "Marmoraria Pedra Real ABC",
        "Cidade": "São Bernardo do Campo",
        "Telefone": "(11) 93210-9876",
        "Avaliações": 88,
        "Website": "",
        "Google Maps": "https://www.google.com/maps/place/Marmoraria+Pedra+Real",
    },
    {
        "Segmento": "Advogado",
        "Empresa": "Moura & Associados Advocacia Empresarial",
        "Cidade": "São Caetano do Sul",
        "Telefone": "(11) 92109-8765",
        "Avaliações": 74,
        "Website": "https://instagram.com/mouraadvocacia",
        "Google Maps": "https://www.google.com/maps/place/Moura+Advocacia",
    },
    {
        "Segmento": "Pet Shop",
        "Empresa": "Villa Pet Boutique & Banho",
        "Cidade": "Santo André",
        "Telefone": "(11) 91098-7654",
        "Avaliações": 164,
        "Website": "",
        "Google Maps": "https://www.google.com/maps/place/Villa+Pet+Boutique",
    },
    {
        "Segmento": "Vidraçaria",
        "Empresa": "Cristal Box & Espelhos sob Medida",
        "Cidade": "Diadema",
        "Telefone": "(11) 98877-6655",
        "Avaliações": 92,
        "Website": "",
        "Google Maps": "https://www.google.com/maps/place/Cristal+Box+Diadema",
    },
    {
        "Segmento": "Arquitetura",
        "Empresa": "Atelier Traço Contemporâneo Arquitetura",
        "Cidade": "São Caetano do Sul",
        "Telefone": "(11) 97766-5544",
        "Avaliações": 65,
        "Website": "https://beacons.ai/tracocontemporaneo",
        "Google Maps": "https://www.google.com/maps/place/Atelier+Traco",
    },
    {
        "Segmento": "Nutricionista",
        "Empresa": "Clínica NutriVida Performance",
        "Cidade": "São Bernardo do Campo",
        "Telefone": "(11) 96655-4433",
        "Avaliações": 109,
        "Website": "https://instagram.com/nutrividasbc",
        "Google Maps": "https://www.google.com/maps/place/Clinica+NutriVida",
    },
    {
        "Segmento": "Studio de Beleza",
        "Empresa": "Maison Rouge Concept Hair",
        "Cidade": "Santo André",
        "Telefone": "(11) 95544-3322",
        "Avaliações": 184,
        "Website": "",
        "Google Maps": "https://www.google.com/maps/place/Maison+Rouge+Hair",
    },
    {
        "Segmento": "Escola de Idiomas",
        "Empresa": "FluentNow English Studio",
        "Cidade": "São Bernardo do Campo",
        "Telefone": "(11) 94433-2211",
        "Avaliações": 130,
        "Website": "https://fluentnow.com.br",
        "Google Maps": "https://www.google.com/maps/place/FluentNow",
    },
    {
        "Segmento": "Psicólogo",
        "Empresa": "Espaço Equilíbrio Psicologia Clínica",
        "Cidade": "Diadema",
        "Telefone": "(11) 93322-1100",
        "Avaliações": 58,
        "Website": "",
        "Google Maps": "https://www.google.com/maps/place/Espaco+Equilibrio",
    },
]


def construir_dataframe_demo() -> pd.DataFrame:
    linhas = []
    for item in LEADS_DEMO:
        tipo_site = classificar_site(item["Website"])
        score = calcular_score(tipo_site, item["Avaliações"], item["Telefone"])
        linhas.append(
            {
                "Segmento": item["Segmento"],
                "Empresa": item["Empresa"],
                "Cidade": item["Cidade"],
                "Telefone": item["Telefone"],
                "Avaliações": item["Avaliações"],
                "Tipo Site": tipo_site,
                "Website": item["Website"],
                "Google Maps": item["Google Maps"],
                "Score": score,
                "Prioridade": classificar_prioridade(score),
            }
        )
    df = pd.DataFrame(linhas)
    return df.sort_values(by=["Score", "Avaliações"], ascending=False).reset_index(drop=True)


def gerar_ambiente_demo(
    caminho_planilha: str | Path,
    historico: Historico | None = None,
    popular_crm: bool = True,
) -> dict:
    """Cria a planilha de leads de demonstração e popula exemplos no funil CRM."""
    df = construir_dataframe_demo()
    destino = exportar_excel(df, caminho_planilha)

    if historico is not None and popular_crm:
        hoje = date.today().isoformat()
        amanha = (date.today() + timedelta(days=1)).isoformat()

        exemplos_funil = [
            {
                "lead_key": "maison rouge concept hair|5511955443322",
                "empresa": "Maison Rouge Concept Hair",
                "telefone": "5511955443322",
                "status": "Fechado",
                "servico": "Landing Page Express — R$ 149",
                "valor_proposta": 249.0,
                "proxima_acao": "",
                "contexto": "Negócio com 184 avaliações em Santo André e sem página própria para agendamentos.",
                "mensagem": (
                    "Olá, tudo bem? Sou o João Pedro, da JPX Lab.\n\n"
                    "Vi a Maison Rouge Concept Hair no Google e notei as 184 avaliações, "
                    "mas não encontrei uma página própria reunindo serviços e agendamento.\n\n"
                    "Pensei em uma estrutura enxuta para transformar essas buscas em contato direto no WhatsApp. "
                    "Posso te enviar um rascunho visual aplicado ao salão?"
                ),
                "notas": "Cliente aprovou pacote Presença Completa + Landing Page. Entrega realizada!",
            },
            {
                "lead_key": "vetcare centro veterinário 24h|5511954321098",
                "empresa": "VetCare Centro Veterinário 24h",
                "telefone": "5511954321098",
                "status": "Fechado",
                "servico": "Site Institucional — R$ 249",
                "valor_proposta": 249.0,
                "proxima_acao": "",
                "contexto": "Clínica 24h com 215 avaliações em Diadema sem site institucional.",
                "mensagem": (
                    "Oi, tudo bem? Aqui é o João Pedro, da JPX Lab.\n\n"
                    "Vi a VetCare Centro Veterinário 24h no Google com mais de 200 avaliações "
                    "e sem um site próprio destacando o plantão e especialidades.\n\n"
                    "Desenvolvi uma ideia rápida para facilitar o chamado de emergência pelo WhatsApp. "
                    "Posso compartilhar com você?"
                ),
                "notas": "Fechado Site Institucional com botão de emergência 24h.",
            },
            {
                "lead_key": "studio lumina estética avançada|5511976543210",
                "empresa": "Studio Lumina Estética Avançada",
                "telefone": "5511976543210",
                "status": "Negociação",
                "servico": "Landing Page Express — R$ 149",
                "valor_proposta": 149.0,
                "proxima_acao": hoje,
                "contexto": "Presença concentrada no Instagram com 198 avaliações no Google em SBC.",
                "mensagem": (
                    "Olá, tudo bem? Sou o João Pedro, da JPX Lab.\n\n"
                    "Vi que a presença da Studio Lumina Estética Avançada está concentrada no Instagram.\n\n"
                    "Pensei em uma página própria para organizar os procedimentos e direcionar "
                    "as avaliações pelo WhatsApp em São Bernardo do Campo. "
                    "Posso te mandar essa ideia resumida?"
                ),
                "notas": "Gestora gostou do modelo em vermelho/creme. Follow-up hoje para confirmar início.",
            },
            {
                "lead_key": "instituto movimento & coluna|5511943210987",
                "empresa": "Instituto Movimento & Coluna",
                "telefone": "5511943210987",
                "status": "Proposta",
                "servico": "Catálogo Digital — R$ 89",
                "valor_proposta": 149.0,
                "proxima_acao": hoje,
                "contexto": "Usa agregador de links simples; 118 avaliações em Santo André.",
                "mensagem": (
                    "Olá, tudo bem? Sou o João Pedro, da JPX Lab.\n\n"
                    "Vi que o Instituto Movimento & Coluna utiliza um link de bio simples para receber pacientes.\n\n"
                    "Estruturei uma sugestão para apresentar as especialidades de fisioterapia "
                    "com triagem rápida no WhatsApp. Posso te mostrar como ficaria?"
                ),
                "notas": "Proposta enviada de Landing Page Express (R$ 149). Cobrar retorno hoje.",
            },
            {
                "lead_key": "cristal box & espelhos sob medida|5511988776655",
                "empresa": "Cristal Box & Espelhos sob Medida",
                "telefone": "5511988776655",
                "status": "Respondeu",
                "servico": "Catálogo Digital — R$ 89",
                "valor_proposta": 89.0,
                "proxima_acao": amanha,
                "contexto": "Vidraçaria bem avaliada em Diadema (92 avaliações) sem catálogo online.",
                "mensagem": (
                    "Oi, tudo bem? Aqui é o João Pedro, da JPX Lab.\n\n"
                    "Vi a Cristal Box & Espelhos sob Medida no Google e notei que ainda não há um "
                    "catálogo digital reunindo modelos de box e espelhos para orçamento.\n\n"
                    "Pensei em uma forma prática de agilizar os pedidos de medida pelo WhatsApp. "
                    "Posso te enviar um exemplo?"
                ),
                "notas": "Dono respondeu pedindo exemplo de catálogo com fotos de obras.",
            },
        ]

        status_atuais = historico.status_por_lead()
        for ex in exemplos_funil:
            if ex["lead_key"] not in status_atuais:
                historico.salvar(
                    lead_key=ex["lead_key"],
                    empresa=ex["empresa"],
                    telefone=ex["telefone"],
                    status=ex["status"],
                    contexto=ex["contexto"],
                    mensagem=ex["mensagem"],
                    provider="modelo local",
                    model="demo-seed",
                    servico=ex["servico"],
                    valor_proposta=ex["valor_proposta"],
                    proxima_acao=ex["proxima_acao"],
                    notas=ex["notas"],
                )

    return {
        "ok": True,
        "arquivo": destino.name,
        "total_leads": len(df),
    }
