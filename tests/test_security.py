from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook

from index import exportar_excel
from prospeccao.leads import carregar_leads
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
