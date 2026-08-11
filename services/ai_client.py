"""
ai_client.py
============
Cliente fino de IA — traduz "analisar este texto" para o provedor configurado.

O SDK de cada provedor é importado só dentro do método correspondente: se o
SDK de um provedor não estiver instalado, apenas aquele provedor deixa de
funcionar (com mensagem clara), sem impedir o app de abrir.
"""

from typing import Optional

from services.ai_config_service import AIConfigService


class AIClientError(Exception):
    """Erro ao chamar o provedor de IA (SDK ausente, token inválido, falha de rede etc.)."""
    pass


class AIClient:
    """Cliente de IA que delega ao provedor configurado em ``AIConfigService``."""

    def __init__(self, config_service: Optional[AIConfigService] = None):
        self._config = config_service or AIConfigService()

    def analisar(self, system: str, prompt: str) -> str:
        """
        Envia ``system``/``prompt`` ao provedor de IA configurado e retorna o texto de resposta.

        Args:
            system: Instrução de sistema (papel/contexto do assistente).
            prompt: Conteúdo a analisar.

        Returns:
            Texto da resposta do modelo.

        Raises:
            AIClientError: Se não houver provedor configurado, o SDK não
                estiver instalado, ou a chamada falhar.
        """
        provider = self._config.get_provider()
        token = self._config.get_token(provider)
        model = self._config.get_model(provider)

        if not token:
            raise AIClientError(
                f"Nenhum token configurado para o provedor '{provider}'. "
                "Configure em Configurações (F12)."
            )

        if provider == "anthropic":
            return self._analisar_anthropic(system, prompt, token, model)
        elif provider == "openai":
            return self._analisar_openai(system, prompt, token, model)
        elif provider == "google":
            return self._analisar_google(system, prompt, token, model)
        else:
            raise AIClientError(f"Provedor desconhecido: {provider}")

    # ------------------------------------------------------------------
    # Adaptadores por provedor
    # ------------------------------------------------------------------

    def _analisar_anthropic(self, system: str, prompt: str, token: str, model: str) -> str:
        try:
            import anthropic
        except ImportError:
            raise AIClientError(
                "SDK do provedor Anthropic não instalado. Execute: pip install anthropic"
            )

        try:
            client = anthropic.Anthropic(api_key=token)
            message = client.messages.create(
                model=model,
                max_tokens=16000,
                thinking={"type": "adaptive"},
                system=system,
                messages=[{"role": "user", "content": prompt}],
            )
            textos = [bloco.text for bloco in message.content if getattr(bloco, "type", "") == "text"]
            return "\n".join(textos).strip()
        except AIClientError:
            raise
        except Exception as exc:
            raise AIClientError(f"Falha ao chamar Anthropic: {exc}")

    def _analisar_openai(self, system: str, prompt: str, token: str, model: str) -> str:
        try:
            import openai
        except ImportError:
            raise AIClientError(
                "SDK do provedor OpenAI não instalado. Execute: pip install openai"
            )

        try:
            client = openai.OpenAI(api_key=token)
            resposta = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
            )
            return (resposta.choices[0].message.content or "").strip()
        except AIClientError:
            raise
        except Exception as exc:
            raise AIClientError(f"Falha ao chamar OpenAI: {exc}")

    def _analisar_google(self, system: str, prompt: str, token: str, model: str) -> str:
        try:
            from google import genai
        except ImportError:
            raise AIClientError(
                "SDK do provedor Google não instalado. Execute: pip install google-genai"
            )

        try:
            client = genai.Client(api_key=token)
            resposta = client.models.generate_content(
                model=model,
                contents=prompt,
                config={"system_instruction": system},
            )
            return (resposta.text or "").strip()
        except AIClientError:
            raise
        except Exception as exc:
            raise AIClientError(f"Falha ao chamar Google: {exc}")

    # ------------------------------------------------------------------
    # Teste de conexão (usado pelo botão "Testar conexão")
    # ------------------------------------------------------------------

    def testar_conexao(self) -> str:
        """
        Faz uma chamada mínima ao provedor configurado para validar o token.

        Returns:
            Texto curto de confirmação retornado pelo modelo.

        Raises:
            AIClientError: Se a chamada falhar.
        """
        return self.analisar(
            system="Responda apenas 'ok', sem mais nenhuma palavra.",
            prompt="teste de conexão",
        )
