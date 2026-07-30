"""Lê os resumos de métricas de produtividade (`_metricas.enc`) presentes
dentro dos zips de contagem já baixados — mesma pasta usada pela tela
"Download Contagens" (`AppConfig.get_last_contagens_dir()`).
"""
import glob
import json
import os
import zipfile

from utils.metrics_decryption import decifrar_metricas


def listar_exports_com_metricas(pasta: str) -> list:
    """Varre `pasta` por `*.zip` e tenta ler+decifrar o `_metricas.enc` de cada um.

    Retorna uma lista de dicts, um por zip que contém `_metricas.enc`:
        {'arquivo_zip': <nome>, 'caminho_zip': <path completo>,
         'ok': bool, 'erro': str (se ok=False), 'metricas': dict (se ok=True)}

    Zips sem `_metricas.enc` não entram na lista. Um `.enc` corrompido/
    adulterado não impede os demais zips de aparecerem — cada um é isolado.
    """
    resultados = []
    if not pasta or not os.path.isdir(pasta):
        return resultados

    for zip_path in sorted(glob.glob(os.path.join(pasta, '*.zip'))):
        nome_zip = os.path.basename(zip_path)
        try:
            with zipfile.ZipFile(zip_path, 'r') as zf:
                enc_names = [n for n in zf.namelist() if n.endswith('_metricas.enc')]
                if not enc_names:
                    continue
                with zf.open(enc_names[0]) as f:
                    envelope = json.loads(f.read().decode('utf-8'))
        except Exception as e:
            resultados.append({
                'arquivo_zip': nome_zip, 'caminho_zip': zip_path,
                'ok': False, 'erro': f'Erro ao ler o zip: {e}',
            })
            continue

        try:
            metricas = decifrar_metricas(envelope)
            resultados.append({
                'arquivo_zip': nome_zip, 'caminho_zip': zip_path,
                'ok': True, 'metricas': metricas,
            })
        except Exception as e:
            resultados.append({
                'arquivo_zip': nome_zip, 'caminho_zip': zip_path,
                'ok': False, 'erro': f'Não foi possível decifrar: {e}',
            })

    return resultados
