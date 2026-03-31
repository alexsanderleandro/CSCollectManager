from PIL import Image
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "assets")
SRC = os.path.join(ASSETS, "logo.png")
DST = os.path.join(ASSETS, "icon.ico")

if not os.path.exists(SRC):
    print(f"Fonte não encontrada: {SRC}")
    sys.exit(1)

img = Image.open(SRC).convert("RGBA")
sizes = [256, 128, 64, 48, 32, 16]
try:
    img.save(DST, format="ICO", sizes=[(s, s) for s in sizes])
    print(f"Ícone gerado: {DST}")
except Exception as e:
    print("Falha ao gerar ícone:", e)
    sys.exit(2)
