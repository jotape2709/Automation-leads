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
    criado_em TEXT NOT NULL,
    atualizado_em TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_contatos_lead_key ON contatos(lead_key);
CREATE INDEX IF NOT EXISTS idx_contatos_criado_em ON contatos(criado_em);
"""


class Historico:
    def __init__(self, caminho: str | Path = "data/prospeccao.db") -> None:
        self.caminho = Path(caminho)
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        with self._conectar() as conexao:
            conexao.executescript(SCHEMA)

    def _conectar(self) -> sqlite3.Connection:
        return sqlite3.connect(self.caminho)

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
    ) -> None:
        agora = datetime.now().isoformat(timespec="seconds")
        with self._conectar() as conexao:
            existente = conexao.execute(
                "SELECT id FROM contatos WHERE lead_key = ? ORDER BY id DESC LIMIT 1",
                (lead_key,),
            ).fetchone()
            if existente:
                conexao.execute(
                    """UPDATE contatos SET status=?, contexto=?, mensagem=?, provider=?,
                    model=?, atualizado_em=? WHERE id=?""",
                    (status, contexto, mensagem, provider, model, agora, existente[0]),
                )
            else:
                conexao.execute(
                    """INSERT INTO contatos
                    (lead_key, empresa, telefone, status, contexto, mensagem, provider,
                    model, criado_em, atualizado_em) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (lead_key, empresa, telefone, status, contexto, mensagem, provider, model, agora, agora),
                )

    def status_por_lead(self) -> dict[str, str]:
        with self._conectar() as conexao:
            linhas = conexao.execute(
                """SELECT c.lead_key, c.status FROM contatos c
                JOIN (SELECT lead_key, MAX(id) id FROM contatos GROUP BY lead_key) u
                ON c.id = u.id"""
            ).fetchall()
        return dict(linhas)

    def contatos_hoje(self) -> int:
        inicio = date.today().isoformat()
        with self._conectar() as conexao:
            return int(conexao.execute(
                "SELECT COUNT(*) FROM contatos WHERE status='Contatado' AND criado_em LIKE ?",
                (f"{inicio}%",),
            ).fetchone()[0])

    def dataframe(self) -> pd.DataFrame:
        with self._conectar() as conexao:
            return pd.read_sql_query("SELECT * FROM contatos ORDER BY atualizado_em DESC", conexao)

