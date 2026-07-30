"""Decriptação do envelope de métricas de produtividade gerado pelo CSCollect
(ver `CSCollect/security/metrics_encryption.py` — AES-256-GCM + RSA-OAEP-SHA256).

Só o LogScan Manager tem a chave privada correspondente à chave pública fixa
embutida em todo celular CSCollect — por isso ela vive aqui, embutida como
constante, mesmo padrão já usado do lado CSCollect para as chaves fixas do
app (`security/export_db_signing.py::_PRIVATE_KEY_PEM`). O par completo (essa
mesma chave privada + a pública) também está documentado, para referência,
em `docs/metrics_private_key.pem` / `docs/decrypt_metrics_reference.py`.

Usa `cryptography` (já é dependência do projeto) em vez de pycryptodome —
evita adicionar uma segunda biblioteca de criptografia só para isso. Único
ponto de atenção na portagem do esquema: `AESGCM.decrypt` desta lib espera a
tag de autenticação concatenada ao FINAL do ciphertext, diferente do
pycryptodome (que recebe a tag como argumento separado).
"""
import base64
import json

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_PRIVATE_KEY_PEM = b"""-----BEGIN RSA PRIVATE KEY-----
MIIEpAIBAAKCAQEApCmg4ibTvyDDVQpFvGnh8vpCAh7bjOzqI7LQSF74oLRkuKCJ
2eLG3Zk3sbVfpKnK/E/DMMvVio1AcS2bY/j+0JmiBs+XlY+Bpqj5YTUwwOqVAI/p
79Vc+Hc1j6O/vZjuoIie0BS0wvgZhc8q+oS6lviT4P8YkVGf6blNF+CXubhp5A97
T/q9EZ7kJd728are5/RI3qe/wd2vAQU5rBTJ2oRHz49l6OB9QpSnoe4Qyw3SP2+v
5uZMuHqRWLG/ZqGsPxzi1iLVAhbZc1XgDElBfSo2XqrvdBAugNYjTxl4xTGjgSo0
GPlwrgwkfwTJHjdG+sRx2EzkdpB/0dUcllbQUQIDAQABAoIBAACog+htk63e5PhJ
Xjd30g6U0zuEhxNDoW+NywuZPuRlE3N76FBEelE/PlO4TeyAUPaDSt2eREpQj+82
6bo5mxWizL1RKzL6iaBtlHIVIfo0uUQl75VqZ3uoaGFzBy+B+8X5b5qXFKpPT0nj
3Lt3BAkGMOXxxpX8QUNb3qZk0bLue9hW7d8huP2gejvrXo2V4iruDAJ9LBwXziQq
ihdNO7yYjjcISwxDLDOmQFKffQqSJmaUhmOCvJS48ErbE/wCemtETka3stJ+A6wg
WDlIXoRZEOBnZsDN7HJruCpP3lugQR1jHfN4//pRz5/dT40bQpQDJVku9mXxhtap
VapYigECgYEAtzN0GvldUVXZ/BtiyEDzConkwm9BJMgZfoXPFvy5s8wUC+wNl5CE
IO/K/+pqy9iRcdCgE8GsqydxWKHX2tZrZwFB/b7PqoayfeNI2h+/fRf0IkJXnoGm
dO+U/omuQIRU90T0bqaeExz1eQvNEQ15/NXt+g7q9rF0tgw+AUXez1ECgYEA5WVz
mHSPQekEZxDWj+gFzKzCGReCRc2lmZigG8byfUfALVpjAFaaf3wxy47xzDdC+EIS
fd8Lg1OQXwdDlQDDbh7UEw6AOPL3aqWWZ0GQf02MPClePoWKj4vQ1DXcN/l6Fs7W
lVdz+HiTNpVV6zVAS8lK2le2W3Q+3gFVCGLRsQECgYEAo4hdmvp/r2wIUsALdKBt
kzm2J03yg6fPAh7l1iowhmukdWP4WhQZreD/f2Q8gsxGQKevTRN0U6+4wRpvOZxv
cRoxUxVyAFGOoUsyq+rtHvgz6CT6W7Z15So8AN7b2iGGSteVrfQzZPJTuQKswg0a
mHRKow2P9jg/64WQD8jT9JECgYEA3gu2ufLRnH3+WflthzyTKIxtETa1TfYCfsvC
50BLBsOGHSBpxjEOOaqw1JYYLZGsTHxARAC7tzITBDkWzMtBYH2M0KlvqjBdF6kT
Df3j7aXVwYJVjHVdKxeuW0uLT883w44RHdvaEMA91070LMmN5A4DW5gdlybNl714
XrawvQECgYAQ+EdvXBuVH7M5O7jQZSIf+oCCx5bft5Ki4M8dUcfbL4UwOQDqvmIL
B1F8MMCnTsVEiyofDta2O45vLz0Mj4L0uaFkpydLSyc1gH8AfdNLfkYTiXn4rudP
yxjaXaUwNv2hRGReti2HTY0+8cRE+JYS1SLlzDNg/TxsJq9I8rcaKQ==
-----END RSA PRIVATE KEY-----"""

_private_key = None


def _get_private_key():
    global _private_key
    if _private_key is None:
        _private_key = serialization.load_pem_private_key(_PRIVATE_KEY_PEM, password=None)
    return _private_key


def decifrar_metricas(envelope: dict) -> dict:
    """Decifra o envelope de métricas (dict já parseado do JSON do `.enc`).

    Retorna o dict de métricas original. Levanta exceção se o envelope for
    inválido, a chave não bater, ou o conteúdo tiver sido adulterado (o GCM
    detecta isso na verificação da tag) — quem chama decide como tratar.
    """
    chave_cifrada = base64.b64decode(envelope['chave_cifrada'])
    nonce = base64.b64decode(envelope['nonce'])
    tag = base64.b64decode(envelope['tag'])
    ciphertext = base64.b64decode(envelope['ciphertext'])

    chave_aes = _get_private_key().decrypt(
        chave_cifrada,
        padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None),
    )

    payload = AESGCM(chave_aes).decrypt(nonce, ciphertext + tag, None)
    return json.loads(payload.decode('utf-8'))
