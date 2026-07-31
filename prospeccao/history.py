from __future__ import annotations

import sqlite3
from datetime import date, datetime
from pathlib import Path

import pandas as pd

SCHEMA = """
CREATE TABLE IF NOT EXISTS contatos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_key TEXT NOT NULL,
    empresa TEXT NOT NULL,
    telefone TEXT NOT NULL,
    status TEXT NOT NULL,
    contexto TEXT,
    mensagem TEXT,
    provider TEXT,
    model TEXT,
    servico TEXT DEFAULT '',
    valor_proposta REAL DEFAULT 0,
    proxima_acao TEXT DEFAULT '',
    notas TEXT DEFAULT '',
    criado_em TEXT NOT NULL,
    atualizado_em TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_contatos_lead_key ON contatos(lead_key);
CREATE INDEX IF NOT EXISTS idx_contatos_status ON contatos(status);
CREATE INDEX IF NOT EXISTS idx_contatos_proxima_acao ON contatos(proxima_acao);

CREATE TABLE IF NOT EXISTS eventos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_key TEXT NOT NULL,
    status TEXT NOT NULL,
    criado_em TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_eventos_lead_key ON eventos(lead_key);
CREATE INDEX IF NOT EXISTS idx_eventos_criado_em ON eventos(criado_em);
"""

MIGRATIONS = {
    "servico": "TEXT DEFAULT ''",
    "valor_proposta": "REAL DEFAULT 0",
    "proxima_acao": "TEXT DEFAULT ''",
    "notas": "TEXT DEFAULT ''",
}

FUNIL_ATIVO = {
    "Rascunho",
    "Contatado",
    "Respondeu",
    "Proposta",
    "Negociação",
    "Fechado",
    "Perdido",
}


class Historico:
    def __init__(self, caminho: str | Path = "data/prospeccao.db") -> None:
        self.caminho = Path(caminho)
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        with self._conectar() as conexao:
            conexao.executescript(SCHEMA)
            self._migrar(conexao)

    def _conectar(self) -> sqlite3.Connection:
        conexao = sqlite3.connect(self.caminho)
        conexao.row_factory = sqlite3.Row
        return conexao

    @staticmethod
    def _migrar(conexao: sqlite3.Connection) -> None:
        colunas = {
            linha["name"]
            for linha in conexao.execute("PRAGMA table_info(contatos)").fetchall()
        }
        for coluna, definicao in MIGRATIONS.items():
            if coluna not in colunas:
                conexao.execute(
                    f"ALTER TABLE contatos ADD COLUMN {coluna} {definicao}"
                )

    def salvar(
        self,
        lead_key: str,
        empresa: str,
        telefone: str,
        status: str,
        contexto: str = "",
        mensagem: str = "",
        provider: str = "",
        model: str = "",
        servico: str = "",
        valor_proposta: float = 0,
        proxima_acao: str = "",
        notas: str = "",
    ) -> None:
        agora = datetime.now().isoformat(timespec="seconds")
        valor = max(float(valor_proposta or 0), 0)
        with self._conectar() as conexao:
            existente = conexao.execute(
                "SELECT id, status FROM contatos WHERE lead_key = ? ORDER BY id DESC LIMIT 1",
                (lead_key,),
            ).fetchone()
            if existente:
                conexao.execute(
                    """UPDATE contatos SET status=?, contexto=?, mensagem=?, provider=?,
                    model=?, servico=?, valor_proposta=?, proxima_acao=?, notas=?,
                    atualizado_em=? WHERE id=?""",
                    (
                        status,
                        contexto,
                        mensagem,
                        provider,
                        model,
                        servico,
                        valor,
                        proxima_acao,
                        notas,
                        agora,
                        existente["id"],
                    ),
                )
                status_mudou = existente["status"] != status
            else:
                conexao.execute(
                    """INSERT INTO contatos
                    (lead_key, empresa, telefone, status, contexto, mensagem, provider,
                    model, servico, valor_proposta, proxima_acao, notas, criado_em,
                    atualizado_em) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        lead_key,
                        empresa,
                        telefone,
                        status,
                        contexto,
                        mensagem,
                        provider,
                        model,
                        servico,
                        valor,
                        proxima_acao,
                        notas,
                        agora,
                        agora,
                    ),
                )
                status_mudou = True
            if status_mudou:
                conexao.execute(
                    "INSERT INTO eventos (lead_key, status, criado_em) VALUES (?, ?, ?)",
                    (lead_key, status, agora),
                )

    def status_por_lead(self) -> dict[str, str]:
        with self._conectar() as conexao:
            linhas = conexao.execute(
                """SELECT c.lead_key, c.status FROM contatos c
                JOIN (SELECT lead_key, MAX(id) id FROM contatos GROUP BY lead_key) u
                ON c.id = u.id"""
            ).fetchall()
        return {linha["lead_key"]: linha["status"] for linha in linhas}

    def dados_por_lead(self) -> dict[str, dict]:
        with self._conectar() as conexao:
            linhas = conexao.execute(
                """SELECT c.* FROM contatos c
                JOIN (SELECT lead_key, MAX(id) id FROM contatos GROUP BY lead_key) u
                ON c.id = u.id"""
            ).fetchall()
        return {linha["lead_key"]: dict(linha) for linha in linhas}

    def contatos_hoje(self) -> int:
        inicio = date.today().isoformat()
        with self._conectar() as conexao:
            return int(
                conexao.execute(
                    "SELECT COUNT(*) FROM eventos WHERE status='Contatado' AND criado_em LIKE ?",
                    (f"{inicio}%",),
                ).fetchone()[0]
            )

    def resumo(self) -> dict:
        with self._conectar() as conexao:
            status = {
                linha["status"]: int(linha["total"])
                for linha in conexao.execute(
                    "SELECT status, COUNT(*) total FROM contatos GROUP BY status"
                ).fetchall()
            }
            receita = float(
                conexao.execute(
                    "SELECT COALESCE(SUM(valor_proposta), 0) FROM contatos WHERE status='Fechado'"
                ).fetchone()[0]
            )
            propostas = int(status.get("Proposta", 0) + status.get("Negociação", 0))
            fechados = int(status.get("Fechado", 0))
            oportunidades = sum(
                total for nome, total in status.items() if nome in FUNIL_ATIVO
            )
        return {
            "por_status": status,
            "propostas_abertas": propostas,
            "fechados": fechados,
            "oportunidades": oportunidades,
            "receita_fechada": receita,
        }

    def followups_pendentes(self) -> list[dict]:
        hoje = date.today().isoformat()
        with self._conectar() as conexao:
            linhas = conexao.execute(
                """SELECT * FROM contatos
                WHERE proxima_acao != ''
                AND proxima_acao <= ?
                AND status NOT IN ('Fechado', 'Perdido', 'Ignorado', 'Bloqueado')
                ORDER BY proxima_acao, atualizado_em""",
                (hoje,),
            ).fetchall()
        return [dict(linha) for linha in linhas]

    def dataframe(self) -> pd.DataFrame:
        with self._conectar() as conexao:
            return pd.read_sql_query(
                "SELECT * FROM contatos ORDER BY atualizado_em DESC", conexao
            )
