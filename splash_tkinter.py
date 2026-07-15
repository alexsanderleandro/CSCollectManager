# -*- coding: utf-8 -*-
"""
Splash desktop responsivo para CSCollect (Python/Tkinter).
Exibe a animação por ~3s, depois chama on_finish para abrir a janela principal.

Uso:

    root = tk.Tk()
    splash = SplashScreen(root, on_finish=lambda: open_main_window(root))
    splash.show(duration=3.0)  # exibe por 3 segundos
    root.mainloop()

ou standalone:

    python splash_tkinter.py
"""

import tkinter as tk
import tkinter.font as tkFont
from PIL import Image, ImageTk, ImageDraw
import math
import threading


class SplashScreen:
    def __init__(self, parent, on_finish=None, icon_path="assets/ceo-icon.png"):
        """
        Args:
            parent: tk.Tk() ou tk.Toplevel()
            on_finish: callback quando splash termina
            icon_path: caminho do ícone PNG (recomendado: 512x512, canto arredondado)
        """
        self.parent = parent
        self.on_finish = on_finish
        self.icon_path = icon_path
        self.is_running = False
        self.angle = 0

        # Configura janela toplevel (sem decoração)
        self.splash = tk.Toplevel(parent)
        self.splash.overrideredirect(True)  # sem decoração
        self.splash.attributes("-topmost", True)

        # Responsividade: dimensões baseadas em DPI
        dpi = self.splash.winfo_fpixels("1i")  # pixels por polegada
        self.scale = dpi / 96.0  # 96 DPI = padrão Windows

        # Tamanho do splash: 60% da tela
        screen_w = self.splash.winfo_screenwidth()
        screen_h = self.splash.winfo_screenheight()
        splash_w = int(screen_w * 0.6)
        splash_h = int(screen_h * 0.6)
        self.splash.geometry(f"{splash_w}x{splash_h}")

        # Centraliza
        x = (screen_w - splash_w) // 2
        y = (screen_h - splash_h) // 2
        self.splash.geometry(f"+{x}+{y}")

        # Canvas para renderização
        self.canvas = tk.Canvas(
            self.splash,
            bg="#0e42b0",
            highlightthickness=0,
            width=splash_w,
            height=splash_h,
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Cache de imagens do Tk (precisa manter referência)
        self._tk_images = {}

        # Timer para animação
        self._animation_job = None

    def show(self, duration=3.0):
        """Exibe o splash por `duration` segundos."""
        self.is_running = True
        self.angle = 0

        # Gradiente via canvas ou imagem
        self._draw_gradient()

        # Inicia loop de animação
        self._animate()

        # Agenda fechamento
        self.splash.after(int(duration * 1000), self.hide)

    def hide(self):
        """Fecha o splash e chama on_finish."""
        self.is_running = False
        if self._animation_job:
            self.splash.after_cancel(self._animation_job)
        self.splash.destroy()
        if self.on_finish:
            self.on_finish()

    def _draw_gradient(self):
        """Desenha fundo gradiente azul."""
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()

        if w <= 1:
            w = int(self.splash.geometry().split("x")[0])
        if h <= 1:
            h = int(self.splash.geometry().split("+")[0].split("x")[1])

        # Cria imagem gradiente em memória
        img = Image.new("RGB", (w, h), color=(14, 66, 176))  # #0e42b0
        draw = ImageDraw.Draw(img, "RGBA")

        # Gradiente 135deg: top-left (#3e9cf7) → bottom-right (#0e42b0)
        for y in range(h):
            for x in range(w):
                t = (x / w + y / h) / 2.0  # interpolação diagonal
                if t < 0.4:
                    r = int(62 + (29 - 62) * (t / 0.4))
                    g = int(156 + (107 - 156) * (t / 0.4))
                    b = int(247 + (176 - 247) * (t / 0.4))
                else:
                    t2 = (t - 0.4) / 0.6
                    r = int(29 + (14 - 29) * t2)
                    g = int(107 + (66 - 107) * t2)
                    b = int(176 + (176 - 176) * t2)
                draw.point((x, y), fill=(r, g, b, 255))

        # Converte para PhotoImage
        self._gradient_tk = ImageTk.PhotoImage(img)
        self.canvas.create_image(0, 0, image=self._gradient_tk, anchor="nw")

    def _animate(self):
        """Loop de animação (ícone, anel, pontos)."""
        if not self.is_running:
            return

        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()

        if w <= 1:
            w = int(self.splash.geometry().split("x")[0])
        if h <= 1:
            h = int(self.splash.geometry().split("+")[0].split("x")[1])

        # Atualiza ângulo do anel
        self.angle = (self.angle + 3.6) % 360  # 360° em ~100 frames / 3s

        # Centro
        cx, cy = w // 2, int(h * 0.35)

        # Desenha anel orbital
        ring_r = int(120 * self.scale)
        self.canvas.create_oval(
            cx - ring_r,
            cy - ring_r,
            cx + ring_r,
            cy + ring_r,
            outline=f"#{int(190*255/256):02x}{int(220*255/256):02x}{int(255*255/256):02x}",
            width=int(3 * self.scale),
        )

        # Ponto branco no anel
        a_rad = math.radians(self.angle)
        dot_x = cx + ring_r * math.cos(a_rad)
        dot_y = cy + ring_r * math.sin(a_rad)
        dot_sz = int(8 * self.scale)
        self.canvas.create_oval(
            dot_x - dot_sz,
            dot_y - dot_sz,
            dot_x + dot_sz,
            dot_y + dot_sz,
            fill="#ffffff",
            outline="",
        )

        # Carrega ícone (com cache)
        if "icon" not in self._tk_images:
            try:
                icon_img = Image.open(self.icon_path).convert("RGBA")
                icon_size = int(200 * self.scale)
                icon_img = icon_img.resize((icon_size, icon_size), Image.Resampling.LANCZOS)
                self._tk_images["icon"] = ImageTk.PhotoImage(icon_img)
            except Exception as e:
                print(f"Erro carregando ícone: {e}")
                return

        # Desenha ícone (sem animação pop por simplicidade; use PIL.Image com efeitos se precisar)
        self.canvas.create_image(cx, cy, image=self._tk_images["icon"], anchor="center")

        # Título
        title_font = tkFont.Font(family="Helvetica", size=int(36 * self.scale), weight="normal")
        self.canvas.create_text(
            cx,
            int(cy + ring_r + 80 * self.scale),
            text="CEOsoftware Sistemas",
            font=title_font,
            fill="#ffffff",
        )

        # Subtítulo
        subtitle_font = tkFont.Font(family="Helvetica", size=int(14 * self.scale), weight="normal")
        self.canvas.create_text(
            cx,
            int(cy + ring_r + 130 * self.scale),
            text="INVENTÁRIO INTELIGENTE",
            font=subtitle_font,
            fill="#a0c3eb",
        )

        # Pontos pulsantes (simplificado)
        dot_y_pos = int(h - 60 * self.scale)
        pulse_frame = (int(self.angle / 3.6) % 100) / 100.0
        for i, delay in enumerate([0, 0.33, 0.66]):
            alpha = 0.25 + 0.75 * max(0, math.sin(math.pi * ((pulse_frame + delay) % 1.0)))
            dot_color_alpha = int(220 * alpha)
            self.canvas.create_oval(
                cx - 30 + i * 30 - 6,
                dot_y_pos - 6,
                cx - 30 + i * 30 + 6,
                dot_y_pos + 6,
                fill=f"#{dot_color_alpha:02x}{int(250 * alpha):02x}{255:02x}",
                outline="",
            )

        # Próximo frame em ~33ms (30 FPS)
        self._animation_job = self.splash.after(33, self._animate)


if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()  # esconde janela principal até o splash fechar

    def open_main():
        root.deiconify()
        root.title("CEOsoftware Sistemas")
        root.geometry("1024x768")
        lbl = tk.Label(root, text="Bem-vindo ao CEOsoftware Sistemas!", font=("Helvetica", 24))
        lbl.pack(expand=True)

    splash = SplashScreen(root, on_finish=open_main)
    splash.show(duration=3.0)

    root.mainloop()
