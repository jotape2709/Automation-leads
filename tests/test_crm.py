from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

from prospeccao.ai import ANGULOS, mensagem_fallback
from prospeccao.history import Historico


class HistoricoCRMTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "crm.db"
        self.historico = Historico(self.db)

    def tearDown(self):
        self.tmp.cleanup()

    def test_salva_pipeline_valor_e_followup(self):
        self.historico.salvar(
            "empresa|5511999999999",
            "Empresa Teste",
            "5511999999999",
            "Proposta",
            servico="Landing Page Express — R$ 149",
            valor_proposta=149,
            proxima_acao=date.today().isoformat(),
            notas="Aguardando retorno.",
        )
        dados = self.historico.dados_por_lead()["empresa|5511999999999"]
        self.assertEqual(dados["status"], "Proposta")
        self.assertEqual(dados["valor_proposta"], 149)
        self.assertEqual(len(self.historico.followups_pendentes()), 1)

    def test_resumo_considera_fechados(self):
        self.historico.salvar(
            "a|1", "A", "1", "Fechado", valor_proposta=89
        )
        self.historico.salvar(
            "b|2", "B", "2", "Negociação", valor_proposta=149
        )
        resumo = self.historico.resumo()
        self.assertEqual(resumo["fechados"], 1)
        self.assertEqual(resumo["propostas_abertas"], 1)
        self.assertEqual(resumo["receita_fechada"], 89)

    def test_evento_contatado_e_registrado_uma_vez(self):
        self.historico.salvar("a|1", "A", "1", "Rascunho")
        self.historico.salvar("a|1", "A", "1", "Contatado")
        self.historico.salvar("a|1", "A", "1", "Contatado", notas="nota")
        self.assertEqual(self.historico.contatos_hoje(), 1)


class MensagemTest(unittest.TestCase):
    def test_catalogo_completo_possui_14_ofertas(self):
        self.assertEqual(len(ANGULOS), 14)

    def test_fallback_nao_expoe_preco(self):
        lead = {
            "Empresa": "Negócio Local",
            "Segmento": "Barbearia",
            "Cidade": "Diadema",
            "Tipo Site": "Sem Site",
            "Avaliações": 15,
        }
        resultado = mensagem_fallback(
            lead, servico="Google Profissional — R$ 69"
        )
        self.assertNotIn("R$ 69", resultado.mensagem)
        self.assertTrue(resultado.mensagem.endswith("?"))


if __name__ == "__main__":
    unittest.main()
