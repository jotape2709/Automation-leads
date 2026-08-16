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
        draft = self.post("/api/generate", {
            "lead_key": lead["Chave"], "provider": "Modelo local",
            "tom": "Direto", "servico": "Landing Page Express — R$ 149",
            "observacao": "O atendimento principal acontece pelo WhatsApp",
        })
        self.assertIn(lead["Empresa"], draft["mensagem"])
        self.assertEqual(draft["provider"], "modelo local")
        updated = self.post("/api/status", {
            "lead_key": lead["Chave"], "status": "Ignorado",
            "contexto": draft["contexto"], "mensagem": draft["mensagem"],
        })
        self.assertTrue(updated["ok"])

    def test_rejeita_content_type_incorreto(self):
        with self.assertRaises(HTTPError) as erro:
            self.post("/api/status", {"status": "Ignorado"}, "text/plain")
        self.assertEqual(erro.exception.code, 400)


if __name__ == "__main__":
    unittest.main()
