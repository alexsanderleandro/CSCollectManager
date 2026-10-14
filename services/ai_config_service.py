"""
ai_config_service.py
=====================
Configuração do provedor de IA (OpenAI / Anthropic / Google) usado na análise
de estoque. Persiste em ``ai_settings.json`` (mesma pasta de
``user_settings.json``), com o token de cada provedor cifrado.
"""

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from encryption import decrypt_field, encrypt_field, is_encrypted
from utils.config import AppConfig

PROVIDERS = ("openai", "anthropic", "google")

# Nome de cada provedor como aparece para o usuário.
NOMES_PROVEDOR = {"openai": "OpenAI", "anthropic": "Anthropic", "google": "Google"}

# Página de cobrança de cada provedor, onde fica o saldo: nenhum deles informa
# o saldo pela API com a chave comum, então a tela de Configurações abre esta.
URL_COBRANCA = {
    "openai": "https://platform.openai.com/settings/organization/billing/overview",
    "anthropic": "https://platform.claude.com/settings/billing",
    "google": "https://aistudio.google.com/billing",
}

# Modelos disponíveis por provedor, com nível de consumo relativo (para a
# barra de indicação na tela de Configurações) e preço de tabela em US$ por
# 1 milhão de tokens (entrada, saída), usado no gasto estimado. Revisar
# periodicamente contra o catálogo e os preços vigentes de cada provedor —
# mudam com frequência. Preços conferidos em 10/2026.
_MODELOS: Dict[str, List[Dict[str, Any]]] = {
    "anthropic": [
        {"id": "claude-haiku-4-5", "nome": "Claude Haiku 4.5", "consumo": "baixo", "preco": (1.00, 5.00)},
        {"id": "claude-sonnet-5", "nome": "Claude Sonnet 5", "consumo": "medio", "preco": (2.00, 10.00)},
        {"id": "claude-opus-5", "nome": "Claude Opus 5", "consumo": "alto", "preco": (5.00, 25.00)},
    ],
    "openai": [
        {"id": "gpt-5-mini", "nome": "GPT-5 Mini", "consumo": "baixo", "preco": (0.25, 2.00)},
        {"id": "gpt-5", "nome": "GPT-5", "consumo": "medio", "preco": (1.25, 10.00)},
        {"id": "gpt-5-pro", "nome": "GPT-5 Pro", "consumo": "alto", "preco": (15.00, 120.00)},
    ],
    "google": [
        {"id": "gemini-2.5-flash-lite", "nome": "Gemini 2.5 Flash-Lite", "consumo": "baixo", "preco": (0.10, 0.40)},
        {"id": "gemini-2.5-flash", "nome": "Gemini 2.5 Flash", "consumo": "medio", "preco": (0.30, 2.50)},
        {"id": "gemini-2.5-pro", "nome": "Gemini 2.5 Pro", "consumo": "alto", "preco": (1.25, 10.00)},
    ],
}


def preco_modelo(provider: str, model: str) -> Optional[Tuple[float, float]]:
    """Preço de tabela (US$ por 1 milhão de tokens de entrada, de saída) do
    modelo, ou ``None`` se ele não estiver na tabela."""
    for m in _MODELOS.get(provider, []):
        if m["id"] == model:
            return m["preco"]
    return None

_MODELO_PADRAO = {
    "openai": "gpt-5",
    "anthropic": "claude-opus-5",
    "google": "gemini-2.5-pro",
}


@dataclass
class ModeloInfo:
    id: str
    nome: str
    consumo: str  # "baixo" | "medio" | "alto"


class AIConfigService:
    """Serviço de leitura/escrita de ``ai_settings.json``."""

    def _settings_path(self) -> str:
        return str(AppConfig.get_app_dir() / "ai_settings.json")

    def _load(self) -> Dict[str, Any]:
        path = self._settings_path()
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}

        data.setdefault("provider", "anthropic")
        providers = data.setdefault("providers", {})
        for p in PROVIDERS:
            providers.setdefault(p, {"token": "", "model": _MODELO_PADRAO[p]})
        return data

    def _save(self, data: Dict[str, Any]) -> None:
        path = self._settings_path()
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Provedor ativo
    # ------------------------------------------------------------------

    def get_provider(self) -> str:
        """Retorna o provedor ativo (``openai``, ``anthropic`` ou ``google``)."""
        return self._load().get("provider", "anthropic")

    def set_provider(self, provider: str) -> None:
        """Define o provedor ativo, preservando os tokens/modelos já salvos."""
        if provider not in PROVIDERS:
            raise ValueError(f"Provedor inválido: {provider}")
        data = self._load()
        data["provider"] = provider
        self._save(data)

    # ------------------------------------------------------------------
    # Token (cifrado em disco)
    # ------------------------------------------------------------------

    def get_token(self, provider: Optional[str] = None) -> str:
        """Retorna o token descriptografado do provedor (ativo, se omitido)."""
        data = self._load()
        p = provider or data.get("provider", "anthropic")
        raw = (data.get("providers", {}).get(p, {}) or {}).get("token") or ""
        if not raw:
            return ""
        try:
            return (decrypt_field(raw) if is_encrypted(raw) else raw) or ""
        except ValueError:
            return ""

    def set_token(self, token: str, provider: Optional[str] = None) -> None:
        """Cifra e grava o token do provedor (ativo, se omitido)."""
        data = self._load()
        p = provider or data.get("provider", "anthropic")
        cifrado = encrypt_field(token) if token else ""
        data["providers"].setdefault(p, {})["token"] = cifrado
        self._save(data)

    # ------------------------------------------------------------------
    # Modelo
    # ------------------------------------------------------------------

    def get_model(self, provider: Optional[str] = None) -> str:
        """Retorna o modelo escolhido do provedor (ativo, se omitido)."""
        data = self._load()
        p = provider or data.get("provider", "anthropic")
        return (data.get("providers", {}).get(p, {}) or {}).get("model") or _MODELO_PADRAO.get(p, "")

    def set_model(self, model: str, provider: Optional[str] = None) -> None:
        """Grava o modelo escolhido do provedor (ativo, se omitido)."""
        data = self._load()
        p = provider or data.get("provider", "anthropic")
        data["providers"].setdefault(p, {})["model"] = model
        self._save(data)

    def list_models(self, provider: str) -> List[ModeloInfo]:
        """Modelos disponíveis do provedor, cada um com seu nível de consumo."""
        return [ModeloInfo(m["id"], m["nome"], m["consumo"]) for m in _MODELOS.get(provider, [])]

    # ------------------------------------------------------------------
    # Estado geral
    # ------------------------------------------------------------------

    def is_configured(self) -> bool:
        """Diz se o provedor ativo tem token e modelo definidos."""
        return bool(self.get_token()) and bool(self.get_model())
