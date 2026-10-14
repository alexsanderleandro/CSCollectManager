# Ajuda — CSColetor Manager

> Documentação da versão: 26.10.14 rev. 2

Este guia explica as rotinas do CSColetor Manager: para que servem e como usar.

---

## 📦 Produtos — F1

**Para que serve:** consultar o catálogo de produtos e selecionar quais itens farão parte de uma carga a ser exportada para os coletores. Somente produtos definidos como item de inventário, ativos e controlando estoque estarão disponíveis para seleção.

**Como usar:**
1. Use o painel **🔍 Filtros**, à esquerda, para restringir a lista por Produto, Grupo de Estoque, Fornecedor, Fabricante, Localização ou Tipo de Produto — cada seção pode ser expandida clicando no título.
2. Marque **"Somente peso variável"** ou **"Somente produtos para venda"** se quiser refinar ainda mais o resultado.
3. A tabela à direita mostra os produtos que atendem aos filtros aplicados.
4. Selecione os produtos desejados na tabela e avance para **Exportar Carga (F2)** para configurar e gerar a exportação.

---

## 📤 Exportar Carga — F2

**Para que serve:** configurar e executar a exportação dos produtos selecionados para um coletor (dispositivo móvel).

**Como usar:**
1. **Diretório de saída** (obrigatório): clique em **📂 Procurar...** para escolher a pasta onde o arquivo de carga será gerado. O último diretório usado é lembrado automaticamente.
2. **Conferente** (obrigatório): clique em **🔍 Buscar** para selecionar o vendedor/conferente responsável pela carga. Somente serão listados os vendedores que estejam com usuário do sistema vinculado.
3. **Dispositivo móvel** (obrigatório): escolha, no combo, o aparelho habilitado na licença (.key). Use o botão **✏️** para definir um nome amigável para o dispositivo. Os aparelhos disponíveis vêm automaticamente da licença.
4. Em **Opções de exportação**, marque **"Incluir fotos dos produtos"** se desejar que as imagens sigam junto na carga.
5. Confira o **Resumo da Exportação** e clique em **📤 Iniciar Exportação [F11]** para gerar o arquivo, ou em **Cancelar [ESC]** para voltar sem exportar.

---

## 📋 Histórico — F3

**Para que serve:** consultar exportações de carga já realizadas anteriormente.

**Como usar:**
1. Clique em **🔄 Atualizar [F5]** para recarregar a lista mais recente do histórico.
2. A lista mostra só as exportações da empresa logada. Marque **Todas as empresas** para ver as de todas, com a empresa indicada em cada linha.
3. Dê duplo clique num item da lista para ver seus detalhes.
4. Clique com o botão direito num item para abrir o menu de contexto, com opções como **📂 Abrir Pasta** (abre a pasta onde o arquivo exportado foi salvo) e **📡 Reenviar para API**.
5. Use **📂 Abrir Pasta** (barra de controles) para abrir a pasta do item selecionado, ou **🗑️ Limpar Histórico** para apagar as exportações que estão na lista — só as da empresa logada ou, com **Todas as empresas** marcado, todas (ação irreversível).

---

## 📥 Download Contagens — F4

**Para que serve:** baixar e validar os arquivos de contagem de inventário enviados pelos coletores (aplicativo móvel CSColetor) para o servidor.

**Como usar:**
1. Clique em **🔄 Atualizar [F5]** para listar as contagens disponíveis no servidor — a tabela mostra ID, Nome do Arquivo, Vendedor, Aparelho, CNPJ e Data de Envio.
2. Selecione uma linha da tabela (clique único).
3. Clique em **⬇️ Baixar Selecionado [F8]** para salvar o arquivo na pasta Cargas local.
4. Acompanhe o resultado da operação na mensagem de status logo abaixo da tabela.

---

## 📊 Métricas — F7

**Para que serve:** acompanhar a produtividade dos conferentes: quantas contagens fizeram, em quanto tempo, quanto tempo ficaram parados, quantos códigos lidos não existiam na carga e quantas quantidades foram digitadas à mão. Os dados vêm das próprias contagens baixadas em **Download Contagens (F4)** — não é preciso baixar nada a mais.

**Como usar:**
1. Clique em **🔄 Atualizar [F5]** para ler as contagens da pasta de contagens. A lista fica agrupada por conferente; clique no nome do conferente para recolher ou expandir o grupo.
2. Cada linha é uma contagem baixada, com Início, Fim, Contagens, Não Encontrados, Duplicados e Ajustes Manuais. Clique no título de uma coluna para ordenar — as linhas são reordenadas dentro de cada conferente.
3. Selecione uma linha e clique em **🔍 Ver Detalhes** (ou dê duplo clique) para abrir o painel completo daquela contagem.

**No painel de detalhes:**
- **Indicadores no topo:** Contagens (e quantos produtos diferentes), Produtivo, Ocioso (com o percentual da jornada), Entre contagens (o intervalo típico entre uma contagem e a próxima), Não encontrados e Ajustes manuais. Clique em **Não encontrados** para ver os códigos lidos que não existem na carga, com os botões **Copiar códigos** e **Exportar PDF**.
- **Resumo:** sessões do dia, projeção de contagens por hora de trabalho efetivo, barra Produtivo × Ocioso, contagens por hora, origem da entrada (Bipado, Digitado, Falado, Agrupado, Sem GTIN e Correção de quantidade) e blocos de trabalho. Em **💸 Valor/hora do conferente**, digite quanto custa uma hora do conferente para ver quanto custou o tempo parado (o valor não é gravado).
- **Ajustes manuais:** produtos que tiveram a quantidade digitada em vez de bipada.
- **Lançamentos manuais:** quantidades lançadas pela tela Consultar Produtos do coletor — produtos sem código de barras e correções de quantidade.
- **Produtividade por localização:** contagens, tempo produtivo e contagens por hora em cada localização.
- O botão **❓** explica como ler o indicador ao lado dele, e o **⛶** abre a tabela em tela cheia.

**Observação:** uma pausa entre contagens maior que o **Deslocamento máximo entre contagens** (definido em Exportar Carga) conta como tempo ocioso. Contagens geradas por versões antigas do coletor não trazem todos os indicadores — o painel avisa quando falta algum.

---

## 🔎 Análise de Estoque

**Para que serve:** comparar o que os conferentes contaram com o estoque do sistema, mostrar as faltas e sobras em quantidade e em R$, medir a acurácia do estoque e, se quiser, pedir à IA uma análise das divergências. Compara até 3 contagens lado a lado — por exemplo, a contagem e a recontagem.

**Como usar:**
1. Clique em **📥 Selecionar contagens...** e marque até 3 contagens da lista. Aparecem as contagens da empresa logada já baixadas em **Download Contagens (F4)**. A assinatura de cada arquivo é conferida: arquivo alterado ou de outra empresa é recusado.
2. Confira a **Data de referência** (o estoque do sistema é o daquela data) e o **Local de Estoque** (Loja, Depósito ou os dois), que já vem preenchido conforme o cadastro da empresa. Mudar qualquer um dos dois refaz a comparação.
3. O resultado aparece na aba **📊 Resultado comparativo**. Na lista de contagens, acima das abas, dê duplo clique numa contagem para ver só ela na grade; o botão direito tem também **Remover da análise**. **Limpar** recomeça do zero.

**📊 Resultado comparativo:**
- Uma coluna **Contado** para cada contagem, seguida de Sistema, Diferença, Valor (R$), Situação, Entrada, Custo (R$), Grupo, Localização e Observações (as observações que o conferente escreveu no coletor).
- **Situação:** Confere, Falta, Sobra, **Lote novo** (lote contado que não existe no sistema), **Sem cadastro** (código que não existe no cadastro de produtos) e **Não contado** (só outra contagem contou aquele item).
- **Entrada:** avisa quando a quantidade não foi bipada — digitada à mão, lançada sem GTIN ou corrigida depois. Confira essas divergências antes de ajustar o estoque.
- Com mais de uma contagem, clique no título da coluna **Contado** do conferente que deve ser comparado com o sistema — ela passa a ser a base da diferença, marcada com ●. O seletor **Base da diferença**, acima da grade, faz o mesmo. Em **Considerar na exportação e na IA**, escolha quais contagens vão para o PDF, o Excel e a IA.
- Filtre por situação, grupo e localização, ou busque por código ou descrição. Clique no título das demais colunas (e no da coluna que já é a base) para ordenar.
- Em **Valor pelo**, escolha o custo usado nos valores em R$: custo médio, atual, médio contábil, contábil ou de reposição. A escolha fica gravada.
- A linha acima da grade mostra a falta, a sobra e o saldo líquido em R$, além da acurácia.

**🤖 Análise da IA:**
1. Antes, configure o provedor de IA em **Configurações (F12)**.
2. No campo **Enviar**, ao lado do botão, escolha quantas divergências vão para a IA (as de maior valor primeiro) e clique em **🤖 Analisar com IA**.
3. A análise aparece na aba **🤖 Análise da IA**. No fim dela, os cartões de **Aprofundar esta análise** pedem mais à IA: 📋 Plano de ação detalhado, 🔎 Explicar um produto, 📝 Resumo curto para a gerência e 👥 Onde os conferentes discordam (só com duas contagens ou mais). Cada cartão faz um novo pedido à IA e acrescenta uma seção à análise.

**🎯 Acurácia:** percentual de registros que conferem com o sistema, em quantidade e em valor, por grupo e por localização. Entram só os registros comparados (Confere, Falta e Sobra). Passe o mouse no título de uma coluna para ver a fórmula; dê duplo clique numa linha (ou clique em **ver a conta**) para ver a conta registro a registro.

**⏳ Validade:** lotes contados já vencidos na data de referência ou que vencem nos dias seguintes — você escolhe quantos dias.

**Recontagem e exportação:**
- **🔁 Gerar recontagem:** leva para **Exportar Carga (F2)** só os produtos das linhas selecionadas na grade (sem seleção, todas as faltas e sobras visíveis), no mesmo local de estoque. Escolha o conferente e o dispositivo e exporte normalmente; **ESC** cancela a recontagem.
- **Exportar ▾:** PDF do resultado comparativo, PDF da análise da IA, os dois juntos, PDF da validade dos lotes e a grade em Excel (.xlsx). O PDF do comparativo e o Excel seguem os filtros aplicados na grade.

**Observação:** a análise compara só os produtos que aparecem em alguma contagem: produtos com estoque que ninguém contou não entram na grade.

---

## Atalhos de teclado

| Tecla | Ação |
|---|---|
| F1 | Ir para Produtos |
| F2 | Ir para Exportar Carga |
| F3 | Ir para Histórico |
| F4 | Ir para Download Contagens |
| F5 | Atualizar (Histórico / Download Contagens / Métricas) |
| F7 | Ir para Métricas |
| F8 | Baixar Selecionado (Download Contagens) |
| F11 | Iniciar Exportação (Exportar Carga) |
| ESC | Cancelar (Exportar Carga) |
| F10 | Sair do aplicativo |
