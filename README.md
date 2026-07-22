# Automation Leads — prospecção assistida

Fluxo local e controlado para encontrar negócios no ABC Paulista, selecionar
leads qualificados, criar uma abordagem personalizada com IA e abrir a conversa
no WhatsApp pessoal. **O sistema não envia mensagens automaticamente.**

## Segurança primeiro

A chave que estava escrita no `index.py` original deve ser revogada no Google
Cloud e substituída por uma nova. Nunca publique `.env`, planilhas de leads ou o
banco `data/prospeccao.db`; esses arquivos já estão cobertos pelo `.gitignore`.

## Instalação

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Preencha no `.env` somente as chaves que for usar. Para começar sem custo de IA,
deixe `OPENAI_API_KEY` e `GEMINI_API_KEY` vazias e escolha **Modelo local**.

## Coletar leads

```bash
python index.py
```

Essa etapa chama a API Google Places e exige `GOOGLE_PLACES_API_KEY` válida.

## Abrir o painel

Coloque `Leads_ABC_Paulista.xlsx` na pasta do projeto ou envie a planilha pela
barra lateral do painel:

```bash
python app.py
```

O navegador abrirá `http://127.0.0.1:8765`. A interface usa apenas bibliotecas
Python já listadas no projeto; não depende de Node.js, Streamlit ou extensões.

O painel:

- aceita a estrutura real da aba `Leads`;
- exclui fixos e telefones inválidos da fila de WhatsApp;
- prioriza `Alta` + `Sem Site` por padrão;
- gera rascunho local, via OpenAI ou via Gemini;
- permite revisar e editar todo texto;
- abre `wa.me` com a mensagem preenchida, sem clicar em enviar;
- registra rascunhos, contatos, ignorados e bloqueados em SQLite;
- limita a quantidade diária de contatos.

## Uso responsável

Faça abordagens individuais e relevantes. Não importe listas compradas, não use
disparo em massa, respeite pedidos de não contato e não tente automatizar o envio
por bibliotecas que controlam o WhatsApp Web.
