"""Painel web local para prospecção assistida.

Execute com `python app.py` e abra http://127.0.0.1:8765.
Nenhum endpoint deste servidor envia mensagens ao WhatsApp.
"""

from __future__ import annotations

import json
import os
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pandas as pd

from prospeccao.ai import gerar_mensagem
from prospeccao.config import carregar_env
from prospeccao.history import Historico
from prospeccao.leads import carregar_leads, filtrar_elegiveis

BASE_DIR = Path(__file__).resolve().parent
carregar_env(BASE_DIR / ".env")
STATIC_FILE = BASE_DIR / "static" / "index.html"
LEADS_FILE = Path(os.getenv("LEADS_FILE", "Leads_ABC_Paulista.xlsx"))
if not LEADS_FILE.is_absolute():
    LEADS_FILE = BASE_DIR / LEADS_FILE
DB_FILE = Path(os.getenv("HISTORY_DB", str(BASE_DIR / "data" / "prospeccao.db")))
HISTORICO = Historico(DB_FILE)
ALLOWED_STATUS = {"Rascunho", "Contatado", "Ignorado", "Bloqueado", "Respondeu", "Reunião"}


def chave_lead(row: pd.Series | dict) -> str:
    return f"{row['Empresa']}|{row['Telefone E164']}".casefold().strip()


def carregar_base() -> pd.DataFrame:
    df = carregar_leads(LEADS_FILE)
    df["Chave"] = df.apply(chave_lead, axis=1)
    status = HISTORICO.status_por_lead()
    df["Status abordagem"] = df["Chave"].map(status).fillna("Não abordado")
    return df


def limpar_valor(valor):
    if pd.isna(valor):
        return None
    if hasattr(valor, "item"):
        return valor.item()
    return valor


def serializar_linhas(df: pd.DataFrame) -> list[dict]:
    return [{k: limpar_valor(v) for k, v in row.items()} for row in df.to_dict("records")]


class Handler(BaseHTTPRequestHandler):
    server_version = "JPXProspeccao/1.0"

    def log_message(self, fmt, *args):
        print(f"[{self.log_date_time_string()}] {fmt % args}")

    def _json(self, payload, status=HTTPStatus.OK):
        body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        length = int(self.headers.get("Content-Length", "0"))
        return json.loads(self.rfile.read(length) or b"{}")

    def _erro(self, mensagem, status=HTTPStatus.BAD_REQUEST):
        self._json({"error": mensagem}, status)

    def do_GET(self):
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/":
                body = STATIC_FILE.read_bytes()
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if parsed.path == "/api/leads":
                self._listar_leads(parse_qs(parsed.query))
                return
            if parsed.path == "/api/history":
                self._json({"items": serializar_linhas(HISTORICO.dataframe())})
                return
            if parsed.path == "/api/health":
                self._json({"ok": True, "leads_file": LEADS_FILE.name})
                return
            self._erro("Rota não encontrada.", HTTPStatus.NOT_FOUND)
        except FileNotFoundError:
            self._erro(f"Planilha não encontrada: {LEADS_FILE}", HTTPStatus.NOT_FOUND)
        except Exception as exc:
            self._erro(str(exc), HTTPStatus.INTERNAL_SERVER_ERROR)

    def do_POST(self):
        try:
            if self.path == "/api/generate":
                self._gerar()
                return
            if self.path == "/api/status":
                self._atualizar_status()
                return
            self._erro("Rota não encontrada.", HTTPStatus.NOT_FOUND)
        except Exception as exc:
            self._erro(str(exc), HTTPStatus.INTERNAL_SERVER_ERROR)

    def _listar_leads(self, query):
        df = carregar_base()
        prioridades = query.get("prioridade", ["Alta"])
        tipos = query.get("tipo", ["Sem Site"])
        cidades = query.get("cidade", [])
        incluir = query.get("incluir_abordados", ["false"])[0] == "true"
        fila = filtrar_elegiveis(df, prioridades, tipos, cidades)
        if not incluir:
            fila = fila[fila["Status abordagem"].isin(["Não abordado", "Rascunho"])]
        resumo = {
            "total": len(df),
            "celulares": int(df["WhatsApp elegível"].sum()),
            "fila": len(fila),
            "contatos_hoje": HISTORICO.contatos_hoje(),
            "limite_diario": int(os.getenv("DAILY_CONTACT_LIMIT", "10")),
            "arquivo": LEADS_FILE.name,
        }
        self._json({"summary": resumo, "items": serializar_linhas(fila)})

    def _encontrar(self, key: str) -> dict:
        df = carregar_base()
        encontrado = df[df["Chave"] == key]
        if encontrado.empty:
            raise ValueError("Lead não encontrado na planilha.")
        return encontrado.iloc[0].to_dict()

    def _gerar(self):
        body = self._body()
        key = str(body.get("lead_key", ""))
        provider = str(body.get("provider", "Modelo local"))
        tom = str(body.get("tom", "Consultivo"))
        servico = str(body.get("servico", "Site / landing page"))
        observacao = str(body.get("observacao", ""))[:500]
        lead = self._encontrar(key)
        gerada = gerar_mensagem(lead, provider, tom, servico, observacao)
        HISTORICO.salvar(
            key, lead["Empresa"], lead["Telefone E164"], "Rascunho",
            gerada.contexto, gerada.mensagem, gerada.provider, gerada.model,
        )
        self._json({
            "contexto": gerada.contexto,
            "mensagem": gerada.mensagem,
            "provider": gerada.provider,
            "model": gerada.model,
        })

    def _atualizar_status(self):
        body = self._body()
        key = str(body.get("lead_key", ""))
        novo_status = str(body.get("status", ""))
        if novo_status not in ALLOWED_STATUS:
            raise ValueError("Status inválido.")
        if novo_status == "Contatado":
            limite = int(os.getenv("DAILY_CONTACT_LIMIT", "10"))
            if HISTORICO.contatos_hoje() >= limite:
                raise ValueError("Limite diário de contatos atingido.")
        lead = self._encontrar(key)
        HISTORICO.salvar(
            key, lead["Empresa"], lead["Telefone E164"], novo_status,
            str(body.get("contexto", "")), str(body.get("mensagem", "")),
            str(body.get("provider", "")), str(body.get("model", "")),
        )
        self._json({"ok": True, "status": novo_status})


def main():
    host = os.getenv("APP_HOST", "127.0.0.1")
    port = int(os.getenv("APP_PORT", "8765"))
    if not STATIC_FILE.exists():
        raise SystemExit(f"Interface não encontrada: {STATIC_FILE}")
    servidor = ThreadingHTTPServer((host, port), Handler)
    url = f"http://{host}:{port}"
    print(f"Painel disponível em {url}")
    print("Pressione Ctrl+C para encerrar.")
    if os.getenv("OPEN_BROWSER", "1") == "1":
        webbrowser.open(url)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nPainel encerrado.")
    finally:
        servidor.server_close()


if __name__ == "__main__":
    main()
