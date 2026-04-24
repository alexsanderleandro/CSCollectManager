"""
api_service.py
==============
Serviço de comunicação com a API CSCollect.

Endpoint utilizado:
  POST {url}/upload
  Header: Authorization: <token>
  Body:   multipart/form-data  →  file=<arquivo.zip>

Referência: https://github.com/alexsanderleandro/CSCollectAPI
"""

import os
from typing import Optional, Tuple


class ApiService:
    """
    Serviço para envio de cargas (arquivos ZIP) para a API CSCollect.

    Utiliza ``requests`` para realizar requisições HTTP.
    """

    UPLOAD_PATH = "/upload"
    TIMEOUT = 60  # segundos

    def __init__(self, base_url: str, authorization: str):
        """
        Inicializa o serviço.

        Args:
            base_url:      URL base da API (ex.: https://cscollectapi.onrender.com)
            authorization: Token de autorização enviado no header ``Authorization``.
        """
        self._base_url = base_url.rstrip("/")
        self._authorization = authorization

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def upload_file(self, filepath: str, cnpj: Optional[str] = None, codvendedor: Optional[str] = None, idcelular: Optional[str] = None) -> Tuple[bool, str]:
        """
        Envia um arquivo ZIP para o endpoint ``/upload`` da API.

        Args:
            filepath: Caminho completo do arquivo a enviar.

        Returns:
            Tupla ``(sucesso, mensagem)``.
            - sucesso:  ``True`` se a resposta HTTP for 2xx.
            - mensagem: Mensagem de retorno da API ou descrição do erro.
        """
        try:
            import requests
        except ImportError:
            return False, "Biblioteca 'requests' não instalada. Execute: pip install requests"

        if not os.path.isfile(filepath):
            return False, f"Arquivo não encontrado: {filepath}"

        url = f"{self._base_url}{self.UPLOAD_PATH}"
        headers = {"Authorization": self._authorization}
        filename = os.path.basename(filepath)

        try:
            with open(filepath, "rb") as fh:
                # Monta payload multipart/form-data com campos adicionais
                data = {}
                if cnpj:
                    data["cnpj"] = cnpj
                if codvendedor:
                    data["codvendedor"] = codvendedor
                if idcelular:
                    data["idcelular"] = idcelular

                # Log de depuração: mostrar payload que será enviado
                try:
                    import logging
                    logger = logging.getLogger("ApiService")
                    logger.debug("Enviando POST %s", url)
                    logger.debug("Headers: %s", {k: (v[:8] + '...' if k.lower()=='authorization' and v else v) for k,v in headers.items()})
                    logger.debug("Form fields: %s", data)
                except Exception:
                    pass

                resp = requests.post(
                    url,
                    files={"file": (filename, fh)},
                    data=data if data else None,
                    headers=headers,
                    timeout=self.TIMEOUT,
                )

                # Log resposta bruta para diagnóstico
                try:
                    import logging
                    logger = logging.getLogger("ApiService")
                    logger.debug("API response status: %s", resp.status_code)
                    try:
                        logger.debug("API response json: %s", resp.json())
                    except Exception:
                        logger.debug("API response text: %s", resp.text[:1000])
                except Exception:
                    pass

            if resp.ok:
                try:
                    data = resp.json()
                    msg = f"Arquivo '{data.get('arquivo', filename)}' enviado com sucesso."
                except Exception:
                    msg = f"Arquivo enviado com sucesso. (HTTP {resp.status_code})"
                return True, msg

            # Erro HTTP
            try:
                detail = resp.json().get("detail", resp.text)
            except Exception:
                detail = resp.text or f"HTTP {resp.status_code}"
            return False, f"Erro da API ({resp.status_code}): {detail}"

        except requests.exceptions.ConnectionError:
            return False, "Não foi possível conectar à API. Verifique a URL e a conexão com a internet."
        except requests.exceptions.Timeout:
            return False, f"Tempo esgotado após {self.TIMEOUT}s. A API pode estar indisponível."
        except Exception as exc:
            return False, f"Erro inesperado ao enviar: {exc}"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def from_config() -> Optional["ApiService"]:
        """
        Cria uma instância a partir das configurações salvas em ``user_settings.json``.

        Returns:
            ``ApiService`` configurado, ou ``None`` se URL/token não estiverem definidos.
        """
        try:
            from utils.config import AppConfig
            url = AppConfig.get_api_url()
            token = AppConfig.get_api_authorization()
            if url and token:
                return ApiService(base_url=url, authorization=token)
        except Exception:
            pass
        return None
