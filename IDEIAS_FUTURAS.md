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


### A. Base da análise (confiabilidade)

1. **Analisar direto do ZIPs baixados (pode selecionar até 3), e não do PDF avulso.**
   - **Por que:**
     - hoje o PDF é anexado de qualquer pasta e lido por um parser de texto, que já teve dois defeitos corrigidos ("Vencimento do lote" e lote em duas linhas);
     - o PDF é opcional no ZIP, e sem ele não há análise;
     - o PDF anexado não é conferido com o `.sig`, então um PDF editado passaria.
   - **O que o `.db` assinado traz:**
     - a tabela `Produtos`, com `codean`, `codproduto`, `descricaoproduto`, `unidade`, `qtdecontada`, `controlalote`, `numlote`, `datafab`, `dataval`, `codgrupo`, `nomegrupo` e `localizacao`;
     - `Empresa.local`, que permitiria preencher sozinho o local de estoque que hoje o usuário escolhe à mão.
   - **PDF como complemento:** as observações do conferente só estão no PDF.
   - **UX:** escolher numa lista das contagens baixadas (conferente, data), em vez de navegar por pastas.
   - **Onde mexer:**
     - leitura: `services/pdf_contagem_parser.py` (hoje) e um leitor novo do `.db`;
     - anexar: `_on_anexar_clicked` em `views/stock_analysis_page.py`;
     - validação: `ApiService.validate_sig` em `services/api_service.py`.

3. **Situação "Sem cadastro".**
   - **Por que:** um código que não existe no ERP cai como "sem lote", o estoque volta 0 e o registro aparece como Sobra. Isso mistura erro de cadastro com sobra física.
   - **Onde mexer:**
     - `StockAnalysisService.analisar` e `_buscar_controlarlote`, que já sabe quais códigos existem;
     - `aplicar_base`;
     - `_SITUACAO_LABEL` e `_SITUACAO_COR` em `views/stock_analysis_page.py`.

### B. Valor e priorização

4. **Valor da divergência em R$** (quantidade × custo do ERP).
   - **O que muda:** totais de falta, sobra e saldo líquido em R$, e a grade e a IA ordenadas por valor.
   - **Por que:** hoje `montar_payload_ia` ordena por quantidade, então 12 un. de um item de R$ 2 passam na frente de 1 un. de um item de R$ 3.000.
   - **A decidir:** qual custo usar e de onde ele vem no ERP: tabela produtosestoque, pelo codempresa (de acordo com a empresa logada), campos custoatual, customedio, customediocontabil, custocontabil, custoreposicao.

6. **Acurácia do inventário:** percentual de registros que conferem, em quantidade e em valor, por grupo e por localização.
   - **Hoje:** só existem os totais (`ResultadoAnalise`).
   - **Entrega:** também no cabeçalho do PDF.

### C. Explicar a divergência


8. **Observações do conferente, grupo e localização na grade**, e as observações também na IA.
   - **Hoje:** as observações ficam só no PDF e o grupo só vai para a IA.
   - **Dados:** já são lidos em `ContagemItem`.
   - **Onde mexer:**
     - `_montar_cabecalho` e `_popular_tabela`;
     - `montar_payload_ia`.
9. **Validade:** listar os lotes vencidos ou que vencem em N dias encontrados na contagem.
   - **Dados:** a validade já vem em `ContagemItem.validade` e em `dataval` no `.db`.
   - **Hoje:** não é usada.
10. **Cruzar com as métricas:** sinalizar as divergências de produtos digitados à mão ou lançados "sem GTIN".
    - **Onde mexer:** `services/metrics_service.py` já lê os ajustes e lançamentos manuais do `_metricas.enc`.

### D. Fechar o ciclo

11. **Gerar carga de recontagem:** selecionar as divergências e mandar direto para Exportar Carga, só com esses produtos.
    - **Assinatura:** reaproveita o fluxo que já leva os produtos selecionados da tela Produtos para Exportar Carga (`views/main_window_erp.py`), então a cadeia de assinatura se mantém.
    - **Retorno:** a recontagem volta como uma nova contagem e entra como mais uma coluna na análise.


### E. Entregáveis e uso da grade

14. **Exportar a grade em Excel**: hoje só existe PDF.
    - **Onde mexer:** as colunas já estão definidas em `_secao_comparativo`.
15. **Filtros e ordenação na grade**, na tabela da Análise de Estoque (`self._table`). Hoje não há nenhum dos dois:
    - filtrar por situação (só divergências), por grupo e por localização;
    - buscar por código ou descrição;
    - ordenar por coluna.
    
