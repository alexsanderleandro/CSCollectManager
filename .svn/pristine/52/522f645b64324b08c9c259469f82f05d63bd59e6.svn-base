# CSCollectManager

Sistema de retaguarda para exportação de carga de inventário para coletores de dados.

## Requisitos

- Python 3.10+
- Microsoft SQL Server
- ODBC Driver 17 for SQL Server (ou superior)

## Instalação

1. Clone o repositório ou copie os arquivos para o diretório desejado.

2. Crie um ambiente virtual:
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

3. Instale as dependências:
```powershell
pip install -r requirements.txt
```

## Execução

```powershell
python -m app.main
```

Ou:
```powershell
cd app
python main.py
```

## Estrutura do Projeto

```
CSCollectManager/
├── app/                    # Ponto de entrada da aplicação
│   ├── __init__.py
│   └── main.py            # Inicialização do PySide6
│
├── controllers/           # Camada de controle (MVC)
│   ├── __init__.py
│   ├── base_controller.py
│   ├── login_controller.py
│   ├── main_controller.py
│   └── inventory_controller.py
│
├── services/              # Camada de serviços (lógica de negócio)
│   ├── __init__.py
│   ├── auth_service.py
│   ├── connection_service.py
│   ├── inventory_service.py
│   └── export_service.py
│
├── repositories/          # Camada de acesso a dados
│   ├── __init__.py
│   ├── base_repository.py
│   ├── inventory_repository.py
│   └── user_repository.py
│
├── models/               # Modelos de dados
│   ├── __init__.py
│   ├── user.py
│   ├── connection.py
│   ├── inventory.py
│   └── company.py
│
├── views/                # Interface gráfica (PySide6)
│   ├── __init__.py
│   ├── base_view.py
│   ├── login_view.py
│   ├── main_view.py
│   └── inventory_view.py
│
├── widgets/              # Componentes visuais reutilizáveis
│   ├── __init__.py
│   ├── loading_overlay.py
│   ├── searchable_combo.py
│   └── data_table.py
│
├── utils/                # Utilitários
│   ├── __init__.py
│   ├── config.py
│   ├── theme_manager.py
│   ├── validators.py
│   └── formatters.py
│
├── database/             # Gerenciamento de conexões
│   ├── __init__.py
│   └── connection_manager.py
│
├── assets/               # Recursos estáticos
│   └── logo.png
│
├── authentication.py     # Módulo de autenticação (existente)
├── login.py             # Módulo de conexões (existente)
├── requirements.txt
└── README.md
```

## Arquitetura MVC

### Controllers
Intermediam a comunicação entre Views e Services. Processam eventos da UI, validam dados de entrada e coordenam fluxos de trabalho.

### Services
Implementam a lógica de negócio. Orquestram operações entre múltiplos repositórios e validam regras de negócio.

### Repositories
Encapsulam acesso ao banco de dados. Mapeiam dados do banco para objetos do domínio.

### Models
Definem estruturas de dados do domínio. Representam entidades do sistema.

### Views
Definem interfaces de usuário com PySide6. Exibem dados e capturam eventos de interação.

### Widgets
Componentes visuais personalizados e reutilizáveis.

### Utils
Funções auxiliares, configurações e helpers.

### Database
Gerenciamento centralizado de conexões com SQL Server.

## Configuração

O sistema utiliza o arquivo `cslogin.xml` para configuração de conexões com o banco de dados. O arquivo deve estar em um dos seguintes locais:

- Diretório atual
- Diretório da aplicação
- `C:\CEOSoftware\cslogin.xml`

## Autor

CEOSoftware

## Licença

Proprietário - Todos os direitos reservados.
