"""Painel local de prospecção, Cofre Criptográfico e CRM da JPX Lab.

Execute com ``python app.py``, ``cargo run --release`` ou clicando nos executáveis
``Iniciar_JPX_CRM.bat`` (Windows) / ``Iniciar_JPX_CRM.sh`` (Linux) / ``Iniciar_JPX_CRM.command`` (macOS).
O sistema prepara e registra abordagens, mas nunca envia mensagens sozinho.
"""

from __future__ import annotations

import hmac
import ipaddress
import json
import os
import socket
import subprocess
import sys
import urllib.request
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

BASE_DIR = Path(__file__).resolve().parent


def _garantir_dependencias() -> None:
    """Garante que pandas e openpyxl estejam disponíveis, criando/usando .venv automaticamente."""
    try:
        import openpyxl  # noqa: F401
        import pandas  # noqa: F401
        return
    except ImportError:
        pass

    venv_py = (
        BASE_DIR / ".venv" / "Scripts" / "python.exe"
        if os.name == "nt"
        else BASE_DIR / ".venv" / "bin" / "python"
    )
    if not venv_py.exists():
        print("⚙ Configurando ambiente virtual Python (.venv) pela primeira vez...")
        subprocess.run([sys.executable, "-m", "venv", str(BASE_DIR / ".venv")], check=True)

    check = subprocess.run(
        [str(venv_py), "-c", "import pandas, openpyxl"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if check.returncode != 0:
        print("📦 Instalando dependências de dados e planilhas em .venv...")
        subprocess.run(
            [str(venv_py), "-m", "pip", "install", "-q", "-r", str(BASE_DIR / "requirements.txt")],
            check=True,
        )

    if Path(sys.executable).resolve() != venv_py.resolve():
        os.execv(str(venv_py), [str(venv_py), __file__, *sys.argv[1:]])


if __name__ == "__main__":
    _garantir_dependencias()

import pandas as pd  # noqa: E402

from index import coletar_leads, exportar_excel  # noqa: E402
from prospeccao.ai import gerar_mensagem  # noqa: E402
from prospeccao.config import carregar_env  # noqa: E402
from prospeccao.demo import gerar_ambiente_demo  # noqa: E402
from prospeccao.history import Historico  # noqa: E402
from prospeccao.leads import (  # noqa: E402
    adicionar_lead_manual,
    carregar_leads,
    explicar_score,
    filtrar_elegiveis,
)
from prospeccao.vault import CofreCredenciais  # noqa: E402

carregar_env(BASE_DIR / ".env")
STATIC_FILE = BASE_DIR / "static" / "index.html"
LOGO_FILE = BASE_DIR / "static" / "logo.png"
LEADS_FILE = Path(os.getenv("LEADS_FILE", "Leads_ABC_Paulista.xlsx"))
if not LEADS_FILE.is_absolute():
    LEADS_FILE = BASE_DIR / LEADS_FILE
DB_FILE = Path(os.getenv("HISTORY_DB", str(BASE_DIR / "data" / "prospeccao.db")))
VAULT_FILE = Path(os.getenv("VAULT_FILE", str(DB_FILE.parent / "vault.enc")))

HISTORICO = Historico(DB_FILE)
VAULT = CofreCredenciais(VAULT_FILE)

ALLOWED_STATUS = {
    "Rascunho",
    "Contatado",
    "Respondeu",
    "Proposta",
    "Negociação",
    "Fechado",
    "Perdido",
    "Ignorado",
    "Bloqueado",
}


def chave_lead(row: pd.Series | dict) -> str:
    return f"{row['Empresa']}|{row['Telefone E164']}".casefold().strip()


def carregar_base() -> pd.DataFrame:
    if not LEADS_FILE.exists():
        gerar_ambiente_demo(LEADS_FILE, historico=HISTORICO, popular_crm=True)
    df = carregar_leads(LEADS_FILE)
    df["Chave"] = df.apply(chave_lead, axis=1)
    status = HISTORICO.status_por_lead()
    df["Status abordagem"] = [
        status.get(chave, "Não abordado") for chave in df["Chave"]
    ]
    return df


def limpar_valor(valor):
    if pd.isna(valor):
        return None
    if hasattr(valor, "item"):
        return valor.item()
    return valor


def serializar_linhas(df: pd.DataFrame) -> list[dict]:
    return [
        {k: limpar_valor(v) for k, v in row.items()}
        for row in df.to_dict("records")
    ]


class Handler(BaseHTTPRequestHandler):
    server_version = "JPXCRM/3.2"
    sys_version = ""

    def log_message(self, fmt, *args):
        print(f"[{self.log_date_time_string()}] {fmt % args}")

    def _security_headers(self):
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Security-Policy", (
            "default-src 'self'; script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
            "connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; "
            "form-action 'none'"
        ))
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")

    def _json(self, payload, status=HTTPStatus.OK):
        body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._security_headers()
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        tipo = self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        if tipo != "application/json":
            raise ValueError("Content-Type deve ser application/json.")
        try:
            length = int(self.headers.get("Content-Length", "0"))
            limite = int(os.getenv("MAX_REQUEST_BODY_BYTES", "65536"))
        except ValueError as exc:
            raise ValueError("Tamanho de requisição inválido.") from exc
        if length <= 0 or length > limite:
            raise ValueError("Corpo da requisição vazio ou acima do limite.")
        try:
            return json.loads(self.rfile.read(length))
        except json.JSONDecodeError as exc:
            raise ValueError("Corpo JSON inválido.") from exc

    def _erro(self, mensagem, status=HTTPStatus.BAD_REQUEST):
        self._json({"error": mensagem}, status)

    def _validar_origem(self):
        try:
            cliente = ipaddress.ip_address(self.client_address[0])
        except ValueError:
            self._erro("Origem de rede inválida.", HTTPStatus.FORBIDDEN)
            return False
        if not cliente.is_loopback:
            self._erro("Acesso permitido apenas no computador local.", HTTPStatus.FORBIDDEN)
            return False
        host = urlparse(f"//{self.headers.get('Host', '')}").hostname
        if host not in {"127.0.0.1", "localhost", "::1"}:
            self._erro("Host não autorizado.", HTTPStatus.FORBIDDEN)
            return False
        origem = self.headers.get("Origin")
        if origem:
            parsed = urlparse(origem)
            try:
                porta_origem = parsed.port
            except ValueError:
                porta_origem = None
            if (
                parsed.scheme != "http"
                or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
                or porta_origem != self.server.server_port
            ):
                self._erro("Origem não autorizada.", HTTPStatus.FORBIDDEN)
                return False
        return True

    def _validar_csrf_se_presente(self) -> None:
        token = self.headers.get("X-JPX-Token")
        if token and not hmac.compare_digest(token, VAULT.token_sessao):
            raise ValueError("Token de sessão de segurança inválido ou expirado.")

    def do_GET(self):
        if not self._validar_origem():
            return
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/":
                body = STATIC_FILE.read_bytes()
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self._security_headers()
                self.end_headers()
                self.wfile.write(body)
                return
            if parsed.path in {"/logo.png", "/static/logo.png"} and LOGO_FILE.exists():
                body = LOGO_FILE.read_bytes()
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "image/png")
                self.send_header("Content-Length", str(len(body)))
                self._security_headers()
                self.end_headers()
                self.wfile.write(body)
                return
            if parsed.path == "/api/leads":
                self._listar_leads(parse_qs(parsed.query))
                return
            if parsed.path == "/api/lead-events":
                q = parse_qs(parsed.query)
                key = q.get("lead_key", [""])[0]
                self._json({"items": HISTORICO.eventos_por_lead(key)})
                return
            if parsed.path == "/api/history":
                self._json({"items": serializar_linhas(HISTORICO.dataframe())})
                return
            if parsed.path == "/api/followups":
                self._json({"items": HISTORICO.followups_pendentes()})
                return
            if parsed.path == "/api/dashboard":
                self._json(HISTORICO.resumo())
                return
            if parsed.path == "/api/settings":
                estado = VAULT.estado_publico()
                estado["csrf_token"] = VAULT.token_sessao
                estado["seguranca_ativa"] = [
                    "Isolamento estrito em Loopback (127.0.0.1)",
                    "Cofre Criptográfico AEAD (PBKDF2-HMAC-SHA256 600k iter + CTR-HMAC-SHA256)",
                    "Comparação de MAC e Tokens em Tempo Constante (hmac.compare_digest)",
                    "Proteção Anti-XSS (DOM estrito sem HTML dinâmico) e CSP ativa",
                    "Neutralização de fórmulas em planilhas (.xlsx) e proteção Anti-ZipBomb",
                    "Redação automática de chaves de API em logs e mensagens de erro",
                ]
                self._json(estado)
                return
            if parsed.path == "/api/health":
                self._json(
                    {
                        "ok": True,
                        "version": "3.2",
                        "engine": "hybrid-rust-python",
                        "leads_file": LEADS_FILE.name,
                        "has_leads_file": LEADS_FILE.exists(),
                        "vault_locked": VAULT.esta_bloqueado(),
                    }
                )
                return
            self._erro("Rota não encontrada.", HTTPStatus.NOT_FOUND)
        except FileNotFoundError:
            self._erro("Planilha de leads não encontrada.", HTTPStatus.NOT_FOUND)
        except ValueError as exc:
            self._erro(str(exc))
        except Exception as exc:
            print(f"Erro interno em GET: {type(exc).__name__}")
            self._erro("Falha interna ao processar a solicitação.", HTTPStatus.INTERNAL_SERVER_ERROR)

    def do_POST(self):
        if not self._validar_origem():
            return
        try:
            self._validar_csrf_se_presente()
            if self.path == "/api/generate":
                self._gerar()
                return
            if self.path == "/api/status":
                self._atualizar_status()
                return
            if self.path == "/api/demo":
                self._gerar_demo()
                return
            if self.path == "/api/leads/add":
                self._adicionar_lead()
                return
            if self.path == "/api/settings":
                self._salvar_configuracoes()
                return
            if self.path == "/api/vault/lock":
                self._bloquear_cofre()
                return
            if self.path == "/api/vault/unlock":
                self._desbloquear_cofre()
                return
            if self.path == "/api/vault/rotate":
                self._rotacionar_cofre()
                return
            if self.path == "/api/collect":
                self._executar_coleta()
                return
            self._erro("Rota não encontrada.", HTTPStatus.NOT_FOUND)
        except ValueError as exc:
            self._erro(str(exc))
        except RuntimeError as exc:
            self._erro(str(exc), HTTPStatus.BAD_GATEWAY)
        except Exception as exc:
            print(f"Erro interno em POST: {type(exc).__name__}")
            self._erro("Falha interna ao processar a solicitação.", HTTPStatus.INTERNAL_SERVER_ERROR)

    def _listar_leads(self, query):
        df = carregar_base()
        prioridades = query.get("prioridade", ["Alta"])
        tipos = query.get("tipo", ["Sem Site"])
        cidades = query.get("cidade", [])
        busca = query.get("busca", [""])[0]
        ordenar = query.get("ordenar", ["score"])[0]
        status_crm = query.get("status_crm", [""])[0]
        incluir = query.get("incluir_abordados", ["false"])[0] == "true"

        fila = filtrar_elegiveis(df, prioridades, tipos, cidades, busca=busca, ordenar=ordenar)
        if status_crm and status_crm.lower() not in {"todos", "todas"}:
            fila = fila[fila["Status abordagem"] == status_crm]
        elif not incluir:
            fila = fila[
                fila["Status abordagem"].isin(["Não abordado", "Rascunho"])
            ]

        crm = HISTORICO.resumo()
        cidades_disp = sorted(df["Cidade"].dropna().astype(str).unique().tolist())
        segmentos_disp = sorted(df["Segmento"].dropna().astype(str).unique().tolist())

        resumo = {
            "total": len(df),
            "celulares": int(df["WhatsApp elegível"].sum()),
            "fila": len(fila),
            "contatos_hoje": HISTORICO.contatos_hoje(),
            "limite_diario": int(VAULT.obter("DAILY_CONTACT_LIMIT", "10")),
            "arquivo": LEADS_FILE.name,
            "propostas_abertas": crm["propostas_abertas"],
            "fechados": crm["fechados"],
            "receita_fechada": crm["receita_fechada"],
            "pipeline_aberto": crm.get("pipeline_aberto", 0),
            "por_status": crm.get("por_status", {}),
            "followups": len(HISTORICO.followups_pendentes()),
            "cidades": cidades_disp,
            "segmentos": segmentos_disp,
            "defaults": {
                "provider": VAULT.obter("DEFAULT_AI_PROVIDER", "Modelo local"),
                "tone": VAULT.obter("DEFAULT_TONE", "Consultivo"),
                "service": VAULT.obter("DEFAULT_SERVICE", "Landing Page Express — R$ 149"),
            },
        }
        dados_crm = HISTORICO.dados_por_lead()
        itens = serializar_linhas(fila)
        for item in itens:
            item["CRM"] = dados_crm.get(item["Chave"], {})
            item["Score detalhes"] = explicar_score(item)
        self._json({"summary": resumo, "items": itens})

    def _encontrar(self, key: str) -> dict:
        df = carregar_base()
        encontrado = df[df["Chave"] == key]
        if encontrado.empty:
            raise ValueError("Lead não encontrado na planilha.")
        return encontrado.iloc[0].to_dict()

    def _gerar(self):
        body = self._body()
        key = str(body.get("lead_key", ""))
        provider = str(body.get("provider", VAULT.obter("DEFAULT_AI_PROVIDER", "Modelo local")))
        tom = str(body.get("tom", VAULT.obter("DEFAULT_TONE", "Consultivo")))
        servico = str(body.get("servico", VAULT.obter("DEFAULT_SERVICE", "Landing Page Express — R$ 149")))
        observacao = str(body.get("observacao", ""))[:500]
        etapa = str(body.get("etapa", "Primeiro contato"))
        lead = self._encontrar(key)
        gerada = gerar_mensagem(lead, provider, tom, servico, observacao, etapa=etapa)
        status_atual = HISTORICO.status_por_lead().get(key, "Rascunho")
        novo_status = status_atual if status_atual != "Não abordado" else "Rascunho"
        HISTORICO.salvar(
            key,
            lead["Empresa"],
            lead["Telefone E164"],
            novo_status,
            gerada.contexto,
            gerada.mensagem,
            gerada.provider,
            gerada.model,
            servico=servico,
        )
        self._json(
            {
                "contexto": gerada.contexto,
                "mensagem": gerada.mensagem,
                "provider": gerada.provider,
                "model": gerada.model,
                "etapa": etapa,
            }
        )

    def _atualizar_status(self):
        body = self._body()
        key = str(body.get("lead_key", ""))
        novo_status = str(body.get("status", ""))
        if novo_status not in ALLOWED_STATUS:
            raise ValueError("Status inválido.")
        if novo_status == "Contatado":
            limite = int(VAULT.obter("DAILY_CONTACT_LIMIT", "10"))
            status_anterior = HISTORICO.status_por_lead().get(key)
            if status_anterior != "Contatado" and HISTORICO.contatos_hoje() >= limite:
                raise ValueError("Limite diário de contatos atingido.")
        valor = float(body.get("valor_proposta", 0) or 0)
        if valor < 0:
            raise ValueError("O valor da proposta não pode ser negativo.")
        proxima_acao = str(body.get("proxima_acao", ""))[:10]
        if proxima_acao:
            try:
                pd.Timestamp(proxima_acao)
            except ValueError as exc:
                raise ValueError("Data da próxima ação inválida.") from exc
        lead = self._encontrar(key)
        HISTORICO.salvar(
            key,
            lead["Empresa"],
            lead["Telefone E164"],
            novo_status,
            str(body.get("contexto", "")),
            str(body.get("mensagem", "")),
            str(body.get("provider", "")),
            str(body.get("model", "")),
            servico=str(body.get("servico", ""))[:120],
            valor_proposta=valor,
            proxima_acao=proxima_acao,
            notas=str(body.get("notas", ""))[:1500],
        )
        self._json(
            {
                "ok": True,
                "status": novo_status,
                "dashboard": HISTORICO.resumo(),
            }
        )

    def _gerar_demo(self):
        body = self._body()
        popular_crm = bool(body.get("popular_crm", True))
        resultado = gerar_ambiente_demo(
            LEADS_FILE, historico=HISTORICO, popular_crm=popular_crm
        )
        self._json(resultado)

    def _adicionar_lead(self):
        body = self._body()
        novo = adicionar_lead_manual(
            LEADS_FILE,
            empresa=str(body.get("empresa", "")),
            segmento=str(body.get("segmento", "Negócio Local")),
            cidade=str(body.get("cidade", "Santo André")),
            telefone=str(body.get("telefone", "")),
            avaliacoes=int(body.get("avaliacoes", 50) or 0),
            website=str(body.get("website", "")),
            google_maps=str(body.get("google_maps", "")),
        )
        self._json({"ok": True, "lead": novo})

    def _salvar_configuracoes(self):
        body = self._body()
        nova_senha = body.get("nova_senha_mestra")
        senha_atual = body.get("senha_atual")
        estado = VAULT.salvar_configuracoes(
            body,
            nova_senha_mestra=str(nova_senha) if nova_senha is not None else None,
            senha_atual=str(senha_atual) if senha_atual is not None else None,
        )
        self._json({"ok": True, "settings": estado})

    def _bloquear_cofre(self):
        _ = self._body()
        VAULT.bloquear()
        self._json({"ok": True, "settings": VAULT.estado_publico()})

    def _desbloquear_cofre(self):
        body = self._body()
        senha = str(body.get("senha_mestra", ""))
        VAULT.desbloquear(senha)
        self._json({"ok": True, "settings": VAULT.estado_publico()})

    def _rotacionar_cofre(self):
        body = self._body()
        senha = str(body.get("senha_mestra", ""))
        estado = VAULT.rotacionar_chaves(senha)
        self._json({"ok": True, "settings": estado})

    def _executar_coleta(self):
        _ = self._body()
        if VAULT.esta_bloqueado():
            raise ValueError("Desbloqueie o cofre criptográfico antes de iniciar a coleta.")
        api_key = VAULT.obter("GOOGLE_PLACES_API_KEY", "").strip()
        if not api_key:
            raise ValueError("Configure a GOOGLE_PLACES_API_KEY na aba de Configurações antes da coleta.")
        if VAULT.obter("GOOGLE_PLACES_ENABLED", "0").strip() != "1":
            raise ValueError("Habilite a opção 'Ativar Coleta Google Places' nas Configurações antes de coletar.")
        max_req = int(VAULT.obter("MAX_PLACES_REQUESTS", "60") or 60)
        df = coletar_leads(api_key, max_requisicoes=max_req, intervalo=0.75)
        destino = exportar_excel(df, LEADS_FILE)
        self._json({"ok": True, "coletados": len(df), "arquivo": destino.name})


def _instancia_ja_ativa(host: str, port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://{host}:{port}/api/health", timeout=1.2) as r:
            dados = json.loads(r.read().decode("utf-8"))
            return bool(dados.get("ok"))
    except Exception:
        return False


def _porta_disponivel(host: str, port_inicial: int) -> int:
    for p in range(port_inicial, port_inicial + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex((host, p)) != 0:
                return p
    return port_inicial


def main():
    host = "127.0.0.1"
    port = int(os.getenv("APP_PORT", "8765"))
    if not STATIC_FILE.exists():
        raise SystemExit(f"Interface não encontrada: {STATIC_FILE}")

    if not LEADS_FILE.exists():
        gerar_ambiente_demo(LEADS_FILE, historico=HISTORICO, popular_crm=True)

    if _instancia_ja_ativa(host, port):
        url = f"http://{host}:{port}"
        print(f"✔ CRM JPX Lab já está ativo em {url}")
        if os.getenv("OPEN_BROWSER", "1") == "1":
            webbrowser.open(url)
        return

    port = _porta_disponivel(host, port)
    servidor = ThreadingHTTPServer((host, port), Handler)
    url = f"http://{host}:{port}"
    print(f"🚀 CRM JPX Lab disponível em {url}")
    print("🔒 Cofre Criptográfico AEAD ativo • Envio sempre manual.")
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
