# Ideias futuras

Ideias já discutidas e deixadas para depois, com o contexto necessário para retomar.

*Nenhuma ideia pendente no momento.*

## Implementadas

### Análise de Estoque (30/09/2026)

Tudo o que estava listado aqui foi aplicado. Decisões tomadas no caminho:

- **Contagens em vez de PDF avulso:** o botão "Selecionar contagens..." lista os ZIPs baixados na tela Download Contagens (até 3). Cada ZIP é conferido com o `.sig` ao entrar na análise. Os itens vêm do `.db`, as observações do PDF de dentro do ZIP e os sinais de entrada manual do `_metricas.enc`. O local de estoque é marcado sozinho a partir de `Empresa.local`. Um item do menu do botão direito na lista remove uma contagem, o que abre vaga para a recontagem.
- **Sem cadastro:** código que não existe em `produtos` vira a situação "Sem cadastro" (cor própria), sem consultar estoque. Não conta mais como sobra.
- **Valor em R$:** o custo é escolhido na tela ("Valor pelo"), entre os 5 campos de `produtosestoque`. Começa no custo médio e guarda a última escolha. Os cinco campos são lidos de uma vez, então trocar de campo não consulta o banco. Campo inexistente no ERP fica sem valor, sem derrubar a análise.
- **Acurácia:** aba própria, com a acurácia por grupo e por localização, e a acurácia geral no cabeçalho do PDF. Entram só os registros comparados (conferem, falta e sobra). Em valor, cada registro pesa custo × a maior quantidade entre contado e sistema.
- **Grade:** colunas novas de valor, entrada, custo, grupo, localização e observações. Filtros por situação, grupo, localização e busca. O cabeçalho ordena, e a base da diferença passou para um seletor acima da grade. A ordem padrão é pelo valor da divergência.
- **Validade:** aba própria com os lotes vencidos até a data de referência ou que vencem em N dias (N guardado). A aba também exporta em PDF.
- **Recontagem:** o botão "Gerar recontagem" leva para Exportar Carga os produtos das linhas selecionadas, ou as divergências visíveis quando não há seleção. A carga passa pelo mesmo fluxo de exportação e assinatura.
- **Excel:** exporta a grade como está na tela (filtro e ordem), sem dependência nova (`utils/xlsx_writer.py`). O PDF do resultado comparativo também segue o filtro e informa isso no cabeçalho.
- **Aprofundar a análise da IA:** layout B aprovado (cartões no fim do texto). Os cartões são: plano de ação, explicar um produto, resumo para a gerência e onde os conferentes discordam (este só com 2 contagens ou mais). "Explicar um produto" usa a linha selecionada na grade ou abre a lista das divergências, e o mesmo produto não pode ser explicado duas vezes. Cada resposta entra como seção nova na aba e no PDF.
