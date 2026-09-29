# Ideias futuras

Ideias já discutidas e deixadas para depois, com o contexto necessário para retomar.

## Análise de Estoque: continuar a análise da IA

*Registrado em 29/09/2026.*

**Contexto.** A análise da IA é um pedido único: o texto vai para a aba "Análise da IA" e para o PDF exportado, e não há como responder. A IA costumava terminar oferecendo mais ajuda ("Se quiser, eu elaboro uma lista priorizada de ações...").

A primeira medida, feita em 29/09/2026, foi ajustar as instruções enviadas à IA. A resposta passou a ser um relatório fechado: sem perguntas nem ofertas, terminando na seção "Ações recomendadas" e em texto simples. As duas opções abaixo vão além, se um dia for preciso aprofundar a análise.

### Opção 2: botões de aprofundamento

- **O que é:** botões embaixo da análise, por exemplo "📋 Plano de ação detalhado", "🔎 Explicar um produto" e "📝 Resumo curto para a gerência".
- **Como funciona:** cada botão faz um novo pedido à IA com os mesmos dados já enviados e a análise anterior. A resposta entra como uma seção nova na aba e no PDF.
- **Por que:** dá a sensação de continuar sem virar uma conversa, e o custo de cada clique é previsível.
- **A decidir:** quais botões entram, e se "Explicar um produto" pede para escolher o produto na grade.
- **Onde mexer:** em `views/stock_analysis_page.py`:
  - `_on_analisar_ia_clicked`: instruções e envio à IA;
  - `_on_ia_finished`: hoje substitui o texto e passaria a acrescentar seções;
  - `_secao_analise_ia`: seção da IA no PDF.
- **Antes de implementar:** gerar 3 artefatos do layout dos botões para aprovação.

### Opção 3: campo de pergunta livre (conversa)

- **O que é:** um campo "Pergunte sobre esta análise" embaixo do texto, com as respostas em sequência.
- **Custos:**
  - cada pergunta reenvia o histórico inteiro (dados, análise e perguntas anteriores), então o gasto cresce a cada rodada;
  - `AIClient.analisar(system, prompt)` (`services/ai_client.py`) só faz pedidos únicos: precisaria aceitar o histórico, com adaptação para os três provedores (OpenAI, Anthropic e Google);
  - o PDF deixaria de ser um relatório e viraria uma conversa, e seria preciso decidir o que exportar.
- **Quando vale:** só se as perguntas fora do roteiro forem frequentes. Caso contrário, a opção 2 resolve com menos custo.
