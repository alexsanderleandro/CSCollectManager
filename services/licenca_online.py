"""
licenca_online.py
==================
Verificação de licença online contra o CSCollectAPI (Neon, tabela `clientes`),
substituindo a verificação HMAC local que existia em `cscollectmanager_verify.py`.

Fluxo:
- `sincronizar_licenca()`: no máximo uma vez por dia (mesma regra do app
  mobile, para manter consistência), consulta `GET /licenca/{cnpj}` no
  CSCollectAPI. Se responder, atualiza `validade`/`tipo_licenca` no `.key`
  local (únicos campos regravados — o restante do arquivo, incluindo dados
  de conexão com o ERP, não é tocado). Se já verificou hoje, ou se a rede
  falhar, usa o `.key` local como fallback — nesse segundo caso, só dentro
  de uma janela de tolerância offline (`OFFLINE_TOLERANCIA_DIAS`), rastreada
  via `AppConfig.get/set_ultima_verificacao_licenca_online`.
- `iniciar_verificacao_background()`: repete a checagem periodicamente com o
  app aberto (na prática, por causa do limite de uma vez por dia, só bate
  rede de fato na primeira chamada do dia — as demais são leitura local
  instantânea), bloqueando a sessão na hora se a licença cair (`ativo=False`
  no Neon) ou expirar. Roda sempre em thread separada — mesmo a checagem
  "só uma vez por dia" pode, na única vez que bate rede, levar até
  `TIMEOUT_SEGUNDOS`, e isso nunca deve travar a UI.

Licença bloqueada/expirada é representada localmente escrevendo `validade`
com uma data já vencida — reaproveita o bloqueio por expiração que já existe
em `views/login_dialog.py`, sem precisar de um campo novo no `.key`.
"""

import json
from datetime import date, datetime, timedelta
from typing import Any, Dict, Optional

import requests

from encryption import decrypt_field, is_encrypted
from utils.config import AppConfig
from utils.logger import get_logger

logger = get_logger(__name__)

OFFLINE_TOLERANCIA_DIAS = 4
TIMEOUT_SEGUNDOS = 60
INTERVALO_BACKGROUND_MIN = 30


def _ler_key_local(caminho_key: str) -> Dict[str, Any]:
    """Lê o .key (JSON puro) e descriptografa os campos sensíveis já criptografados."""
    conteudo = None
    for enc in ('utf-8-sig', 'utf-8', 'latin-1', 'cp1252'):
        try:
            with open(caminho_key, 'r', encoding=enc) as f:
                conteudo = f.read().strip()
            break
        except (UnicodeDecodeError, LookupError):
            continue
    if conteudo is None:
        raise ValueError(f"Não foi possível decodificar o arquivo de licença: {caminho_key}")

    data = json.loads(conteudo)
    payload = dict(data)
    for campo in ('api_authorization', 'api_database_url', 'database_url'):
        val = data.get(campo) or ''
        payload[campo] = decrypt_field(val) if is_encrypted(val) else val
    return payload


def _gravar_validade_tipo_licenca(caminho_key: str, validade: Optional[str], tipo_licenca: str) -> None:
    """Regrava só `validade`/`tipo_licenca` no .key, preservando os demais campos."""
    with open(caminho_key, 'r', encoding='utf-8-sig') as f:
        data = json.load(f)
    data['validade'] = validade
    if tipo_licenca:
        data['tipo_licenca'] = tipo_licenca
    with open(caminho_key, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _data_vencida_ontem() -> str:
    return (date.today() - timedelta(days=1)).isoformat()


def _ja_verificou_online_hoje() -> bool:
    """Diz se já houve uma verificação online bem-sucedida hoje — mesma regra
    do app mobile (no máximo uma verificação online por dia)."""
    ultima = AppConfig.get_ultima_verificacao_licenca_online()
    if not ultima:
        return False
    try:
        return datetime.fromisoformat(ultima).date() == date.today()
    except Exception:
        return False


def consultar_licenca_online(
    cnpj: str, api_url: str, api_authorization: str, timeout: int = TIMEOUT_SEGUNDOS
) -> Optional[Dict[str, Any]]:
    """Consulta ``GET {api_url}/licenca/{cnpj}``.

    Retorna o JSON da resposta em caso de sucesso (200), ou ``None`` para
    qualquer falha (rede, timeout, status diferente de 200) — o chamador
    decide o fallback, sem exceções propagadas.
    """
    if not api_url or not cnpj:
        return None
    url = f"{api_url.rstrip('/')}/licenca/{cnpj}"
    try:
        resp = requests.get(url, headers={"Authorization": api_authorization}, timeout=timeout)
        if resp.status_code != 200:
            logger.warning(f"[licenca_online] GET /licenca/{cnpj} retornou {resp.status_code}")
            return None
        return resp.json()
    except requests.RequestException as e:
        logger.warning(f"[licenca_online] Falha ao consultar licença online: {e}")
        return None


def sincronizar_licenca(caminho_key: Optional[str] = None) -> Dict[str, Any]:
    """Sincroniza o `.key` local com o Neon (via CSCollectAPI) e retorna o
    payload efetivo a ser usado pelo app, no mesmo formato que
    `cscollectmanager_verify.load_and_verify_file()` retornava (`validade`,
    `tipo_licenca`, `sql_servidor`, `sql_banco`, `cnpjs`, `nome_cliente`,
    `api_authorization`, `api_database_url`, `api_url`, ...).
    """
    if not caminho_key:
        caminho_key = AppConfig._find_key_file()
    if not caminho_key:
        raise FileNotFoundError("Nenhum arquivo .key encontrado.")

    payload = _ler_key_local(caminho_key)

    if _ja_verificou_online_hoje() and not _licenca_bloqueada(payload):
        # Já verificou online hoje e a licença local está válida — mesma
        # regra do app mobile: no máximo uma verificação online por dia. Usa
        # o .key local direto, sem rede.
        #
        # Exceção: se o .key local está marcando bloqueio/expiração, o limite
        # de 1x/dia é ignorado e tenta online de novo a cada carregamento —
        # senão o cliente ficaria preso no bloqueio até o dia seguinte, mesmo
        # que o suporte já tenha corrigido a licença no Neon.
        return payload

    cnpjs = payload.get('cnpjs') or []
    cnpj = (cnpjs[0] if cnpjs else '').strip()

    api_url = (payload.get('api_url') or '').strip()
    api_authorization = (payload.get('api_authorization') or '').strip()

    resposta = consultar_licenca_online(cnpj, api_url, api_authorization) if cnpj else None

    if resposta is not None:
        ativo = bool(resposta.get('ativo', True))
        validade_online = resposta.get('validade')
        tipo_online = str(resposta.get('tipo_licenca') or payload.get('tipo_licenca') or '').strip()

        validade_efetiva = validade_online if ativo else _data_vencida_ontem()

        if validade_efetiva != payload.get('validade') or tipo_online != payload.get('tipo_licenca'):
            try:
                _gravar_validade_tipo_licenca(caminho_key, validade_efetiva, tipo_online)
            except Exception as e:
                logger.error(f"[licenca_online] Falha ao regravar .key: {e}")

        payload['validade'] = validade_efetiva
        payload['tipo_licenca'] = tipo_online
        AppConfig.set_ultima_verificacao_licenca_online(datetime.now().isoformat())
        return payload

    # Sem resposta online — aplica a tolerância offline.
    ultima = AppConfig.get_ultima_verificacao_licenca_online()
    dentro_da_tolerancia = False
    if ultima:
        try:
            dentro_da_tolerancia = (datetime.now() - datetime.fromisoformat(ultima)) <= timedelta(days=OFFLINE_TOLERANCIA_DIAS)
        except Exception:
            dentro_da_tolerancia = False

    if not dentro_da_tolerancia:
        logger.warning("[licenca_online] Sem verificação online dentro da tolerância — bloqueando por segurança.")
        payload['validade'] = _data_vencida_ontem()

    return payload


def _licenca_bloqueada(payload: Dict[str, Any]) -> bool:
    """Diz se `payload` representa uma licença expirada/bloqueada (mesma
    checagem de data usada em `login_dialog.py`)."""
    validade = (payload.get('validade') or '').strip()
    if not validade:
        return False
    try:
        if 'T' in validade or validade.endswith('Z'):
            from datetime import timezone
            v = validade.replace('Z', '+00:00')
            dt = datetime.fromisoformat(v)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt < datetime.now(timezone.utc)
        return date.fromisoformat(validade[:10]) < date.today()
    except Exception:
        return False


def iniciar_verificacao_background(main_window, intervalo_min: int = INTERVALO_BACKGROUND_MIN):
    """Inicia um QTimer que reconsulta a licença periodicamente enquanto o
    app está aberto, bloqueando a sessão imediatamente (via
    ``main_window._bloquear_sessao_por_licenca``) se o status cair para
    bloqueado/expirado.

    A checagem em si roda numa QThread separada — mesmo com o limite de uma
    verificação online por dia, a única chamada do dia que bate rede pode
    levar até ``TIMEOUT_SEGUNDOS``, e isso nunca deve travar a UI.
    """
    from PySide6.QtCore import QThread, QTimer, Signal

    class _VerificacaoWorker(QThread):
        resultado = Signal(object)  # payload (dict) ou None em caso de erro

        def run(self):
            try:
                self.resultado.emit(sincronizar_licenca())
            except Exception as e:
                logger.error(f"[licenca_online] Falha na verificação em background: {e}")
                self.resultado.emit(None)

    timer = QTimer(main_window)

    def _tratar_resultado(payload):
        if payload and _licenca_bloqueada(payload):
            main_window._bloquear_sessao_por_licenca(
                "Sua licença foi bloqueada ou expirou.\n\n"
                "Entre em contato com o setor comercial da CEOsoftware."
            )

    def _checar():
        worker = _VerificacaoWorker(main_window)
        worker.resultado.connect(_tratar_resultado)
        # Mantém a referência viva até o worker terminar sozinho.
        main_window._licenca_online_worker = worker
        worker.start()

    timer.timeout.connect(_checar)
    timer.start(intervalo_min * 60_000)
    # Mantém a referência viva (um QTimer sem "dono" python pode ser coletado
    # pelo GC mesmo com parent Qt definido).
    main_window._licenca_online_timer = timer
    return timer
