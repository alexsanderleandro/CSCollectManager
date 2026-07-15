# Splash Desktop — CSCollect

Splash animado responsivo para aplicativo desktop Python/Tkinter.

## Arquivos

```
seu_projeto/
├── splash_tkinter.py     ← módulo do splash
├── assets/
│   └── ceo-icon.png      ← ícone (512x512 recomendado, PNG com cantos arredondados)
└── main.py               ← seu app principal
```

## Uso básico

```python
import tkinter as tk
from splash_tkinter import SplashScreen

root = tk.Tk()
root.withdraw()  # esconde até o splash fechar

def abrir_app():
    root.deiconify()
    root.title("CSCollect")
    root.geometry("1024x768")

splash = SplashScreen(root, on_finish=abrir_app)
splash.show(duration=3.0)  # exibe por 3 segundos

root.mainloop()
```

## Customização rápida

| Parâmetro | Padrão | Função |
|---|---|---|
| `duration` | 3.0 | segundos de exibição |
| `icon_path` | `"assets/ceo-icon.png"` | caminho do ícone |

Edite dentro de `SplashScreen` (linhas 120-130):
- Cores do gradiente (RGB)
- Tamanho do ícone
- Textos ("CSCollect", "INVENTÁRIO INTELIGENTE")

## Dependências

```bash
pip install Pillow
```

## Responsividade

O splash escala automaticamente com:
- **DPI do monitor** (Tkinter detecta)
- **Tamanho da tela** (60% por padrão)
- **Fontes** via `tkFont`

Se quiser outro tamanho base, edite em `show()`:
```python
splash_w = int(screen_w * 0.6)  # mude 0.6 para outra fração
```

## Teste rápido

```bash
python splash_tkinter.py
```

Exibe o splash por 3s, depois abre janela de exemplo.
