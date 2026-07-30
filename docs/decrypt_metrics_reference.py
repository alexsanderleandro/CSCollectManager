"""Script de referência para decifrar o arquivo `<nome>_metricas.enc` gerado
pelo LogScan mobile (CSCollect) e empacotado no zip de exportação de contagem.

NÃO está integrado ao CSCollectManager ainda — é só a implementação de
referência para quando essa leitura for construída na UI do Manager.

Uso:
    python decrypt_metrics_reference.py <caminho>_metricas.enc

Requer `pycryptodome` (mesma lib já usada em outras partes do ecossistema).

Esquema: envelope híbrido AES-256-GCM (dados) + RSA-OAEP-SHA256 (chave AES) —
ver `CSCollect/security/metrics_encryption.py` para o lado que gera o arquivo.
A chave privada usada aqui (`metrics_private_key.pem`, neste mesmo diretório)
é distinta da chave de assinatura do `.db` (ver `export_db_public_key.pem` em
CSCollectAPI/docs) — uma é para confidencialidade, a outra para autenticidade.
"""
import base64
import json
import sys
import os

from Crypto.PublicKey import RSA
from Crypto.Cipher import AES, PKCS1_OAEP
from Crypto.Hash import SHA256

_PRIVATE_KEY_PATH = os.path.join(os.path.dirname(__file__), 'metrics_private_key.pem')


def decifrar_metricas(caminho_enc, caminho_chave_privada=_PRIVATE_KEY_PATH):
    with open(caminho_enc, 'r', encoding='utf-8') as f:
        envelope = json.load(f)

    with open(caminho_chave_privada, 'r', encoding='utf-8') as f:
        chave_privada = RSA.import_key(f.read())

    chave_cifrada = base64.b64decode(envelope['chave_cifrada'])
    nonce = base64.b64decode(envelope['nonce'])
    tag = base64.b64decode(envelope['tag'])
    ciphertext = base64.b64decode(envelope['ciphertext'])

    cipher_rsa = PKCS1_OAEP.new(chave_privada, hashAlgo=SHA256)
    chave_aes = cipher_rsa.decrypt(chave_cifrada)

    cipher_aes = AES.new(chave_aes, AES.MODE_GCM, nonce=nonce)
    payload = cipher_aes.decrypt_and_verify(ciphertext, tag)  # levanta ValueError se adulterado

    return json.loads(payload.decode('utf-8'))


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Uso: python decrypt_metrics_reference.py <caminho>_metricas.enc')
        sys.exit(1)

    metricas = decifrar_metricas(sys.argv[1])
    print(json.dumps(metricas, indent=2, ensure_ascii=False))
