# JPX Lab CRM v2

## O que mudou

- Interface redesenhada na identidade preto, branco e cinza da JPX Lab.
- Catálogo com 14 ofertas de aquisição.
- Funil com `Rascunho`, `Contatado`, `Respondeu`, `Proposta`, `Negociação`,
  `Fechado`, `Perdido`, `Ignorado` e `Bloqueado`.
- Registro de valor proposto, próxima ação e notas.
- Follow-ups vencidos e métricas de propostas, fechamentos e receita.
- Histórico de eventos para contar contatos do dia corretamente.
- Migração automática do banco SQLite existente, sem apagar dados.
- Prompt e modelo local atualizados para cada oferta.

## Validação

```bash
python -m unittest discover -s tests -v
```

O painel continua sem envio automático. O usuário revisa o texto e abre a
conversa manualmente no WhatsApp.
