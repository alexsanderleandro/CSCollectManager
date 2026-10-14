"""
ai_settings_page.py
====================
Página "Configurações" — seleção do provedor de IA, token de acesso e modelo,
usada pela análise de estoque.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
    QLabel, QLineEdit, QComboBox, QPushButton, QMessageBox
)
from PySide6.QtCore import Qt, QThreadPool, QUrl
from PySide6.QtGui import QCursor, QDesktopServices

from app.styles import themed_qss
from services import ai_consumo
from services.ai_config_service import AIConfigService, NOMES_PROVEDOR, PROVIDERS, URL_COBRANCA
from services.ai_client import AIClient, AIClientError
from utils.workers import WorkerSignals, TaskRunnable

_QSS_BOTAO_SECUNDARIO = """
    QPushButton {
        background-color: {{BG_HOVER}};
        color: {{FG_PRIMARY}};
        border: none;
        border-radius: 8px;
        padding: 8px 18px;
    }
    QPushButton:hover { background-color: {{BG_SELECTED}}; }
"""

_CONSUMO_BADGE = {
    "baixo": ("🟢 Consumo baixo", "{{SUCCESS}}"),
    "medio": ("🟠 Consumo médio", "{{WARNING}}"),
    "alto": ("🔴 Consumo alto", "{{ERROR}}"),
}


class AISettingsPage(QWidget):
    """Página de configuração do provedor de IA (F12)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._config = AIConfigService()
        self._setup_ui()
        self._load_from_config()

    def _setup_ui(self):
        from views.main_window_erp import ModuleHeader

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = ModuleHeader(
            "⚙️",
            "Configurações",
            "Provedor de inteligência artificial usado na análise de estoque",
        )
        layout.addWidget(header)

        content = QWidget()
        content.setStyleSheet(themed_qss("background-color: {{BG_PRIMARY}};"))
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(24, 20, 24, 16)
        content_layout.setSpacing(16)

        group = QGroupBox("🤖 Provedor de IA")
        group.setStyleSheet(themed_qss("""
            QGroupBox {
                color: {{FG_PRIMARY}};
                border: 1px solid {{BORDER}};
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 12px;
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
            }
        """))
        form = QFormLayout(group)
        form.setSpacing(14)
        form.setContentsMargins(18, 16, 18, 16)

        # Provedor
        self._cmb_provider = QComboBox()
        for provedor in PROVIDERS:
            self._cmb_provider.addItem(NOMES_PROVEDOR[provedor], provedor)
        self._cmb_provider.setMinimumHeight(36)
        self._cmb_provider.currentIndexChanged.connect(self._on_provider_changed)
        form.addRow("Provedor:", self._cmb_provider)

        # Token (com botão de revelar)
        token_row = QHBoxLayout()
        token_row.setSpacing(6)
        self._txt_token = QLineEdit()
        self._txt_token.setEchoMode(QLineEdit.EchoMode.Password)
        self._txt_token.setMinimumHeight(36)
        self._txt_token.setPlaceholderText("Cole aqui o token de API do provedor...")
        token_row.addWidget(self._txt_token)

        self._btn_reveal = QPushButton("👁")
        self._btn_reveal.setCheckable(True)
        self._btn_reveal.setFixedSize(36, 36)
        self._btn_reveal.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._btn_reveal.toggled.connect(self._on_reveal_toggled)
        token_row.addWidget(self._btn_reveal)
        form.addRow("Token:", token_row)

        lbl_hint = QLabel("O token fica gravado criptografado nesta máquina.")
        lbl_hint.setStyleSheet(themed_qss("color: {{FG_DISABLED}}; font-size: 9pt;"))
        form.addRow("", lbl_hint)

        # Modelo + indicador de consumo
        model_row = QHBoxLayout()
        model_row.setSpacing(10)
        self._cmb_model = QComboBox()
        self._cmb_model.setMinimumHeight(36)
        self._cmb_model.currentIndexChanged.connect(self._on_model_changed)
        model_row.addWidget(self._cmb_model, 1)

        self._lbl_consumo = QLabel("")
        self._lbl_consumo.setMinimumWidth(130)
        model_row.addWidget(self._lbl_consumo)
        form.addRow("Modelo:", model_row)

        lbl_model_hint = QLabel(
            "Modelos mais caros analisam melhor. Para conferência de estoque, "
            "o de consumo médio costuma bastar."
        )
        lbl_model_hint.setWordWrap(True)
        lbl_model_hint.setStyleSheet(themed_qss("color: {{FG_DISABLED}}; font-size: 9pt;"))
        form.addRow("", lbl_model_hint)

        # Gasto estimado + saldo no site do provedor
        gasto_row = QHBoxLayout()
        gasto_row.setSpacing(10)
        self._lbl_gasto = QLabel("")
        self._lbl_gasto.setWordWrap(True)
        self._lbl_gasto.setTextFormat(Qt.TextFormat.RichText)
        self._lbl_gasto.setStyleSheet(themed_qss("color: {{FG_PRIMARY}}; font-size: 10pt;"))
        gasto_row.addWidget(self._lbl_gasto, 1)

        self._btn_saldo = QPushButton("💳  Ver saldo no site")
        self._btn_saldo.setMinimumHeight(36)
        self._btn_saldo.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._btn_saldo.setStyleSheet(themed_qss(_QSS_BOTAO_SECUNDARIO))
        self._btn_saldo.clicked.connect(self._on_ver_saldo_clicked)
        gasto_row.addWidget(self._btn_saldo)
        form.addRow("Gasto estimado:", gasto_row)

        lbl_gasto_hint = QLabel(
            "Estimativa: tokens informados em cada resposta da IA × preço de tabela do modelo. "
            "Conta só os pedidos feitos neste computador — o saldo real está no site do provedor."
        )
        lbl_gasto_hint.setWordWrap(True)
        lbl_gasto_hint.setStyleSheet(themed_qss("color: {{FG_DISABLED}}; font-size: 9pt;"))
        form.addRow("", lbl_gasto_hint)

        # Botões
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        self._btn_test = QPushButton("Testar conexão")
        self._btn_test.setMinimumHeight(36)
        self._btn_test.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._btn_test.setStyleSheet(themed_qss(_QSS_BOTAO_SECUNDARIO))
        self._btn_test.clicked.connect(self._on_test_clicked)
        btn_row.addWidget(self._btn_test)

        self._btn_save = QPushButton("Salvar")
        self._btn_save.setMinimumHeight(36)
        self._btn_save.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._btn_save.setStyleSheet(themed_qss("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {{ACCENT}}, stop:1 #1d6bb0);
                color: white;
                border: none;
                border-radius: 8px;
                padding: 8px 22px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {{ACCENT_HOVER}}, stop:1 #2a7cc4);
            }
        """))
        self._btn_save.clicked.connect(self._on_save_clicked)
        btn_row.addWidget(self._btn_save)
        btn_row.addStretch()
        form.addRow("", btn_row)

        self._lbl_status = QLabel("")
        self._lbl_status.setWordWrap(True)
        self._lbl_status.setStyleSheet(themed_qss("font-size: 9pt;"))
        form.addRow("", self._lbl_status)

        content_layout.addWidget(group)
        content_layout.addStretch()
        layout.addWidget(content)

    # ------------------------------------------------------------------
    # Carregamento / persistência
    # ------------------------------------------------------------------

    def _load_from_config(self):
        provider = self._config.get_provider()
        idx = self._cmb_provider.findData(provider)
        if idx >= 0:
            self._cmb_provider.setCurrentIndex(idx)
        self._reload_provider_fields()

    def _reload_provider_fields(self):
        """Recarrega token e lista de modelos do provedor selecionado no combo."""
        provider = self._cmb_provider.currentData()

        self._txt_token.blockSignals(True)
        self._txt_token.setText(self._config.get_token(provider))
        self._txt_token.blockSignals(False)

        self._cmb_model.blockSignals(True)
        self._cmb_model.clear()
        modelos = self._config.list_models(provider)
        modelo_atual = self._config.get_model(provider)
        idx_atual = 0
        for i, m in enumerate(modelos):
            self._cmb_model.addItem(m.nome, (m.id, m.consumo))
            if m.id == modelo_atual:
                idx_atual = i
        self._cmb_model.blockSignals(False)
        self._cmb_model.setCurrentIndex(idx_atual)
        self._update_consumo_badge()
        self._atualizar_gasto()

    def _atualizar_gasto(self):
        """Gasto estimado do provedor do combo neste mês e no anterior."""
        provider = self._cmb_provider.currentData()
        nome = NOMES_PROVEDOR.get(provider, provider)
        mes, mes_anterior = ai_consumo.mes_atual_e_anterior()
        atual = ai_consumo.resumo_mes(provider, mes)
        anterior = ai_consumo.resumo_mes(provider, mes_anterior)

        if atual.pedidos:
            plural = "pedido" if atual.pedidos == 1 else "pedidos"
            texto = (f"<b>{ai_consumo.formatar_usd(atual.custo_usd)}</b> neste mês "
                     f"({atual.pedidos} {plural} à IA)")
        else:
            texto = "Nenhum pedido à IA neste mês"
        if anterior.pedidos:
            texto += f" &nbsp;·&nbsp; mês passado: {ai_consumo.formatar_usd(anterior.custo_usd)}"
        sem_preco = atual.sem_preco + anterior.sem_preco
        if sem_preco:
            texto += (f" &nbsp;·&nbsp; {sem_preco} pedido(s) de modelo sem preço na tabela, "
                      "fora da soma")
        self._lbl_gasto.setText(texto)

        url = URL_COBRANCA.get(provider, "")
        self._btn_saldo.setEnabled(bool(url))
        self._btn_saldo.setToolTip(
            f"Abre a página de cobrança da conta {nome}:\n{url}\n"
            "O saldo aparece depois de entrar na conta." if url else "")

    def _update_consumo_badge(self):
        data = self._cmb_model.currentData()
        if not data:
            self._lbl_consumo.setText("")
            return
        _, consumo = data
        texto, cor_token = _CONSUMO_BADGE.get(consumo, ("", "{{FG_DISABLED}}"))
        self._lbl_consumo.setText(texto)
        self._lbl_consumo.setStyleSheet(themed_qss(f"color: {cor_token}; font-weight: bold; font-size: 9pt;"))

    def _salvar_campos_atuais(self):
        """Persiste provedor, token e modelo atualmente exibidos na tela."""
        provider = self._cmb_provider.currentData()
        self._config.set_provider(provider)
        self._config.set_token(self._txt_token.text().strip(), provider)
        data = self._cmb_model.currentData()
        if data:
            self._config.set_model(data[0], provider)

    # ------------------------------------------------------------------
    # Eventos
    # ------------------------------------------------------------------

    def _on_provider_changed(self):
        self._reload_provider_fields()

    def _on_model_changed(self):
        self._update_consumo_badge()

    def showEvent(self, event):
        super().showEvent(event)
        # Pode ter havido análises desde a última vez que a tela apareceu.
        self._atualizar_gasto()

    def _on_ver_saldo_clicked(self):
        url = URL_COBRANCA.get(self._cmb_provider.currentData(), "")
        if url and not QDesktopServices.openUrl(QUrl(url)):
            QMessageBox.information(
                self, "Ver saldo no site",
                f"Não foi possível abrir o navegador. Acesse este endereço:\n\n{url}")

    def _on_reveal_toggled(self, checked: bool):
        self._txt_token.setEchoMode(
            QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
        )

    def _on_save_clicked(self):
        self._salvar_campos_atuais()
        QMessageBox.information(self, "Configurações", "Configuração da IA salva com sucesso.")

    def _on_test_clicked(self):
        if not self._txt_token.text().strip():
            self._lbl_status.setText("⚠️ Informe um token antes de testar.")
            self._lbl_status.setStyleSheet(themed_qss("color: {{WARNING}}; font-size: 9pt;"))
            return

        self._salvar_campos_atuais()

        self._btn_test.setEnabled(False)
        self._lbl_status.setText("🔄 Testando conexão...")
        self._lbl_status.setStyleSheet(themed_qss("color: {{FG_SECONDARY}}; font-size: 9pt;"))

        signals = WorkerSignals()
        signals.finished.connect(self._on_test_finished)
        signals.error.connect(self._on_test_error)
        runnable = TaskRunnable(AIClient().testar_conexao, signals=signals)
        QThreadPool.globalInstance().start(runnable)

    def _on_test_finished(self, resultado):
        self._btn_test.setEnabled(True)
        self._atualizar_gasto()
        self._lbl_status.setText("✅ Conexão validada com sucesso.")
        self._lbl_status.setStyleSheet(themed_qss("color: {{SUCCESS}}; font-size: 9pt;"))

    def _on_test_error(self, exc: Exception):
        self._btn_test.setEnabled(True)
        if isinstance(exc, AIClientError):
            mensagem = f"{exc.mensagem}\n{exc.orientacao}".strip()
        else:
            mensagem = f"Erro inesperado: {exc}"
        self._lbl_status.setText(f"❌ {mensagem}")
        self._lbl_status.setStyleSheet(themed_qss("color: {{ERROR}}; font-size: 9pt;"))
