import json
import os
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
_tmp = tempfile.TemporaryDirectory()
_leads = Path(_tmp.name) / "leads.xlsx"
_db = Path(_tmp.name) / "test.db"
_vault = Path(_tmp.name) / "test_vault.enc"
_vault_key = Path(_tmp.name) / ".test_vault.key"

pd.DataFrame([
    {
        "Segmento": "Barbearia", "Empresa": "Barbearia Central",
        "Cidade": "Diadema", "Telefone": "(11) 99999-9999",
        "Avaliações": 100, "Tipo Site": "Sem Site", "Website": "",
        "Google Maps": "https://www.google.com/maps/place/teste",
        "Score": 80, "Prioridade": "Alta",
    },
    {
        "Segmento": "Pet Shop", "Empresa": "Pet ABC",
        "Cidade": "Santo André", "Telefone": "(11) 98888-8888",
        "Avaliações": 90, "Tipo Site": "Rede Social",
        "Website": "https://instagram.com/petabc",
        "Google Maps": "https://www.google.com/maps/place/pet",
        "Score": 70, "Prioridade": "Alta",
    },
]).to_excel(_leads, sheet_name="Leads", index=False, engine="openpyxl")

os.environ["LEADS_FILE"] = str(_leads)
os.environ["HISTORY_DB"] = str(_db)
os.environ["VAULT_FILE"] = str(_vault)
os.environ["VAULT_KEY_FILE"] = str(_vault_key)
os.environ["OPEN_BROWSER"] = "0"

import app


class TestMVP(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        _tmp.cleanup()

    def get(self, path):
        with urlopen(self.base + path, timeout=10) as response:
            return json.loads(response.read()), response.headers

    def post(self, path, payload, content_type="application/json"):
        req = Request(
            self.base + path,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": content_type},
            method="POST",
        )
        with urlopen(req, timeout=10) as response:
            return json.loads(response.read())

    def test_fila_e_rascunho_local(self):
        data, headers = self.get("/api/leads?prioridade=Alta&tipo=Sem%20Site")
        self.assertEqual(data["summary"]["total"], 2)
        self.assertEqual(data["summary"]["celulares"], 2)
        self.assertEqual(data["summary"]["fila"], 1)
        self.assertEqual(headers["X-Frame-Options"], "DENY")
        lead = data["items"][0]
        self.assertEqual(len(lead["Score detalhes"]), 3)
        draft = self.post("/api/generate", {
            "lead_key": lead["Chave"], "provider": "Modelo local",
            "tom": "Direto", "servico": "Landing Page Express — R$ 149",
            "observacao": "O atendimento principal acontece pelo WhatsApp",
            "etapa": "Primeiro contato",
        })
        self.assertIn(lead["Empresa"], draft["mensagem"])
        self.assertEqual(draft["provider"], "modelo local")
        updated = self.post("/api/status", {
            "lead_key": lead["Chave"], "status": "Ignorado",
            "contexto": draft["contexto"], "mensagem": draft["mensagem"],
        })
        self.assertTrue(updated["ok"])
        from urllib.parse import quote
        eventos, _ = self.get(f"/api/lead-events?lead_key={quote(lead['Chave'])}")
        self.assertGreaterEqual(len(eventos["items"]), 1)

    def test_cofre_api_settings_e_rotacao(self):
        info, _ = self.get("/api/settings")
        self.assertIn("credenciais", info)
        self.assertIn("csrf_token", info)
        chave_ficticia = "sk-" + ("abcdef12" * 3)
        salvo = self.post("/api/settings", {
            "OPENAI_API_KEY": chave_ficticia,
            "DEFAULT_AI_PROVIDER": "OpenAI",
            "DEFAULT_TONE": "Direto",
            "DAILY_CONTACT_LIMIT": "12",
        })
        self.assertTrue(salvo["ok"])
        self.assertTrue(salvo["settings"]["credenciais"]["OPENAI_API_KEY"]["configurada"])
        self.assertNotIn(
            "abcdef12abcdef12",
            salvo["settings"]["credenciais"]["OPENAI_API_KEY"]["mascara"],
        )
        rot = self.post("/api/vault/rotate", {})
        self.assertTrue(rot["ok"])

    def test_z_adicionar_lead_manual_e_health(self):
        health, _ = self.get("/api/health")
        self.assertTrue(health["ok"])
        self.assertEqual(health["engine"], "hybrid-rust-python")
        res = self.post("/api/leads/add", {
            "empresa": "Clínica Sorriso Real",
            "segmento": "Odontologia",
            "cidade": "São Caetano do Sul",
            "telefone": "(11) 97777-6666",
            "avaliacoes": 110,
            "website": "",
        })
        self.assertTrue(res["ok"])
        self.assertEqual(res["lead"]["Score"], 80)

    def test_rejeita_content_type_incorreto(self):
        with self.assertRaises(HTTPError) as erro:
            self.post("/api/status", {"status": "Ignorado"}, "text/plain")
        self.assertEqual(erro.exception.code, 400)


if __name__ == "__main__":
    unittest.main()
