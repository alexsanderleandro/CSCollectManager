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

from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QIcon

from app.styles import DarkTheme, apply_theme
from utils.logger import get_logger, setup_logging
from utils.error_handler import setup_exception_handler
from authentication import DBConfig, set_db_config
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
        # (Chaves não são geradas automaticamente no startup)
        
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
        self._splash = None  # AnimatedSplash (widgets/splash_screen.py)
        self._login_dialog = None
        self._main_window = None
        
        # Estado
        self._connection_info = {}
        self._empresa_info = {}
        self._usuario_info = {}
        self._licenca_info = {}  # Payload da licença (.key)
    
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
            # Mostra splash animado; ao terminar, ele dispara o fluxo de login
            self._show_splash()

            return self.app.exec()
            
        except Exception as e:
            logger.critical(f"Erro fatal: {e}", exc_info=True)
            QMessageBox.critical(
                None, "Erro Fatal",
                f"Ocorreu um erro crítico:\n\n{str(e)}\n\nA aplicação será encerrada."
            )
            return 1
    
    def _show_splash(self):
        """Mostra splash animado (conforme docs em assets/) e agenda o login."""
        try:
            from app.splash import AnimatedSplash

            # Resolve o ícone tanto em dev quanto no bundle PyInstaller onefile
            # (assets extraídos em sys._MEIPASS). Usa ceo-icon.png se existir,
            # senão o logo da marca (fundo transparente).
            base_dir = getattr(sys, "_MEIPASS", ROOT_DIR)
            icon_path = os.path.join(base_dir, "assets", "ceo-icon.png")
            if not os.path.exists(icon_path):
                icon_path = os.path.join(base_dir, "assets", "logo.png")

            self._splash = AnimatedSplash(
                on_finish=self._start_login_flow,
                icon_path=icon_path,
                title="CEOsoftware Sistemas",
                subtitle="INVENTÁRIO INTELIGENTE",
            )
            self._splash.start(duration=3.0)
            self.app.processEvents()
            logger.debug("Splash animado exibido")
        except Exception as e:
            # Splash nunca deve impedir a inicialização: segue direto p/ login.
            logger.warning(f"Falha ao exibir splash: {e}", exc_info=True)
            self._splash = None
            QTimer.singleShot(0, self._start_login_flow)
    
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
        self._licenca_info = login_data.get("licenca", {})
        licenca_token = login_data.get("licenca_token", "")

        # Configura conexão global do banco de dados
        server = self._connection_info.get("server", "localhost")
        database = self._connection_info.get("database", "master")
        
        db_config = DBConfig(
            server=server,
            database=database,
            auth="trusted"  # Windows Authentication
        )
        set_db_config(db_config)
        
        logger.info(
            f"Login bem-sucedido: {self._usuario_info.get('nome', 'N/A')} "
            f"@ {self._empresa_info.get('nome', 'N/A')}"
        )
        logger.info(f"Conexão configurada: {server}/{database}")
        
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
            connection=self._connection_info,
            licenca=self._licenca_info
        )
        
        # Conecta sinais
        self._main_window.logout_requested.connect(self._on_logout)
        self._main_window.export_requested.connect(self._on_export)

        # Exibe a janela imediatamente; os dados dos filtros são carregados
        # em background logo em seguida, sem travar o primeiro paint.
        self._main_window.show()

        # Carrega dados nos combos de filtro a partir do banco
        self._load_filter_data()
    
    def _load_filter_data(self):
        """Carrega dados dos combos de filtro a partir do banco de dados."""
        try:
            self._main_window.load_filter_data()
        except Exception as e:
            logger.warning(f"Erro ao carregar dados dos filtros: {e}")
    
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
