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
from typing import Any, Dict, List, Optional

from encryption import decrypt_field, encrypt_field, is_encrypted
from utils.config import AppConfig

PROVIDERS = ("openai", "anthropic", "google")

# Modelos disponíveis por provedor, com nível de consumo relativo (para a
# barra de indicação na tela de Configurações). Revisar periodicamente
# contra o catálogo vigente de cada provedor — muda com frequência.
_MODELOS: Dict[str, List[Dict[str, str]]] = {
    "anthropic": [
        {"id": "claude-haiku-4-5", "nome": "Claude Haiku 4.5", "consumo": "baixo"},
        {"id": "claude-sonnet-5", "nome": "Claude Sonnet 5", "consumo": "medio"},
        {"id": "claude-opus-5", "nome": "Claude Opus 5", "consumo": "alto"},
    ],
    "openai": [
        {"id": "gpt-5-mini", "nome": "GPT-5 Mini", "consumo": "baixo"},
        {"id": "gpt-5", "nome": "GPT-5", "consumo": "medio"},
        {"id": "gpt-5-pro", "nome": "GPT-5 Pro", "consumo": "alto"},
    ],
    "google": [
        {"id": "gemini-2.5-flash-lite", "nome": "Gemini 2.5 Flash-Lite", "consumo": "baixo"},
        {"id": "gemini-2.5-flash", "nome": "Gemini 2.5 Flash", "consumo": "medio"},
        {"id": "gemini-2.5-pro", "nome": "Gemini 2.5 Pro", "consumo": "alto"},
    ],
}

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
        return [ModeloInfo(**m) for m in _MODELOS.get(provider, [])]

    # ------------------------------------------------------------------
    # Estado geral
    # ------------------------------------------------------------------

    def is_configured(self) -> bool:
        """Diz se o provedor ativo tem token e modelo definidos."""
        return bool(self.get_token()) and bool(self.get_model())
