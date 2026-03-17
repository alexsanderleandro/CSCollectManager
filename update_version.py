from datetime import datetime
import re
import os

VERSION_FILE = "version.py"

def gerar_versao():
    hoje = datetime.now().strftime("%y.%m.%d")
    rev = 1

    if os.path.exists(VERSION_FILE):
        with open(VERSION_FILE, "r", encoding="utf-8") as f:
            conteudo = f.read()

        match = re.search(r'(\d{2}\.\d{2}\.\d{2}) rev\. (\d+)', conteudo)
        if match:
            data_antiga, rev_antigo = match.groups()

            if data_antiga == hoje:
                rev = int(rev_antigo) + 1
            else:
                rev = 1

    versao = f'{hoje} rev. {rev}'

    with open(VERSION_FILE, "w", encoding="utf-8") as f:
        f.write(f'VERSION = "{versao}"\n')

    print(f"Versão atualizada para: {versao}")

if __name__ == "__main__":
    gerar_versao()
