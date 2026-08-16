# Automation Leads

Pipeline local de coleta, qualificação e prospecção assistida desenvolvido por
**João Pedro de Moura Lima** para transformar dados públicos de negócios locais
em uma fila comercial priorizada e controlada.

O projeto combina Google Places API, tratamento de dados, scoring, Excel, CRM em
SQLite e geração assistida de mensagens com modelo local, OpenAI ou Gemini. O
sistema não realiza disparos: toda abordagem precisa ser revisada e enviada
manualmente pelo operador.

## Resultado entregue

- coleta negócios locais pela API oficial Google Places;
- normaliza e deduplica registros por empresa e cidade;
- classifica presença digital e calcula um score de oportunidade;
- valida celulares brasileiros antes de liberar WhatsApp;
- organiza prioridades em uma planilha Excel filtrável;
- mantém funil, histórico, propostas e follow-ups em SQLite;
- gera rascunhos contextualizados sem afirmar fatos não verificados;
- limita contatos diários e exige revisão humana;
- funciona localmente, sem expor o painel na rede.

## Arquitetura

```text
Google Places API
       |
       v
Coleta e validação -> scoring -> planilha local
                                      |
                                      v
                               painel CRM local
                              /       |        \
                         SQLite   modelo local   APIs de IA
                              \       |        /
                               revisão humana
                                      |
                                      v
                              WhatsApp preenchido
```

## Segurança

Nenhuma credencial fica no código. Chaves são carregadas por variáveis de
ambiente e o arquivo `.env` é ignorado. Bases de leads, bancos SQLite, logs e
formatos comuns de credenciais também são bloqueados pelo `.gitignore`.

O painel:

- aceita conexões somente de loopback;
- valida `Host`, `Origin`, tipo e tamanho das requisições;
- aplica CSP e cabeçalhos contra clickjacking e MIME sniffing;
- evita HTML dinâmico com dados de leads;
- valida links externos antes de abri-los;
- limita tamanho, expansão e quantidade de linhas dos workbooks;
- neutraliza fórmulas em exportações Excel;
- reduz dados enviados aos provedores de IA;
- redige possíveis segredos de mensagens de erro.

As orientações completas para proteger a chave do Google estão em
[SECURITY.md](SECURITY.md).

## Instalação

```bash
git clone https://github.com/jotape2709/Automation-leads.git
cd Automation-leads
python -m venv .venv
```

Linux e macOS:

```bash
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Windows:

```powershell
.venv\Scripts\activate
pip install -r requirements.txt
Copy-Item .env.example .env
```

## Configuração

Preencha somente as credenciais que pretende utilizar:

```env
GOOGLE_PLACES_API_KEY=
GOOGLE_PLACES_ENABLED=0
MAX_PLACES_REQUESTS=60

OPENAI_API_KEY=
GEMINI_API_KEY=
```

Antes de alterar `GOOGLE_PLACES_ENABLED` para `1`, restrinja a chave à
**Places API (New)** e configure quotas no Google Cloud.

## Execução

Coletar e exportar leads:

```bash
python index.py
```

Abrir o CRM:

```bash
python app.py
```

O painel fica disponível em `http://127.0.0.1:8765`.

## Testes e verificação

```bash
python -m unittest discover -s tests -v
python scripts/security_scan.py
```

O workflow do GitHub executa testes em múltiplas versões do Python, busca
segredos e arquivos sensíveis e audita dependências conhecidas.

## Estrutura

```text
app.py                     servidor local e API do CRM
index.py                   coleta, scoring e exportação
prospeccao/ai.py           geração assistida de mensagens
prospeccao/history.py      persistência e métricas do funil
prospeccao/leads.py        validação de planilhas e telefones
prospeccao/http.py         cliente HTTP com respostas limitadas
static/index.html          interface local
scripts/security_scan.py   verificação pré-publicação
tests/                     testes funcionais e de segurança
```

## Uso responsável

O projeto foi desenhado para prospecção individual e relevante. Não importe
listas compradas, não faça disparos em massa, respeite pedidos de não contato e
revise toda mensagem antes do envio.

## Autor

Desenvolvido por **João Pedro de Moura Lima**.

## Licença

MIT.
