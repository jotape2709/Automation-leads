from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

from prospeccao.ai import ANGULOS, mensagem_fallback
from prospeccao.demo import construir_dataframe_demo
from prospeccao.history import Historico
from prospeccao.leads import explicar_score, filtrar_elegiveis, normalizar_telefone_br


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

    def test_resumo_considera_fechados_e_pipeline_aberto(self):
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
        self.assertEqual(resumo["pipeline_aberto"], 149)

    def test_evento_contatado_e_registrado_uma_vez_e_listado(self):
        self.historico.salvar("a|1", "A", "1", "Rascunho")
        self.historico.salvar("a|1", "A", "1", "Contatado")
        self.historico.salvar("a|1", "A", "1", "Contatado", notas="nota")
        self.assertEqual(self.historico.contatos_hoje(), 1)
        eventos = self.historico.eventos_por_lead("a|1")
        self.assertEqual(len(eventos), 2)
        self.assertEqual(eventos[0]["status"], "Contatado")


class MensagemEQualificacaoTest(unittest.TestCase):
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

    def test_etapas_cadencia_followup(self):
        lead = {
            "Empresa": "Barbearia Imperial",
            "Segmento": "Barbearia",
            "Cidade": "Santo André",
            "Tipo Site": "Sem Site",
            "Avaliações": 120,
        }
        fu1 = mensagem_fallback(lead, etapa="Follow-up 1")
        self.assertIn("retomando meu contato", fu1.mensagem)
        self.assertTrue(fu1.mensagem.endswith("?"))

    def test_demo_e_filtros_avancados(self):
        df = construir_dataframe_demo()
        df["Telefone E164"] = df["Telefone"].map(normalizar_telefone_br)
        df["WhatsApp elegível"] = df["Telefone E164"].map(bool)
        todos = filtrar_elegiveis(df, ["Todas"], ["Todos"], ["Todas"], busca="Santo André")
        self.assertGreaterEqual(len(todos), 3)
        detalhes = explicar_score(df.iloc[0])
        self.assertEqual(len(detalhes), 3)


if __name__ == "__main__":
    unittest.main()
