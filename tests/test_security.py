from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook

from index import exportar_excel
from prospeccao.leads import carregar_leads
from prospeccao.vault import (
    CofreCredenciais,
    LimitadorTaxa,
    criptografar_bytes,
    descriptografar_bytes,
    mascarar_segredo,
    validar_formato_credencial,
)
from scripts.security_scan import analisar


COLUNAS = {
    "Segmento": ["Barbearia"],
    "Empresa": ["Empresa Teste"],
    "Cidade": ["Diadema"],
    "Telefone": ["(11) 99999-9999"],
    "Avaliações": [100],
    "Tipo Site": ["Sem Site"],
    "Website": [""],
    "Google Maps": ["https://www.google.com/maps/place/teste"],
    "Score": [80],
    "Prioridade": ["Alta"],
}


class SecurityTest(unittest.TestCase):
    def test_planilha_valida_e_limitada(self):
        with tempfile.TemporaryDirectory() as pasta:
            arquivo = Path(pasta) / "leads.xlsx"
            with pd.ExcelWriter(arquivo, engine="openpyxl") as writer:
                pd.DataFrame(COLUNAS).to_excel(
                    writer, sheet_name="Leads", index=False
                )
            dados = carregar_leads(arquivo)
            self.assertEqual(len(dados), 1)
            self.assertEqual(dados.iloc[0]["Telefone E164"], "5511999999999")

    def test_exportacao_neutraliza_formula(self):
        with tempfile.TemporaryDirectory() as pasta:
            arquivo = Path(pasta) / "saida.xlsx"
            dados = pd.DataFrame({"Empresa": ["=1+1"], "Telefone": ["+5511999"]})
            exportar_excel(dados, arquivo)
            planilha = load_workbook(arquivo, data_only=False)
            self.assertEqual(planilha["Leads"]["A2"].value, "'=1+1")
            self.assertEqual(planilha["Leads"]["B2"].value, "'+5511999")

    def test_criptografia_aead_e_integridade_mac(self):
        chave_ficticia = "sk-" + ("demo" * 7)
        segredo = f'{{"OPENAI_API_KEY":"{chave_ficticia}"}}'.encode("utf-8")
        chave = b"x" * 32
        pacote = criptografar_bytes(segredo, chave)
        self.assertEqual(descriptografar_bytes(pacote, chave), segredo)

        # Adulterar bytes no pacote decodificado deve falhar no HMAC em tempo constante
        import base64
        bruto = bytearray(base64.b64decode(pacote))
        self.assertTrue(bytes(bruto).startswith(b"JPXVAULT1"))
        bruto[-1] ^= 0x01
        adulterado = base64.b64encode(bytes(bruto))
        with self.assertRaises(ValueError):
            descriptografar_bytes(adulterado, chave)

    def test_cofre_credenciais_ciclo_completo_e_rotacao(self):
        chave_ficticia = "sk-" + ("testkey" * 4)
        with tempfile.TemporaryDirectory() as pasta:
            base = Path(pasta)
            cofre = CofreCredenciais(caminho_cofre=base / "vault.enc")
            res = cofre.salvar_configuracoes(
                {
                    "OPENAI_API_KEY": chave_ficticia,
                    "DEFAULT_AI_PROVIDER": "OpenAI",
                    "DEFAULT_TONE": "Consultivo",
                    "DAILY_CONTACT_LIMIT": "15",
                },
                nova_senha_mestra="SenhaForte#2026",
            )
            self.assertTrue(res["cofre_existe"])
            self.assertTrue(res["possui_senha_mestra"])
            self.assertIn("••••", res["credenciais"]["OPENAI_API_KEY"]["mascara"])

            # Bloquear na memória exige senha para ler novamente
            cofre.bloquear()
            estado_bloq = cofre.estado_publico()
            self.assertTrue(estado_bloq["bloqueado"])

            with self.assertRaises(ValueError):
                cofre.desbloquear("SenhaErrada")

            self.assertTrue(cofre.desbloquear("SenhaForte#2026"))
            self.assertFalse(cofre.esta_bloqueado())
            self.assertEqual(cofre.obter("OPENAI_API_KEY"), chave_ficticia)

            # Rotação criptográfica
            rot = cofre.rotacionar_chaves("SenhaForte#2026")
            self.assertTrue(rot["cofre_existe"])
            self.assertEqual(cofre.obter("OPENAI_API_KEY"), chave_ficticia)

    def test_mascaramento_e_limitador_taxa(self):
        self.assertEqual(mascarar_segredo(""), "")
        gkey = "AIza" + ("DemoKey123" * 3)
        self.assertIn("••••", mascarar_segredo(gkey))
        validar_formato_credencial("GOOGLE_PLACES_API_KEY", gkey)
        with self.assertRaises(ValueError):
            validar_formato_credencial("OPENAI_API_KEY", "invalida")

        lim = LimitadorTaxa(max_tentativas=2, janela_segundos=60)
        lim.verificar("127.0.0.1")
        lim.verificar("127.0.0.1")
        with self.assertRaises(ValueError):
            lim.verificar("127.0.0.1")

    def test_repositorio_sem_segredos(self):
        raiz = Path(__file__).resolve().parents[1]
        self.assertEqual(analisar(raiz), [])

    def test_interface_nao_usa_html_dinamico_inseguro(self):
        raiz = Path(__file__).resolve().parents[1]
        html = (raiz / "static" / "index.html").read_text(encoding="utf-8")
        self.assertNotIn("innerHTML", html)
        self.assertNotIn("onclick=", html)


if __name__ == "__main__":
    unittest.main()

