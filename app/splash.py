"""
splash.py
=========
Splash animado da aplicação CSCollectManager.

Reimplementação em PySide6/Qt do design de referência descrito na documentação
(``assets/README.md`` + ``assets/splash_tkinter.py``): fundo em gradiente azul
diagonal, ícone central da marca com um anel orbital e um ponto branco girando,
título/subtítulo e três pontos pulsantes de carregamento. Exibe por alguns
segundos e então chama ``on_finish`` para prosseguir com o fluxo do app.

Fica no pacote ``app`` (leve) — e não em ``widgets`` (cujo ``__init__`` importa
toda a árvore de widgets/serviços) — para carregar cedo e rápido no boot.
"""

import math
import os
from typing import Callable, Optional

from PySide6.QtCore import Qt, QTimer, QRectF, QPointF
from PySide6.QtGui import (
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import QApplication, QWidget


class AnimatedSplash(QWidget):
    """
    Tela de splash animada (sem bordas, sempre no topo).

    Desenha um gradiente azul, o ícone da marca com um anel orbital girando,
    título e subtítulo e três pontos pulsantes. Após ``duration`` segundos,
    fecha-se e invoca ``on_finish``.
    """

    #: Altura de referência (splash a 60% em tela 1080p) para escalar elementos.
    _REF_HEIGHT = 648.0

    def __init__(
        self,
        on_finish: Optional[Callable[[], None]] = None,
        icon_path: Optional[str] = None,
        title: str = "CEOsoftware Sistemas",
        subtitle: str = "INVENTÁRIO INTELIGENTE",
        parent: Optional[QWidget] = None,
    ):
        """
        Args:
            on_finish: Callback chamado uma vez quando o splash termina.
            icon_path: Caminho do ícone PNG (idealmente quadrado, com fundo
                transparente). Se ausente/inválido, o ícone não é desenhado.
            title: Texto do título principal.
            subtitle: Texto do subtítulo.
            parent: Widget pai (normalmente ``None``).
        """
        super().__init__(parent)
        self.on_finish = on_finish
        self.title = title
        self.subtitle = subtitle

        self._angle = 0.0        # ângulo do ponto orbital (graus)
        self._finished = False   # guarda contra fim duplo

        # Carrega o ícone (opcional)
        self._icon: Optional[QPixmap] = None
        if icon_path and os.path.exists(icon_path):
            pm = QPixmap(icon_path)
            if not pm.isNull():
                self._icon = pm

        self._setup_window()

        # Timer de animação (~30 FPS)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_tick)

    def _setup_window(self):
        """Configura a janela sem bordas, translúcida e centralizada (60% da tela)."""
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        screen = QApplication.primaryScreen()
        geo = screen.availableGeometry() if screen else None
        if geo is not None:
            w = int(geo.width() * 0.6)
            h = int(geo.height() * 0.6)
            self.resize(w, h)
            self.move(
                geo.x() + (geo.width() - w) // 2,
                geo.y() + (geo.height() - h) // 2,
            )
        else:
            self.resize(760, 480)

        # Fator de escala relativo à altura de referência.
        self._scale = max(0.5, self.height() / self._REF_HEIGHT)

    # ------------------------------------------------------------------
    # Ciclo de vida
    # ------------------------------------------------------------------
    def start(self, duration: float = 3.0):
        """
        Exibe o splash, inicia a animação e agenda o fechamento.

        Args:
            duration: Tempo de exibição em segundos.
        """
        self._angle = 0.0
        self._finished = False
        self.show()
        self.raise_()
        self._timer.start(33)
        QTimer.singleShot(int(duration * 1000), self._finish)

    def _finish(self):
        """Para a animação, fecha o splash e chama ``on_finish`` (apenas uma vez)."""
        if self._finished:
            return
        self._finished = True
        self._timer.stop()
        self.close()
        if self.on_finish:
            self.on_finish()

    def _on_tick(self):
        """Avança a animação em um frame."""
        # ~360° a cada 100 frames (~3,3s) — ponto orbital em rotação suave.
        self._angle = (self._angle + 3.6) % 360.0
        self.update()

    # ------------------------------------------------------------------
    # Pintura
    # ------------------------------------------------------------------
    def paintEvent(self, event):
        """Desenha o splash completo (gradiente, anel, ícone, textos, pontos)."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        w = self.width()
        h = self.height()
        s = self._scale

        self._paint_gradient(painter, w, h)

        cx = w / 2.0
        cy = h * 0.35
        ring_r = 120.0 * s

        self._paint_ring(painter, cx, cy, ring_r, s)
        self._paint_icon(painter, cx, cy, s)
        self._paint_texts(painter, cx, cy, ring_r, w, s)
        self._paint_pulsing_dots(painter, cx, h, s)

        painter.end()

    def _paint_gradient(self, painter: QPainter, w: int, h: int):
        """Fundo em gradiente azul diagonal (135°), com cantos arredondados."""
        grad = QLinearGradient(0, 0, w, h)
        grad.setColorAt(0.0, QColor(62, 156, 247))   # #3e9cf7
        grad.setColorAt(0.4, QColor(29, 107, 176))   # #1d6bb0
        grad.setColorAt(1.0, QColor(14, 66, 176))    # #0e42b0

        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, w, h), 16.0, 16.0)
        painter.fillPath(path, grad)

    def _paint_ring(self, painter: QPainter, cx: float, cy: float, ring_r: float, s: float):
        """Anel orbital com um ponto branco girando."""
        painter.setPen(QPen(QColor(189, 219, 254), max(1.0, 3.0 * s)))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QPointF(cx, cy), ring_r, ring_r)

        a = math.radians(self._angle)
        dot_x = cx + ring_r * math.cos(a)
        dot_y = cy + ring_r * math.sin(a)
        dot_r = 8.0 * s
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(255, 255, 255))
        painter.drawEllipse(QPointF(dot_x, dot_y), dot_r, dot_r)

    def _paint_icon(self, painter: QPainter, cx: float, cy: float, s: float):
        """Ícone central da marca (se disponível)."""
        if self._icon is None:
            return
        icon_size = max(1, int(200 * s))
        pm = self._icon.scaledToWidth(
            icon_size, Qt.TransformationMode.SmoothTransformation
        )
        painter.drawPixmap(
            int(cx - pm.width() / 2.0),
            int(cy - pm.height() / 2.0),
            pm,
        )

    def _paint_texts(
        self, painter: QPainter, cx: float, cy: float, ring_r: float, w: int, s: float
    ):
        """Título e subtítulo centralizados abaixo do anel."""
        # Título
        painter.setPen(QColor(255, 255, 255))
        title_font = QFont("Segoe UI")
        title_font.setPixelSize(max(14, int(36 * s)))
        title_font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(title_font)
        title_y = cy + ring_r + 36 * s
        painter.drawText(
            QRectF(0, title_y, w, 60 * s),
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
            self.title,
        )

        # Subtítulo
        painter.setPen(QColor(160, 195, 235))  # #a0c3eb
        sub_font = QFont("Segoe UI")
        sub_font.setPixelSize(max(9, int(14 * s)))
        sub_font.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 130)
        painter.setFont(sub_font)
        sub_y = title_y + 52 * s
        painter.drawText(
            QRectF(0, sub_y, w, 40 * s),
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
            self.subtitle,
        )

    def _paint_pulsing_dots(self, painter: QPainter, cx: float, h: int, s: float):
        """Três pontos pulsantes na base (indicador de carregamento)."""
        painter.setPen(Qt.PenStyle.NoPen)
        dot_y = h - 60 * s
        spacing = 30 * s
        r = 6 * s
        phase_base = self._angle / 360.0  # 0..1 por ciclo de rotação
        for i, delay in enumerate((0.0, 0.33, 0.66)):
            phase = (phase_base + delay) % 1.0
            alpha = 0.25 + 0.75 * max(0.0, math.sin(math.pi * phase))
            color = QColor(220, 235, 255)
            color.setAlphaF(alpha)
            painter.setBrush(color)
            x = cx - spacing + i * spacing
            painter.drawEllipse(QPointF(x, dot_y), r, r)
