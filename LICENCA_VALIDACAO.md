# Sistema de Validação de Licença - CSCollectManager

## 📋 Resumo das Alterações

O sistema foi atualizado para suportar o **novo formato de licença JSON** com validação híbrida (offline + online).

### ✅ Arquivos Criados/Modificados

1. **`services/license_validator.py`** (NOVO)
   - Módulo completo de validação de licença
   - Validação offline (token HMAC-SHA256)
   - Validação online (PostgreSQL)
   - Validação híbrida (recomendada)

2. **`licenca.py`** (ATUALIZADO)
   - Nova função `salvar_licenca_json()` para salvar no formato JSON
   - Modo interativo atualizado para solicitar `database_url`
   - Mantém compatibilidade com formato antigo

3. **`main.py`** (ATUALIZADO)
   - Validação de licença na abertura da aplicação
   - Suporte a leitura de CNPJ de `nome_device.json`
   - Mensagens de erro amigáveis

4. **`requirements.txt`** (ATUALIZADO)
   - Adicionado `psycopg2-binary>=2.9.0` (validação online PostgreSQL)
   - Adicionado `python-dotenv>=1.0.0` (variáveis de ambiente)

---

## 🔑 Formato do Arquivo de Licença (.key)

O arquivo `licenca.key` agora está no formato **JSON**:

```json
{
  "cnpjs": ["12345678000199", "98765432000188"],
  "ids": ["a3e9e3a0a4659652", "device-123"],
  "token": "eyJjbnBqcyI6WyIxMjM0NTY3ODAwMDE5OSIsIjk4NzY1NDMyMDAwMTg4Il0sImlkc19jZWx1bGFyIjpbImEzZTllM2EwYTQ2NTk2NTIiLCJkZXZpY2UtMTIzIl0sInZhbGlkYWRlIjoiMjAyNi0xMi0zMSIsIm5vbWVfY2xpZW50ZSI6IkVtcHJlc2EgQUJDIiwic3FsX3NlcnZpZG9yIjoiU0VSVklET1IxIiwic3FsX2JhbmNvIjoiREJfUFJPRCIsImdlcmFkb19lbSI6IjIwMjYtMDQtMThUMTQ6MzA6NDVaIn0.abcd1234...",
  "validade": "2026-12-31",
  "database_url": "postgresql://user:pass@host.region.aws.neon.tech:5432/dbname"
}
```

### Campos

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| `cnpjs` | Array | Sim | Lista de CNPJs autorizados |
| `ids` | Array | Sim | Lista de IDs de dispositivos autorizados |
| `token` | String | Sim | Token assinado (HMAC-SHA256) |
| `validade` | String/null | Não | Data de validade (YYYY-MM-DD) ou null |
| `database_url` | String/null | Não | Connection string PostgreSQL para validação online |

---

## 🚀 Como Usar

### 1. Gerar Nova Licença

```bash
# Modo interativo
python licenca.py

# O script irá solicitar:
# - CNPJs autorizados
# - IDs de dispositivos
# - Validade (opcional)
# - Nome do cliente (obrigatório)
# - Servidor SQL (obrigatório)
# - Banco de dados (obrigatório)
# - Database URL PostgreSQL (opcional - para validação online)
```

O arquivo será salvo como `Licenca_CSCollectManager_NomeCliente.key` no formato JSON.

### 2. Configurar MASTER_KEY

Crie um arquivo `.env` na raiz do projeto:

```env
MASTER_KEY=sua_chave_secreta_aqui_minimo_32_caracteres
```

⚠️ **IMPORTANTE**: Esta chave deve ser a mesma usada no gerador de licenças!

### 3. Instalar Dependências

```bash
pip install -r requirements.txt
```

### 4. Executar Aplicação

```bash
python main.py
```

A aplicação irá:
1. Validar a licença (`licenca.key`)
2. Verificar CNPJ (obtido de `nome_device.json` ou solicitado ao usuário)
3. Validar Device ID (obtido automaticamente do hardware)
4. Tentar validação online se `database_url` estiver presente
5. Se tudo OK, mostra tela de login

---

## 🔐 Validação da Licença

### Fluxo de Validação Híbrida

```
┌─────────────────────────────────────┐
│  1. Carrega licenca.key (JSON)      │
└────────────────┬────────────────────┘
                 │
┌────────────────▼────────────────────┐
│  2. Validação OFFLINE (obrigatória) │
│     ✓ Token HMAC-SHA256             │
│     ✓ CNPJ autorizado               │
│     ✓ Device ID autorizado          │
│     ✓ Validade (se definida)        │
└────────────────┬────────────────────┘
                 │
         ┌───────▼───────┐
         │ database_url? │
         └───┬───────┬───┘
             │       │
          Sim│       │Não
             │       │
┌────────────▼─┐     │
│ 3. Validação │     │
│    ONLINE    │     │
│  (opcional)  │     │
└────────────┬─┘     │
             │       │
             └───┬───┘
                 │
         ┌───────▼────────┐
         │  LICENÇA VÁLIDA │
         └─────────────────┘
```

### Validação Offline

- Sempre executada
- Verifica assinatura HMAC-SHA256 do token
- Valida CNPJ e Device ID contra as listas
- Verifica data de validade (se definida)
- **Não requer conexão com internet**

### Validação Online (Opcional)

- Executada se `database_url` estiver presente
- Conecta ao PostgreSQL e busca registro do cliente
- Verifica se licença está ativa no servidor
- Valida token, CNPJ e Device ID contra o banco
- Se falhar, **não bloqueia** (continua com validação offline)

---

## 🗄️ Estrutura do Banco de Dados (Validação Online)

```sql
CREATE TABLE clientes (
    id SERIAL PRIMARY KEY,
    cnpj TEXT NOT NULL,           -- CNPJs separados por vírgula (ordenados)
    idcelular TEXT,               -- IDs separados por vírgula
    token TEXT NOT NULL,          -- Token gerado
    validade DATE,                -- Data de validade ou NULL
    ativo BOOLEAN DEFAULT true,   -- Se licença está ativa
    nome_cliente VARCHAR(100),    -- Nome do cliente
    criado_em TIMESTAMP DEFAULT NOW(),
    atualizado_em TIMESTAMP DEFAULT NOW()
);

-- Exemplo de registro
INSERT INTO clientes (cnpj, idcelular, token, validade, ativo, nome_cliente)
VALUES (
    '12345678000199,98765432000188',
    'a3e9e3a0a4659652,device-123',
    'eyJjbnBqcyI6W...',
    '2026-12-31',
    true,
    'Empresa ABC Ltda'
);
```

---

## 📝 Exemplos de Uso

### Gerar Licença com Validação Online

```bash
$ python licenca.py

Modo interativo de gerenciamento de licença
Ler arquivo de licença existente? (s/n): n

Digite os CNPJs (apenas dígitos). Enter em branco para terminar:
CNPJ: 12345678000199
CNPJ: 98765432000188
CNPJ: 

Digite os IDs de celular. Enter em branco para terminar:
ID Celular: a3e9e3a0a4659652
ID Celular: device-123
ID Celular: 

Validade (YYYY-MM-DD ou ISO, vazio para sem validade): 2026-12-31
Nome do cliente (obrigatório, máx 30): Empresa ABC
Servidor SQL (obrigatório, máx 30): SERVIDOR1
Banco de dados (obrigatório, máx 30): DB_PROD
Database URL PostgreSQL para validação online (opcional, Enter para pular): postgresql://user:pass@host.neon.tech:5432/db

Salvar em (padrão 'Licenca_CSCollectManager_Empresa_ABC.key'): 

Licença gerada e salva em Licenca_CSCollectManager_Empresa_ABC.key (formato JSON)
```

### Validar Licença Programaticamente

```python
from services.license_validator import validar_licenca_completa, obter_device_id

try:
    resultado = validar_licenca_completa(
        caminho_key="licenca.key",
        cnpj_atual="12345678000199",
        device_id_atual=obter_device_id(),
        validar_online=True,      # Tenta validação online
        obrigar_online=False      # Não obriga online (permite offline)
    )
    
    print(f"✅ LICENÇA VÁLIDA")
    print(f"Cliente: {resultado['nome_cliente']}")
    print(f"Servidor: {resultado['sql_servidor']}")
    print(f"Banco: {resultado['sql_banco']}")
    print(f"Validação Online: {'Sim' if resultado['validacao_online'] else 'Não'}")
    
except ValueError as e:
    print(f"❌ LICENÇA INVÁLIDA: {e}")
except Exception as e:
    print(f"❌ ERRO: {e}")
```

---

## 🔒 Segurança

### Boas Práticas

1. **MASTER_KEY**
   - Manter em segredo absoluto
   - Não commitar no Git (.env no .gitignore)
   - Usar chave forte (mínimo 32 caracteres)
   - Mesma chave no gerador e validador

2. **Database URL**
   - Contém credenciais sensíveis
   - Usar usuário com permissões **somente leitura** (SELECT)
   - Connection string deve ser tratada como senha

3. **Device ID**
   - Baseado em MAC address do hardware
   - Identifica unicamente cada máquina
   - Impede uso da licença em dispositivos não autorizados

4. **Validação Híbrida**
   - Sempre valida offline primeiro (segurança local)
   - Validação online adiciona camada extra
   - Sistema funciona mesmo sem internet (offline)

---

## ⚠️ Troubleshooting

### Erro: "MASTER_KEY não definida"

**Solução**: Crie arquivo `.env` com:
```env
MASTER_KEY=sua_chave_aqui
```

### Erro: "psycopg2 não instalado"

**Solução**: Instale as dependências:
```bash
pip install psycopg2-binary
```

### Erro: "CNPJ não autorizado"

**Solução**: Verifique se o CNPJ está na lista `cnpjs` do arquivo `licenca.key`

### Erro: "Device ID não autorizado"

**Solução**: Obtenha o Device ID atual com:
```python
from services.license_validator import obter_device_id
print(obter_device_id())
```

E adicione na lista `ids` da licença.

### Validação online falha mas offline funciona

**Comportamento esperado**: O sistema continua funcionando com validação offline. Verifique:
- Connection string do PostgreSQL
- Registro existe no banco de dados
- Campo `ativo` está como `true`

---

## 📞 Suporte

Para dúvidas ou problemas:

1. Verifique se está usando a mesma `MASTER_KEY` no gerador e validador
2. Valide o formato do arquivo `.key` (deve ser JSON válido)
3. Teste a connection string isoladamente
4. Verifique se o registro existe na tabela `clientes` do PostgreSQL

---

## 📚 Documentação Adicional

Consulte também:
- [`views/orientacao.md`](views/orientacao.md) - Guia completo de integração
- [`services/license_validator.py`](services/license_validator.py) - Documentação das funções
- [`licenca.py`](licenca.py) - Geração e validação de tokens
