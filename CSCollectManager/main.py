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
from services.license_validator import validar_licenca_completa, obter_device_id


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
            # Valida licença antes de iniciar
            if not self._validar_licenca():
                return 1
            
            # Inicia com tela de login
            self._show_login()
            return self.app.exec()
            
        except Exception as e:
            QMessageBox.critical(
                None, "Erro Fatal",
                f"Ocorreu um erro crítico:\n\n{str(e)}"
            )
            return 1
    
    def _validar_licenca(self) -> bool:
        """
        Valida a licença do sistema antes de iniciar.
        
        Returns:
            True se licença válida, False caso contrário
        """
        caminho_licenca = os.path.join(os.path.dirname(__file__), "licenca.key")
        
        # Verifica se arquivo de licença existe
        if not os.path.exists(caminho_licenca):
            QMessageBox.critical(
                None, "Licença Não Encontrada",
                "Arquivo de licença (licenca.key) não encontrado.\n\n"
                "A aplicação não pode ser iniciada sem uma licença válida.\n"
                "Entre em contato com o fornecedor."
            )
            return False
        
        try:
            # Obtém CNPJ do arquivo nome_device.json se existir
            cnpj_atual = self._obter_cnpj_configurado()
            if not cnpj_atual:
                # Se não houver CNPJ configurado, solicita ao usuário
                from PySide6.QtWidgets import QInputDialog
                cnpj_atual, ok = QInputDialog.getText(
                    None, "CNPJ Necessário",
                    "Digite o CNPJ da empresa (apenas números):"
                )
                if not ok or not cnpj_atual:
                    QMessageBox.warning(
                        None, "CNPJ Necessário",
                        "O CNPJ é necessário para validar a licença."
                    )
                    return False
                
                # Limpa CNPJ (apenas dígitos)
                cnpj_atual = ''.join(ch for ch in cnpj_atual if ch.isdigit())
            
            # Obtém Device ID (apenas informativo, não valida)
            device_id = obter_device_id()
            
            # Valida licença (offline + online se disponível)
            # IMPORTANTE: validar_device_id=False - valida apenas CNPJ
            resultado = validar_licenca_completa(
                caminho_key=caminho_licenca,
                cnpj_atual=cnpj_atual,
                device_id_atual=device_id,
                validar_online=True,  # Tenta validação online
                obrigar_online=False,  # Não obriga validação online (permite offline)
                validar_device_id=False  # NÃO valida device ID (apenas CNPJ)
            )
            
            # Exibe informações da licença
            info_msg = "✅ Licença Válida\n\n"
            info_msg += f"Cliente: {resultado.get('nome_cliente', 'N/A')}\n"
            info_msg += f"Servidor: {resultado.get('sql_servidor', 'N/A')}\n"
            info_msg += f"Banco: {resultado.get('sql_banco', 'N/A')}\n"
            
            validade = resultado.get('validade')
            if validade:
                info_msg += f"Validade: {validade}\n"
            else:
                info_msg += "Validade: Sem expiração\n"
            
            if resultado.get('validacao_online'):
                info_msg += "\nValidação online: ✓ Realizada"
            else:
                info_msg += "\nValidação online: ○ Não disponível (offline)"
            
            # Mostra mensagem informativa (opcional - pode comentar para não mostrar toda vez)
            # QMessageBox.information(None, "Licença Validada", info_msg)
            
            print(info_msg)  # Log no console
            return True
            
        except FileNotFoundError as e:
            QMessageBox.critical(
                None, "Arquivo Não Encontrado",
                f"Erro ao carregar licença:\n\n{str(e)}"
            )
            return False
            
        except ValueError as e:
            QMessageBox.critical(
                None, "Licença Inválida",
                f"A licença não é válida:\n\n{str(e)}\n\n"
                "Entre em contato com o fornecedor para obter uma licença válida."
            )
            return False
            
        except Exception as e:
            erro_msg = str(e)
            if "online" in erro_msg.lower():
                # Erro na validação online - permite continuar com offline
                QMessageBox.warning(
                    None, "Aviso de Validação",
                    f"Não foi possível validar online:\n\n{erro_msg}\n\n"
                    "Continuando com validação offline..."
                )
                return True
            else:
                QMessageBox.critical(
                    None, "Erro na Validação",
                    f"Erro ao validar licença:\n\n{erro_msg}"
                )
                return False
    
    def _obter_cnpj_configurado(self) -> str:
        """
        Obtém o CNPJ configurado do arquivo nome_device.json.
        
        Returns:
            CNPJ (apenas dígitos) ou string vazia se não encontrado
        """
        try:
            import json
            caminho_config = os.path.join(os.path.dirname(__file__), "nome_device.json")
            
            if os.path.exists(caminho_config):
                with open(caminho_config, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    cnpj = config.get('cnpj', '')
                    # Retorna apenas dígitos
                    return ''.join(ch for ch in str(cnpj) if ch.isdigit())
        except Exception:
            pass
        
        return ""
    
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
