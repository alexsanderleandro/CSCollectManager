# Ajuda — LogScan Manager

> Documentação da versão: 26.07.22 rev. 1

Este guia explica as rotinas do LogScan Manager: para que servem e como usar.

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
2. Dê duplo clique num item da lista para ver seus detalhes.
3. Clique com o botão direito num item para abrir o menu de contexto, com opções como **📂 Abrir Pasta** (abre a pasta onde o arquivo exportado foi salvo) e **📡 Reenviar para API**.
4. Use **📂 Abrir Pasta** (barra de controles) para abrir a pasta do item selecionado, ou **🗑️ Limpar Histórico** para apagar todo o registro (ação irreversível).

---

## 📥 Download Contagens — F4

**Para que serve:** baixar e validar os arquivos de contagem de inventário enviados pelos coletores (aplicativo móvel LogScan) para o servidor.

**Como usar:**
1. Clique em **🔄 Atualizar [F5]** para listar as contagens disponíveis no servidor — a tabela mostra ID, Nome do Arquivo, Vendedor, Aparelho, CNPJ e Data de Envio.
2. Selecione uma linha da tabela (clique único).
3. Clique em **⬇️ Baixar Selecionado [F8]** para salvar o arquivo na pasta Cargas local.
4. Acompanhe o resultado da operação na mensagem de status logo abaixo da tabela.

---

## Atalhos de teclado

| Tecla | Ação |
|---|---|
| F1 | Ir para Produtos |
| F2 | Ir para Exportar Carga |
| F3 | Ir para Histórico |
| F4 | Ir para Download Contagens |
| F5 | Atualizar (Histórico / Download Contagens) |
| F8 | Baixar Selecionado (Download Contagens) |
| F11 | Iniciar Exportação (Exportar Carga) |
| ESC | Cancelar (Exportar Carga) |
| F10 | Sair do aplicativo |
