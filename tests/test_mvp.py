import json
import os
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["LEADS_FILE"] = str(ROOT / "Leads_ABC_Paulista.xlsx")
_tmp = tempfile.TemporaryDirectory()
os.environ["HISTORY_DB"] = str(Path(_tmp.name) / "test.db")
os.environ["OPEN_BROWSER"] = "0"

import app  # noqa: E402


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
            return json.loads(response.read())

    def post(self, path, payload):
        req = Request(
            self.base + path,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(req, timeout=10) as response:
            return json.loads(response.read())

    def test_fila_real_e_rascunho_local(self):
        data = self.get("/api/leads?prioridade=Alta&tipo=" + quote("Sem Site"))
        self.assertEqual(data["summary"]["total"], 450)
        self.assertEqual(data["summary"]["celulares"], 309)
        self.assertEqual(data["summary"]["fila"], 54)
        lead = data["items"][0]
        draft = self.post("/api/generate", {
            "lead_key": lead["Chave"], "provider": "Modelo local"
        })
        self.assertIn(lead["Empresa"], draft["mensagem"])
        self.assertEqual(draft["provider"], "modelo local")
        updated = self.post("/api/status", {
            "lead_key": lead["Chave"], "status": "Ignorado",
            "contexto": draft["contexto"], "mensagem": draft["mensagem"],
        })
        self.assertTrue(updated["ok"])


if __name__ == "__main__":
    unittest.main()
