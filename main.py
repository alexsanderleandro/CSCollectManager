"""
main.py
=======
Ponto de entrada principal do sistema CSCollectManager.
"""

import sys
import os

# Adiciona o diretório raiz ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QIcon

from views.login_view import LoginView
from views.main_window import MainWindow
from controllers.login_controller import LoginController
from utils.config import Config


class CSCollectManagerApp:
    """
    Classe principal da aplicação CSCollectManager.
    Gerencia o ciclo de vida e navegação entre telas.
    """
    
    def __init__(self):
        self.app = QApplication(sys.argv)
        self._setup_app()
        
        self.login_view: LoginView = None
        self.main_window: MainWindow = None
        self.login_controller: LoginController = None
        
        # Informações de conexão após login
        self._connection_info = {}
    
    def _setup_app(self):
        """Configura a aplicação."""
        # Nome da aplicação
        self.app.setApplicationName("CSCollectManager")
        self.app.setApplicationVersion("1.0.0")
        self.app.setOrganizationName("CEOsoftware")
        
        # Fonte padrão
        font = QFont("Segoe UI", 10)
        self.app.setFont(font)
        
        # Ícone (se existir)
        icon_path = os.path.join(os.path.dirname(__file__), "assets", "icon.ico")
        if os.path.exists(icon_path):
            self.app.setWindowIcon(QIcon(icon_path))
        
        # Habilita High DPI
        self.app.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )
        
        # Estilo global
        self.app.setStyleSheet("""
            QToolTip {
                background-color: #2d2d30;
                color: #cccccc;
                border: 1px solid #555;
                padding: 5px;
            }
        """)
    
    def run(self) -> int:
        """
        Executa a aplicação.
        
        Returns:
            Código de saída
        """
        try:
            # Inicia com tela de login
            self._show_login()
            return self.app.exec()
            
        except Exception as e:
            QMessageBox.critical(
                None, "Erro Fatal",
                f"Ocorreu um erro crítico:\n\n{str(e)}"
            )
            return 1
    
    def _show_login(self):
        """Mostra tela de login."""
        # Fecha janela principal se aberta
        if self.main_window:
            self.main_window.close()
            self.main_window = None
        
        # Cria view e controller de login
        self.login_view = LoginView()
        self.login_controller = LoginController(self.login_view)
        
        # Conecta sinal de sucesso
        self.login_controller.login_success.connect(self._on_login_success)
        
        self.login_view.show()
    
    def _on_login_success(self, connection_info: dict):
        """
        Callback quando login é bem sucedido.
        
        Args:
            connection_info: Informações da conexão
        """
        self._connection_info = connection_info
        
        # Fecha tela de login
        if self.login_view:
            self.login_view.close()
            self.login_view = None
        
        # Mostra janela principal
        self._show_main_window()
    
    def _show_main_window(self):
        """Mostra janela principal."""
        self.main_window = MainWindow()
        
        # Define informações da conexão
        self.main_window.set_connection_info(
            empresa=self._connection_info.get("empresa_nome", ""),
            usuario=self._connection_info.get("usuario_nome", ""),
            database=self._connection_info.get("database", "")
        )
        
        # Conecta sinal de logout
        self.main_window.logout_requested.connect(self._on_logout)
        
        # Carrega dados iniciais
        self._load_initial_data()
        
        self.main_window.show()
    
    def _on_logout(self):
        """Callback quando logout é solicitado."""
        self._connection_info = {}
        self._show_login()
    
    def _load_initial_data(self):
        """Carrega dados iniciais na janela principal."""
        # TODO: Implementar carregamento de dados do banco
        # Por enquanto, carrega dados de exemplo
        
        # Dados de exemplo para filtros
        self.main_window.load_filter_data(
            grupos=[(1, "Bebidas"), (2, "Alimentos"), (3, "Limpeza"), (4, "Higiene")],
            tipos_produto=[(1, "Revenda"), (2, "Consumo"), (3, "Matéria-prima")],
            localizacoes=[(1, "A1"), (2, "A2"), (3, "B1"), (4, "B2")],
        )
        
        # Dados de exemplo para produtos
        test_products = [
            {
                "codigo": 1,
                "referencia": "REF001",
                "descricao": "Coca-Cola 2L",
                "grupo_nome": "Bebidas",
                "unidade": "UN",
                "estoque": 150,
                "custo": 5.50,
                "venda": 8.90,
                "localizacao": "A1-01"
            },
            {
                "codigo": 2,
                "referencia": "REF002",
                "descricao": "Arroz Tio João 5kg",
                "grupo_nome": "Alimentos",
                "unidade": "UN",
                "estoque": 45,
                "custo": 18.00,
                "venda": 28.90,
                "localizacao": "B2-03"
            },
            {
                "codigo": 3,
                "referencia": "REF003",
                "descricao": "Detergente Ypê 500ml",
                "grupo_nome": "Limpeza",
                "unidade": "UN",
                "estoque": 0,
                "custo": 2.00,
                "venda": 3.50,
                "localizacao": "C1-02"
            },
            {
                "codigo": 4,
                "referencia": "REF004",
                "descricao": "Sabonete Dove 90g",
                "grupo_nome": "Higiene",
                "unidade": "UN",
                "estoque": -10,
                "custo": 3.50,
                "venda": 5.90,
                "localizacao": ""
            },
        ]
        
        self.main_window.load_products(test_products)
        self.main_window.set_status("Dados carregados com sucesso")


def main():
    """Função principal."""
    app = CSCollectManagerApp()
    sys.exit(app.run())


if __name__ == "__main__":
    main()
