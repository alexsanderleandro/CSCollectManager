"""
ai_consumo.py
=============
Gasto estimado com a IA, registrado a cada resposta: os tokens que o provedor
informa na própria resposta × o preço de tabela do modelo (``_MODELOS`` em
``ai_config_service``).

É uma estimativa local: conta só os pedidos feitos neste computador, com o
preço da tabela no momento do pedido. O saldo real fica no site do provedor —
nenhum dos três informa saldo pela API com a chave comum.

Persiste em ``ai_consumo.json`` (mesma pasta de ``ai_settings.json``), somado
por mês, provedor e modelo — o arquivo não cresce a cada pedido.
"""

import json
import os
import threading
from datetime import date, datetime
from typing import Any, Dict, NamedTuple, Optional

from services.ai_config_service import preco_modelo
from utils.config import AppConfig
from utils.logger import get_logger

logger = get_logger(__name__)

# As análises rodam em threads do QThreadPool: dois pedidos terminando juntos
# não podem ler e regravar o arquivo ao mesmo tempo.
_LOCK = threading.Lock()


class ResumoMes(NamedTuple):
    pedidos: int
    custo_usd: float
    sem_preco: int  # pedidos de modelo fora da tabela de preços (custo desconhecido)


def _caminho() -> str:
    return str(AppConfig.get_app_dir() / "ai_consumo.json")


def _ler() -> Dict[str, Any]:
    try:
        with open(_caminho(), "r", encoding="utf-8") as f:
            dados = json.load(f)
        return dados if isinstance(dados, dict) else {}
    except Exception:
        return {}


def _gravar(dados: Dict[str, Any]) -> None:
    caminho = _caminho()
    temporario = caminho + ".tmp"
    with open(temporario, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)
    os.replace(temporario, caminho)  # nunca deixa o arquivo pela metade


def registrar(provider: str, model: str, tokens_entrada: int, tokens_saida: int,
              quando: Optional[datetime] = None) -> None:
    """Soma um pedido à IA no mês corrente. Falha aqui nunca derruba a
    análise — só deixa de contar aquele pedido."""
    try:
        tokens_entrada = int(tokens_entrada or 0)
        tokens_saida = int(tokens_saida or 0)
        preco = preco_modelo(provider, model)
        mes = (quando or datetime.now()).strftime("%Y-%m")
        with _LOCK:
            dados = _ler()
            atual = (dados.setdefault(mes, {}).setdefault(provider, {})
                     .setdefault(model, {"pedidos": 0, "tokens_entrada": 0, "tokens_saida": 0,
                                         "custo_usd": 0.0, "sem_preco": 0}))
            atual["pedidos"] += 1
            atual["tokens_entrada"] += tokens_entrada
            atual["tokens_saida"] += tokens_saida
            if preco is None:
                atual["sem_preco"] += 1
            else:
                preco_entrada, preco_saida = preco
                atual["custo_usd"] = round(
                    atual["custo_usd"]
                    + (tokens_entrada * preco_entrada + tokens_saida * preco_saida) / 1_000_000, 6)
            _gravar(dados)
    except Exception as exc:
        logger.warning(f"Consumo da IA não registrado ({provider}/{model}): {exc}")


def resumo_mes(provider: str, mes: str) -> ResumoMes:
    """Pedidos e gasto estimado do provedor no mês (``"AAAA-MM"``)."""
    with _LOCK:
        modelos = (_ler().get(mes) or {}).get(provider) or {}
    pedidos = sem_preco = 0
    custo = 0.0
    for contadores in modelos.values():
        pedidos += int(contadores.get("pedidos", 0))
        sem_preco += int(contadores.get("sem_preco", 0))
        custo += float(contadores.get("custo_usd", 0.0))
    return ResumoMes(pedidos, custo, sem_preco)


def mes_atual_e_anterior(hoje: Optional[date] = None):
    """``("AAAA-MM" deste mês, "AAAA-MM" do mês passado)``."""
    hoje = hoje or date.today()
    anterior = date(hoje.year - 1, 12, 1) if hoje.month == 1 else date(hoje.year, hoje.month - 1, 1)
    return hoje.strftime("%Y-%m"), anterior.strftime("%Y-%m")


def formatar_usd(valor: float) -> str:
    """``US$ 1.234,56`` — e "menos de US$ 0,01" para frações de centavo, que
    são comuns aqui (um pedido curto custa milésimos de dólar)."""
    if 0 < valor < 0.005:
        return "menos de US$ 0,01"
    texto = f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"US$ {texto}"
