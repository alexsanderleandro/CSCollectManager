"""
ai_client.py
============
Cliente fino de IA — traduz "analisar este texto" para o provedor configurado.

O SDK de cada provedor é importado só dentro do método correspondente: se o
SDK de um provedor não estiver instalado, apenas aquele provedor deixa de
funcionar (com mensagem clara), sem impedir o app de abrir.
"""

from typing import Optional

from services import ai_consumo
from services.ai_config_service import AIConfigService, NOMES_PROVEDOR
from utils.logger import get_logger

logger = get_logger(__name__)


class AIClientError(Exception):
    """Erro ao chamar o provedor de IA (SDK ausente, token inválido, falha de rede etc.).

    ``mensagem`` diz ao usuário o que aconteceu e ``orientacao`` o que ele pode
    fazer; ``detalhe`` guarda o erro técnico original, para o suporte.
    """

    def __init__(self, mensagem: str, orientacao: str = "", detalhe: str = ""):
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.orientacao = orientacao
        self.detalhe = detalhe

    def __str__(self) -> str:
        return f"{self.mensagem} {self.orientacao}".strip()


_CONFIGURACOES = "em Configurações (F12)"


def _nome_provedor(provider: str) -> str:
    """Nome do provedor já com a preposição: "da OpenAI", "do Google"."""
    nome = NOMES_PROVEDOR.get(provider, provider)
    return f"do {nome}" if provider == "google" else f"da {nome}"


def _cadeia(exc: BaseException):
    """O erro e os que o causaram (o SDK costuma embrulhar o erro de rede)."""
    vistos = set()
    while exc is not None and id(exc) not in vistos:
        vistos.add(id(exc))
        yield exc
        exc = exc.__cause__ or exc.__context__


def _status_http(exc: Exception) -> Optional[int]:
    # OpenAI e Anthropic: status_code; Google: code (na OpenAI, code é texto).
    for atributo in ("status_code", "code"):
        valor = getattr(exc, atributo, None)
        if isinstance(valor, int) and not isinstance(valor, bool):
            return valor
    return None


def _traduzir_erro(exc: Exception, provider: str, model: str) -> AIClientError:
    """Converte o erro cru do SDK numa mensagem que o usuário entende.

    Os três SDKs têm classes de erro diferentes, então a classificação usa o
    que todos expõem: o status HTTP e o texto do erro (que traz o código do
    provedor, ex.: ``expired_secret_key``, ``insufficient_quota``).
    """
    detalhe = f"{type(exc).__name__}: {exc}"
    logger.warning(f"IA ({provider}/{model}) falhou: {detalhe}")

    de = _nome_provedor(provider)
    status = _status_http(exc)
    texto = str(exc).lower()
    classes = [type(e).__name__.lower() for e in _cadeia(exc)]

    def erro(mensagem: str, orientacao: str) -> AIClientError:
        return AIClientError(mensagem, orientacao, detalhe)

    def contem(*trechos: str) -> bool:
        return any(t in texto for t in trechos)

    if any("timeout" in c for c in classes) or status in (408, 504) or contem("deadline_exceeded"):
        return erro(f"O serviço {de} demorou demais para responder.",
                    "Tente de novo em alguns minutos. Se continuar, verifique a internet desta máquina.")
    if status is None and any("connect" in c or "network" in c or "transport" in c for c in classes):
        return erro(f"Não foi possível conectar ao serviço {de}.",
                    "Verifique a conexão com a internet (ou se um firewall/proxy bloqueia o "
                    "acesso) e tente de novo.")
    if status in (None, 400, 401, 403) and "expired" in texto and "key" in texto:
        return erro(f"A chave de API {de} expirou.",
                    f"Gere uma nova chave no painel {de} e cadastre-a {_CONFIGURACOES}. "
                    "Depois, tente de novo.")
    if status == 401 or contem("invalid_api_key", "incorrect api key", "api_key_invalid",
                               "api key not valid", "invalid x-api-key", "authentication_error"):
        return erro(f"A chave de API {de} foi recusada (incorreta, revogada ou desativada).",
                    f"Confira a chave cadastrada {_CONFIGURACOES} ou gere uma nova no painel {de}.")
    # A cota estourada do Google (429) fala em "billing" mas é limite por
    # minuto/dia — vai para o caso do 429 logo abaixo.
    if status == 402 or contem("insufficient_quota", "credit balance", "billing_error") \
            or (status != 429 and "billing" in texto):
        return erro(f"A conta {de} está sem créditos ou atingiu o limite de gastos.",
                    f"Adicione créditos ou aumente o limite no painel de cobrança {de} e tente de novo.")
    if status == 429 or contem("rate_limit", "resource_exhausted"):
        return erro(f"O serviço {de} recusou a chamada por excesso de uso neste momento.",
                    "Aguarde um ou dois minutos e tente de novo. Se continuar, confira os "
                    f"limites e a cobrança da conta no painel {de}.")
    if status == 413 or contem("context_length", "maximum context", "too long", "too large",
                               "request_too_large", "exceeds the maximum"):
        return erro(f'Os dados desta análise são grandes demais para o modelo "{model}".',
                    f"Escolha {_CONFIGURACOES} um modelo que aceite textos maiores, ou analise "
                    "menos contagens de cada vez.")
    if status == 404 or contem("model_not_found", "not_found"):
        return erro(f'O modelo "{model}" não existe ou não está liberado para a sua chave {de}.',
                    f"Escolha outro modelo {_CONFIGURACOES}.")
    if status == 403 or contem("permission"):
        return erro(f'A chave de API {de} não tem permissão para usar o modelo "{model}".',
                    f"Escolha outro modelo {_CONFIGURACOES} ou verifique as permissões da chave "
                    f"no painel {de}.")
    if (status is not None and status >= 500) or contem("overloaded", "unavailable"):
        return erro(f"O serviço {de} está fora do ar ou sobrecarregado no momento.",
                    "Não é um problema desta máquina. Tente de novo em alguns minutos.")
    return erro(f"O serviço {de} recusou o pedido de análise.",
                f"Confira o modelo escolhido {_CONFIGURACOES} e tente de novo. Se continuar, "
                "envie ao suporte os detalhes técnicos deste erro.")


def _registrar_uso(provider: str, model: str, uso, campo_entrada: str, *campos_saida: str) -> None:
    """Soma o pedido ao gasto estimado, com os tokens que o provedor informa
    na própria resposta (o raciocínio do modelo é cobrado como saída)."""
    if uso is None:
        return
    saida = sum(getattr(uso, campo, 0) or 0 for campo in campos_saida)
    ai_consumo.registrar(provider, model, getattr(uso, campo_entrada, 0) or 0, saida)


def _sdk_ausente(provider: str, pacote: str) -> AIClientError:
    return AIClientError(
        f"O componente de acesso à IA {_nome_provedor(provider)} não está instalado.",
        f'Avise o suporte: falta o pacote "{pacote}" nesta instalação.',
        f"pip install {pacote}",
    )


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
                f"Nenhuma chave de API cadastrada para o provedor {NOMES_PROVEDOR.get(provider, provider)}.",
                f"Cadastre a chave {_CONFIGURACOES}.",
            )

        if provider == "anthropic":
            return self._analisar_anthropic(system, prompt, token, model)
        elif provider == "openai":
            return self._analisar_openai(system, prompt, token, model)
        elif provider == "google":
            return self._analisar_google(system, prompt, token, model)
        else:
            raise AIClientError(f"Provedor de IA desconhecido: {provider}.",
                                f"Escolha um provedor {_CONFIGURACOES}.")

    # ------------------------------------------------------------------
    # Adaptadores por provedor
    # ------------------------------------------------------------------

    def _analisar_anthropic(self, system: str, prompt: str, token: str, model: str) -> str:
        try:
            import anthropic
        except ImportError:
            raise _sdk_ausente("anthropic", "anthropic")

        try:
            client = anthropic.Anthropic(api_key=token)
            message = client.messages.create(
                model=model,
                max_tokens=16000,
                thinking={"type": "adaptive"},
                system=system,
                messages=[{"role": "user", "content": prompt}],
            )
            _registrar_uso("anthropic", model, message.usage, "input_tokens", "output_tokens")
            textos = [bloco.text for bloco in message.content if getattr(bloco, "type", "") == "text"]
            return "\n".join(textos).strip()
        except AIClientError:
            raise
        except Exception as exc:
            raise _traduzir_erro(exc, "anthropic", model) from exc

    def _analisar_openai(self, system: str, prompt: str, token: str, model: str) -> str:
        try:
            import openai
        except ImportError:
            raise _sdk_ausente("openai", "openai")

        try:
            client = openai.OpenAI(api_key=token)
            resposta = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
            )
            _registrar_uso("openai", model, resposta.usage, "prompt_tokens", "completion_tokens")
            return (resposta.choices[0].message.content or "").strip()
        except AIClientError:
            raise
        except Exception as exc:
            raise _traduzir_erro(exc, "openai", model) from exc

    def _analisar_google(self, system: str, prompt: str, token: str, model: str) -> str:
        try:
            from google import genai
        except ImportError:
            raise _sdk_ausente("google", "google-genai")

        try:
            client = genai.Client(api_key=token)
            resposta = client.models.generate_content(
                model=model,
                contents=prompt,
                config={"system_instruction": system},
            )
            _registrar_uso("google", model, resposta.usage_metadata, "prompt_token_count",
                           "candidates_token_count", "thoughts_token_count")
            return (resposta.text or "").strip()
        except AIClientError:
            raise
        except Exception as exc:
            raise _traduzir_erro(exc, "google", model) from exc

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
