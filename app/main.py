"""
main.py
=======
Ponto de entrada principal do sistema CSCollectManager.

Este módulo inicializa a aplicação PySide6, configura o tema,
carrega recursos e inicia a janela de login.
"""

import sys
import os

# Adiciona o diretório raiz ao path para importações
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon, QFont
from PySide6.QtCore import Qt

from utils.constants import APP_INFO, init_app_directories
from utils.logger import get_logger
from utils.error_handler import setup_error_handler
from app.styles import apply_theme, DarkTheme


# Logger para este módulo
logger = get_logger("main")


def setup_application() -> QApplication:
    """
    Configura e retorna a instância da aplicação Qt.
    """
    logger.info(f"Iniciando {APP_INFO.NAME} v{APP_INFO.VERSION}")
    
    # Cria diretórios necessários
    init_app_directories()
    
    # Habilita High DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    
    app = QApplication(sys.argv)
    app.setApplicationName(APP_INFO.NAME)
    app.setApplicationVersion(APP_INFO.VERSION)
    app.setOrganizationName("CEOSoftware")
    app.setOrganizationDomain("ceosoftware.com.br")
    
    # Configura ícone da aplicação
    from utils.config import AppConfig
    icon_path = AppConfig.get_asset_path("logo.png")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    
    # Aplica tema escuro
    apply_theme(app, "dark")
    logger.debug("Tema escuro aplicado")
    
    # Configura fonte padrão
    font = QFont("Segoe UI", 10)
    app.setFont(font)
    
    # Configura tratamento de erros global
    setup_error_handler()
    logger.debug("Handler de erros configurado")
    
    return app


def main():
    """
    Função principal que inicia a aplicação.
    """
    try:
        app = setup_application()
        
        # Inicia com a tela de login
        from views.login_view import LoginView
        login_view = LoginView()
        login_view.show()
        
        logger.info("Aplicação iniciada com sucesso")
        
        exit_code = app.exec()
        
        # Verifica se deve reiniciar (código 1000)
        if exit_code == 1000:
            logger.info("Reiniciando aplicação...")
            os.execv(sys.executable, ['python'] + sys.argv)
        
        logger.info(f"Aplicação encerrada com código {exit_code}")
        sys.exit(exit_code)
        
    except Exception as e:
        logger.critical(f"Erro fatal ao iniciar aplicação: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
