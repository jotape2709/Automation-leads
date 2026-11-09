# JPX Lab CRM — Notas de Evolução (v2.0 → v3.0)

## Novidades da v3.0 (Arquitetura Híbrida Rust + Python & Nova Identidade Visual)

- **Motor Nativo em Rust (`Cargo.toml` + `src/main.rs`)**:
  - CLI e Gateway HTTP loopback em Rust puro (`std`) que supervisiona e consome os módulos Python via IPC JSON (`prospeccao/bridge.py`).
  - Comandos nativos: `cargo run -- serve`, `cargo run -- demo`, `cargo run -- stats`, `cargo run -- generate`, `cargo run -- collect` e `cargo run -- doctor`.
- **Sistema de Design Vermelho, Creme & Amarelo (Temas Escuro & Claro)**:
  - **Tema Escuro (*Rubi Noturno*)**: superfícies obsidiana-rubi com destaques em amarelo geométrico (`#FFD426`), vermelho carmesim (`#C8102E`) e tipografia creme (`#FDF8EE`).
  - **Tema Claro (*Creme Solar*)**: fundo creme editorial (`#FAF3E3` / `#FFFDF8`), tipografia expresso-bordô (`#1E090C`) e acentos em vermelho e amarelo da JPX Lab.
  - Alternância instantânea no topo ou via atalho `Alt + T` com persistência local.
- **Usabilidade e Novas Visões Comerciais**:
  - **3 Modos de Visualização**: `🎯 Estação SDR`, `📋 Pipeline Kanban` e `⏰ Central de Follow-ups & Histórico`.
  - **Busca em tempo real**, ordenação por Score/Avaliações/Nome, filtro dinâmico por cidade e chips rápidos de fila.
  - **Diagnóstico transparente de Score** explicando os pontos atribuídos a cada lead.
  - **Etapas de Cadência na IA**: suporte a `Primeiro contato`, `Follow-up 1`, `Follow-up 2` e `Proposta`.
  - **Gerador de Base Demonstrativa (`POST /api/demo`)** e **Cadastro Manual de Leads (`POST /api/leads/add`)** direto pela interface.

## O que mudou na v2.0

- Catálogo com 14 ofertas de aquisição.
- Funil com `Rascunho`, `Contatado`, `Respondeu`, `Proposta`, `Negociação`, `Fechado`, `Perdido`, `Ignorado` e `Bloqueado`.
- Registro de valor proposto, próxima ação e notas.
- Follow-ups vencidos e métricas de propostas, fechamentos e receita.
- Histórico de eventos para contar contatos do dia corretamente.
- Migração automática do banco SQLite existente, sem apagar dados.

## Validação

```bash
cargo test
cargo run -- doctor
python -m unittest discover -s tests -v
python scripts/security_scan.py
```

O painel continua sem envio automático. O usuário revisa o texto e abre a conversa manualmente no WhatsApp.
