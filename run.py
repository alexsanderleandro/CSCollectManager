"""
run.py
======
Ponto de entrada principal do CSCollectManager.

Fluxo do Sistema:
    1. Login (usuário/senha)
    2. Escolha da base de dados
    3. Seleção de empresa
    4. Tela principal (filtros + listagem)
    5. Exportação (TXT + Fotos.zip)

Uso:
    python run.py
"""

import sys
import os

# Adiciona diretório raiz ao path
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT_DIR)

from PySide6.QtWidgets import QApplication, QMessageBox, QSplashScreen
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QIcon, QPixmap

from app.styles import DarkTheme, apply_theme
from utils.logger import get_logger, setup_logging
from utils.error_handler import setup_exception_handler
from utils.constants import APP_INFO

logger = get_logger(__name__)


class CSCollectManagerApp:
    """
    Aplicação principal CSCollectManager.
    
    Gerencia o ciclo de vida completo:
    - Splash screen
    - Login/autenticação
    - Seleção de base/empresa
    - Janela principal ERP
    - Logout/reconexão
    """
    
    def __init__(self):
        # Configura logging
        setup_logging()
        logger.info("=" * 60)
        logger.info(f"Iniciando {APP_INFO.NAME} v{APP_INFO.VERSION}")
        logger.info("=" * 60)
        
        # High DPI deve ser configurado ANTES de criar QApplication
        QApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )
        
        # Cria aplicação Qt
        self.app = QApplication(sys.argv)
        self._setup_app()
        
        # Configura handler de exceções global (depois do QApplication)
        setup_exception_handler()
        
        # Componentes
        self._splash: QSplashScreen = None
        self._login_dialog = None
        self._main_window = None
        
        # Estado
        self._connection_info = {}
        self._empresa_info = {}
        self._usuario_info = {}
    
    def _setup_app(self):
        """Configura propriedades da aplicação."""
        self.app.setApplicationName(APP_INFO.NAME)
        self.app.setApplicationVersion(APP_INFO.VERSION)
        self.app.setOrganizationName(APP_INFO.COMPANY)
        
        # Fonte padrão
        font = QFont("Segoe UI", 10)
        self.app.setFont(font)
        
        # Ícone
        icon_path = os.path.join(ROOT_DIR, "assets", "icon.ico")
        if os.path.exists(icon_path):
            self.app.setWindowIcon(QIcon(icon_path))
        
        # Aplica tema escuro
        apply_theme(self.app, "dark")
        
        logger.debug("Aplicação Qt configurada")
    
    def run(self) -> int:
        """
        Executa a aplicação.
        
        Returns:
            Código de saída (0=sucesso)
        """
        try:
            # Mostra splash screen
            self._show_splash()
            
            # Inicia fluxo de login após splash
            QTimer.singleShot(1500, self._start_login_flow)
            
            return self.app.exec()
            
        except Exception as e:
            logger.critical(f"Erro fatal: {e}", exc_info=True)
            QMessageBox.critical(
                None, "Erro Fatal",
                f"Ocorreu um erro crítico:\n\n{str(e)}\n\nA aplicação será encerrada."
            )
            return 1
    
    def _show_splash(self):
        """Mostra splash screen."""
        splash_path = os.path.join(ROOT_DIR, "assets", "splash.png")
        
        if os.path.exists(splash_path):
            pixmap = QPixmap(splash_path)
        else:
            # Cria splash simples se não houver imagem
            pixmap = QPixmap(500, 300)
            pixmap.fill(Qt.GlobalColor.transparent)
        
        self._splash = QSplashScreen(pixmap)
        self._splash.setStyleSheet("""
            QSplashScreen {
                background-color: #1e1e1e;
                border: 1px solid #0078d4;
                border-radius: 8px;
            }
        """)
        self._splash.showMessage(
            f"\n\n\n\n\n📦 {APP_INFO.NAME}\n\nCarregando sistema...",
            Qt.AlignmentFlag.AlignCenter,
            Qt.GlobalColor.white
        )
        self._splash.show()
        self.app.processEvents()
        
        logger.debug("Splash screen exibida")
    
    def _start_login_flow(self):
        """Inicia fluxo de login."""
        # Fecha splash
        if self._splash:
            self._splash.close()
            self._splash = None
        
        self._show_login()
    
    def _show_login(self):
        """Mostra diálogo de login."""
        from views.login_dialog import LoginDialog
        
        logger.info("Exibindo tela de login")
        
        # Fecha janela principal se existir
        if self._main_window:
            self._main_window.close()
            self._main_window = None
        
        # Cria diálogo de login
        self._login_dialog = LoginDialog()
        self._login_dialog.login_successful.connect(self._on_login_success)
        self._login_dialog.show()
    
    def _on_login_success(self, login_data: dict):
        """
        Callback de login bem-sucedido.
        
        Args:
            login_data: Dados do login (conexão, empresa, usuário)
        """
        self._connection_info = login_data.get("connection", {})
        self._empresa_info = login_data.get("empresa", {})
        self._usuario_info = login_data.get("usuario", {})
        
        logger.info(
            f"Login bem-sucedido: {self._usuario_info.get('nome', 'N/A')} "
            f"@ {self._empresa_info.get('nome', 'N/A')}"
        )
        
        # Fecha diálogo de login
        if self._login_dialog:
            self._login_dialog.close()
            self._login_dialog = None
        
        # Mostra janela principal
        self._show_main_window()
    
    def _show_main_window(self):
        """Mostra janela principal ERP."""
        from views.main_window_erp import MainWindowERP
        
        logger.info("Abrindo janela principal")
        
        self._main_window = MainWindowERP()
        
        # Configura informações de conexão
        self._main_window.set_connection_info(
            empresa=self._empresa_info,
            usuario=self._usuario_info,
            connection=self._connection_info
        )
        
        # Conecta sinais
        self._main_window.logout_requested.connect(self._on_logout)
        self._main_window.export_requested.connect(self._on_export)
        
        # Carrega estatísticas iniciais (exemplo)
        self._load_statistics()
        
        self._main_window.show()
    
    def _load_statistics(self):
        """Carrega estatísticas para o dashboard."""
        # TODO: Buscar do banco de dados
        # Por enquanto, valores de exemplo
        self._main_window.update_statistics(
            products=0,
            exports=0,
            photos=0,
            pending=0
        )
    
    def _on_logout(self):
        """Callback de logout."""
        logger.info("Logout solicitado")
        
        # Limpa estado
        self._connection_info = {}
        self._empresa_info = {}
        self._usuario_info = {}
        
        # Volta para login
        self._show_login()
    
    def _on_export(self, export_data: dict):
        """
        Callback de exportação.
        
        Args:
            export_data: Dados da exportação
        """
        codprodutos = export_data.get("codprodutos", [])
        logger.info(f"Exportação solicitada: {len(codprodutos)} produtos")
        # TODO: Implementar exportação via ExportService


def main():
    """Função principal."""
    app = CSCollectManagerApp()
    sys.exit(app.run())


if __name__ == "__main__":
    main()
