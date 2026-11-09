"""Ponte IPC JSON entre o núcleo nativo em Rust (jpx-crm) e os módulos Python.

Permite que o binário Rust invoque operações de dados, IA, scoring,
planilhas Excel e funil SQLite com contratos JSON tipados.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
BASE_DIR = SCRIPT_DIR.parent
sys.path = [p for p in sys.path if Path(p or ".").resolve() != SCRIPT_DIR]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from prospeccao.ai import gerar_mensagem
from prospeccao.config import carregar_env
from prospeccao.demo import gerar_ambiente_demo
from prospeccao.history import Historico
from prospeccao.leads import adicionar_lead_manual, carregar_leads
from scripts.security_scan import analisar

carregar_env(BASE_DIR / ".env")


def _caminhos() -> tuple[Path, Path]:
    leads_file = Path(os.getenv("LEADS_FILE", "Leads_ABC_Paulista.xlsx"))
    if not leads_file.is_absolute():
        leads_file = BASE_DIR / leads_file
    db_file = Path(os.getenv("HISTORY_DB", str(BASE_DIR / "data" / "prospeccao.db")))
    return leads_file, db_file


def cmd_stats() -> dict:
    leads_file, db_file = _caminhos()
    historico = Historico(db_file)
    crm = historico.resumo()
    total_leads = 0
    elegiveis = 0
    alta_prio = 0
    if leads_file.exists():
        df = carregar_leads(leads_file)
        total_leads = len(df)
        elegiveis = int(df["WhatsApp elegível"].sum())
        alta_prio = int((df["Prioridade"] == "Alta").sum())
    return {
        "ok": True,
        "leads_file": leads_file.name,
        "leads_file_exists": leads_file.exists(),
        "total_leads": total_leads,
        "whatsapp_elegiveis": elegiveis,
        "prioridade_alta": alta_prio,
        "contatos_hoje": historico.contatos_hoje(),
        "limite_diario": int(os.getenv("DAILY_CONTACT_LIMIT", "10")),
        "followups_pendentes": len(historico.followups_pendentes()),
        "crm": crm,
    }


def cmd_seed_demo(popular_crm: bool = True) -> dict:
    leads_file, db_file = _caminhos()
    historico = Historico(db_file)
    return gerar_ambiente_demo(leads_file, historico=historico, popular_crm=popular_crm)


def cmd_generate(
    empresa: str,
    segmento: str,
    cidade: str,
    tipo_site: str,
    avaliacoes: int,
    provider: str,
    tom: str,
    servico: str,
    observacao: str,
    etapa: str,
) -> dict:
    lead = {
        "Empresa": empresa,
        "Segmento": segmento,
        "Cidade": cidade,
        "Tipo Site": tipo_site,
        "Avaliações": avaliacoes,
    }
    res = gerar_mensagem(lead, provider, tom, servico, observacao, etapa=etapa)
    return {
        "ok": True,
        "contexto": res.contexto,
        "mensagem": res.mensagem,
        "provider": res.provider,
        "model": res.model,
        "etapa": etapa,
    }


def cmd_doctor() -> dict:
    leads_file, db_file = _caminhos()
    problemas_seguranca = analisar(BASE_DIR)
    return {
        "ok": len(problemas_seguranca) == 0,
        "python_version": sys.version.split()[0],
        "leads_file": str(leads_file.name),
        "leads_exists": leads_file.exists(),
        "db_file": str(db_file.relative_to(BASE_DIR)) if db_file.is_relative_to(BASE_DIR) else str(db_file),
        "security_issues": problemas_seguranca,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="JPX Lab Python Bridge for Rust Engine")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("stats")
    demo_p = sub.add_parser("seed-demo")
    demo_p.add_argument("--no-crm", action="store_true")

    gen_p = sub.add_parser("generate")
    gen_p.add_argument("--empresa", default="Empresa Exemplo")
    gen_p.add_argument("--segmento", default="Barbearia")
    gen_p.add_argument("--cidade", default="Santo André")
    gen_p.add_argument("--tipo-site", default="Sem Site")
    gen_p.add_argument("--avaliacoes", type=int, default=120)
    gen_p.add_argument("--provider", default="Modelo local")
    gen_p.add_argument("--tom", default="Consultivo")
    gen_p.add_argument("--servico", default="Landing Page Express — R$ 149")
    gen_p.add_argument("--observacao", default="")
    gen_p.add_argument("--etapa", default="Primeiro contato")

    add_p = sub.add_parser("add-lead")
    add_p.add_argument("--empresa", required=True)
    add_p.add_argument("--segmento", default="Negócio Local")
    add_p.add_argument("--cidade", default="Santo André")
    add_p.add_argument("--telefone", required=True)
    add_p.add_argument("--avaliacoes", type=int, default=80)
    add_p.add_argument("--website", default="")

    sub.add_parser("doctor")

    args = parser.parse_args()
    try:
        if args.command == "stats":
            saida = cmd_stats()
        elif args.command == "seed-demo":
            saida = cmd_seed_demo(popular_crm=not args.no_crm)
        elif args.command == "generate":
            saida = cmd_generate(
                empresa=args.empresa,
                segmento=args.segmento,
                cidade=args.cidade,
                tipo_site=args.tipo_site,
                avaliacoes=args.avaliacoes,
                provider=args.provider,
                tom=args.tom,
                servico=args.servico,
                observacao=args.observacao,
                etapa=args.etapa,
            )
        elif args.command == "add-lead":
            leads_file, _ = _caminhos()
            novo = adicionar_lead_manual(
                leads_file,
                empresa=args.empresa,
                segmento=args.segmento,
                cidade=args.cidade,
                telefone=args.telefone,
                avaliacoes=args.avaliacoes,
                website=args.website,
            )
            saida = {"ok": True, "lead": novo}
        elif args.command == "doctor":
            saida = cmd_doctor()
        else:
            saida = {"ok": False, "error": "Comando desconhecido"}
        print(json.dumps(saida, ensure_ascii=False))
        return 0
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
