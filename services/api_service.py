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

        # Log de diagnóstico: mostra prefixo/sufixo do token para comparar com API_TOKEN do servidor
        try:
            import logging
            _log = logging.getLogger("CSCollect.services.api_service")
            _tok = self._authorization or ""
            _tok_repr = (
                f"{_tok[:20]}...{_tok[-10:]}" if len(_tok) > 32
                else (_tok[:8] + "..." if len(_tok) > 8 else f"(vazio ou muito curto: {len(_tok)} chars)")
            )
            _log.warning(
                "Token sendo enviado para API → comprimento=%d | valor='%s' | url='%s'",
                len(_tok), _tok_repr, url,
            )
        except Exception:
            pass

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
                    _rlog = logging.getLogger("CSCollect.services.api_service")
                    _rlog.warning("API response status: %s", resp.status_code)
                    try:
                        _rlog.warning("API response body: %s", resp.json())
                    except Exception:
                        _rlog.warning("API response text: %s", resp.text[:2000])
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

    def check_existing(
        self,
        cnpj: str,
        codvendedor: str,
        idcelular: str,
        database_url: str = "",
    ) -> "Tuple[bool, Optional[dict], Optional[str]]":
        """
        Verifica se já existe uma carga registrada para cnpj + codvendedor + idcelular.

        Estratégia:
          1. Se ``database_url`` for informado → consulta direta ao banco Neon (mais confiável).
          2. Caso contrário → tenta ``GET /cargas`` na API HTTP.

        Returns:
            (encontrado, registro_ou_None, erro_ou_None)
        """
        if database_url:
            return self._check_existing_db(cnpj, codvendedor, idcelular, database_url)
        return self._check_existing_http(cnpj, codvendedor, idcelular)

    def _check_existing_db(
        self, cnpj: str, codvendedor: str, idcelular: str, database_url: str
    ) -> "Tuple[bool, Optional[dict], Optional[str]]":
        """Verifica duplicata consultando diretamente o banco PostgreSQL (Neon)."""
        try:
            import psycopg2
            import psycopg2.extras
        except ImportError:
            # fallback para psycopg (v3)
            try:
                import psycopg as psycopg2  # type: ignore
                import psycopg.rows  # type: ignore
            except ImportError:
                return False, None, "Driver psycopg2/psycopg não instalado."

        try:
            conn = psycopg2.connect(database_url)
            cur = conn.cursor(cursor_factory=getattr(psycopg2.extras, 'RealDictCursor', None))
            cur.execute(
                """
                SELECT id, nome_arquivo, cnpj, codvendedor, idcelular, data_envio
                  FROM cargas
                 WHERE cnpj = %s AND codvendedor = %s AND idcelular = %s
                 ORDER BY data_envio DESC
                 LIMIT 1
                """,
                (cnpj, codvendedor, idcelular),
            )
            row = cur.fetchone()
            cur.close()
            conn.close()
            if row:
                rec = dict(row) if hasattr(row, 'keys') else {
                    'id': row[0], 'nome_arquivo': row[1], 'cnpj': row[2],
                    'codvendedor': row[3], 'idcelular': row[4], 'data_envio': str(row[5]) if row[5] else '',
                }
                return True, rec, None
            return False, None, None
        except Exception as exc:
            return False, None, f"Erro ao consultar banco: {exc}"

    def _check_existing_http(
        self, cnpj: str, codvendedor: str, idcelular: str
    ) -> "Tuple[bool, Optional[dict], Optional[str]]":
        """Verifica duplicata via GET /cargas na API HTTP (fallback)."""
        try:
            import requests
        except ImportError:
            return False, None, "Biblioteca 'requests' não instalada."

        url = f"{self._base_url}/cargas"
        params: dict = {}
        if cnpj:
            params["cnpj"] = cnpj
        if codvendedor:
            params["codvendedor"] = codvendedor
        if idcelular:
            params["idcelular"] = idcelular

        headers = {"Authorization": self._authorization}
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=self.TIMEOUT)
            if resp.ok:
                body = resp.json()
                if isinstance(body, list):
                    items = body
                elif isinstance(body, dict):
                    items = body.get("items") or body.get("cargas") or []
                else:
                    items = []
                if items:
                    return True, items[0], None
                return False, None, None
            return False, None, f"HTTP {resp.status_code}: {resp.text[:300]}"
        except Exception as exc:
            return False, None, str(exc)

    def delete_carga(self, carga_id, database_url: str = "") -> "Tuple[bool, str]":
        """
        Remove uma carga pelo seu ID.

        Se ``database_url`` for informado → DELETE direto no banco.
        Caso contrário → DELETE /cargas/{id} via HTTP.

        Returns:
            (sucesso, mensagem)
        """
        if database_url:
            return self._delete_carga_db(carga_id, database_url)
        return self._delete_carga_http(carga_id)

    def _delete_carga_db(self, carga_id, database_url: str) -> "Tuple[bool, str]":
        """Remove carga diretamente no banco PostgreSQL (Neon)."""
        try:
            import psycopg2
        except ImportError:
            try:
                import psycopg as psycopg2  # type: ignore
            except ImportError:
                return False, "Driver psycopg2/psycopg não instalado."
        try:
            conn = psycopg2.connect(database_url)
            cur = conn.cursor()
            cur.execute("DELETE FROM cargas WHERE id = %s", (carga_id,))
            conn.commit()
            cur.close()
            conn.close()
            return True, "Registro anterior removido com sucesso."
        except Exception as exc:
            return False, f"Erro ao remover do banco: {exc}"

    def _delete_carga_http(self, carga_id) -> "Tuple[bool, str]":
        """Remove carga via DELETE /cargas/{id} na API HTTP."""
        try:
            import requests
        except ImportError:
            return False, "Biblioteca 'requests' não instalada."

        url = f"{self._base_url}/cargas/{carga_id}"
        headers = {"Authorization": self._authorization}
        try:
            resp = requests.delete(url, headers=headers, timeout=self.TIMEOUT)
            if resp.ok:
                return True, "Registro anterior removido com sucesso."
            return False, f"Erro ao remover registro ({resp.status_code}): {resp.text[:300]}"
        except Exception as exc:
            return False, str(exc)

    def delete_contagem(self, contagem_id, database_url: str = "") -> "Tuple[bool, str]":
        """
        Remove uma contagem pelo seu ID.

        Se ``database_url`` for informado → DELETE direto no banco.
        Caso contrário → DELETE /contagens/{id} via HTTP.

        Returns:
            (sucesso, mensagem)
        """
        if database_url:
            return self._delete_contagem_db(contagem_id, database_url)
        return self._delete_contagem_http(contagem_id)

    def _delete_contagem_db(self, contagem_id, database_url: str) -> "Tuple[bool, str]":
        """Remove contagem diretamente no banco PostgreSQL (Neon)."""
        try:
            import psycopg2
        except ImportError:
            try:
                import psycopg as psycopg2  # type: ignore
            except ImportError:
                return False, "Driver psycopg2/psycopg não instalado."
        try:
            conn = psycopg2.connect(database_url)
            cur = conn.cursor()
            cur.execute("DELETE FROM contagens WHERE id = %s", (contagem_id,))
            conn.commit()
            cur.close()
            conn.close()
            return True, "Registro removido com sucesso."
        except Exception as exc:
            return False, f"Erro ao remover do banco: {exc}"

    def _delete_contagem_http(self, contagem_id) -> "Tuple[bool, str]":
        """Remove contagem via DELETE /contagens/{id} na API HTTP."""
        try:
            import requests
        except ImportError:
            return False, "Biblioteca 'requests' não instalada."

        url = f"{self._base_url}/contagens/{contagem_id}"
        headers = {"Authorization": self._authorization}
        try:
            resp = requests.delete(url, headers=headers, timeout=self.TIMEOUT)
            if resp.ok:
                return True, "Registro removido com sucesso."
            return False, f"Erro ao remover registro ({resp.status_code}): {resp.text[:300]}"
        except Exception as exc:
            return False, str(exc)

    # ------------------------------------------------------------------
    # Contagens
    # ------------------------------------------------------------------

    def list_contagens(
        self,
        cnpj: str,
        database_url: str = "",
    ) -> "Tuple[bool, list, Optional[str]]":
        """
        Lista contagens registradas para o CNPJ informado.

        Estratégia:
          1. Se ``database_url`` → consulta direta ao banco Neon.
          2. Caso contrário → GET /contagens na API HTTP.

        Returns:
            (sucesso, lista_de_registros, erro_ou_None)
        """
        if database_url:
            return self._list_contagens_db(cnpj, database_url)
        return self._list_contagens_http(cnpj)

    def _list_contagens_db(
        self, cnpj: str, database_url: str
    ) -> "Tuple[bool, list, Optional[str]]":
        """Consulta contagens diretamente no banco PostgreSQL (Neon)."""
        try:
            import psycopg2
            import psycopg2.extras
        except ImportError:
            try:
                import psycopg as psycopg2  # type: ignore
                import psycopg.rows  # type: ignore
            except ImportError:
                return False, [], "Driver psycopg2/psycopg não instalado."

        try:
            conn = psycopg2.connect(database_url)
            cur = conn.cursor(cursor_factory=getattr(psycopg2.extras, 'RealDictCursor', None))
            cur.execute(
                """
                SELECT id, cliente_id, nome_arquivo, data_envio,
                       cnpj, codvendedor, idcelular, url_arquivo
                  FROM contagens
                 WHERE cnpj = %s
                 ORDER BY data_envio DESC
                """,
                (cnpj,),
            )
            rows = cur.fetchall()
            cur.close()
            conn.close()
            result = []
            for row in rows:
                rec = dict(row) if hasattr(row, 'keys') else {
                    'id': row[0], 'cliente_id': row[1], 'nome_arquivo': row[2],
                    'data_envio': str(row[3]) if row[3] else '',
                    'cnpj': row[4], 'codvendedor': row[5],
                    'idcelular': row[6], 'url_arquivo': row[7],
                }
                if 'data_envio' in rec and rec['data_envio'] and not isinstance(rec['data_envio'], str):
                    rec['data_envio'] = str(rec['data_envio'])
                result.append(rec)
            return True, result, None
        except Exception as exc:
            return False, [], f"Erro ao consultar banco: {exc}"

    def _list_contagens_http(
        self, cnpj: str
    ) -> "Tuple[bool, list, Optional[str]]":
        """Lista contagens via GET /contagens na API HTTP (fallback)."""
        try:
            import requests
        except ImportError:
            return False, [], "Biblioteca 'requests' não instalada."

        url = f"{self._base_url}/contagens"
        headers = {"Authorization": self._authorization}
        params = {"cnpj": cnpj} if cnpj else {}
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=self.TIMEOUT)
            if resp.ok:
                body = resp.json()
                if isinstance(body, list):
                    return True, body, None
                if isinstance(body, dict):
                    items = body.get("items") or body.get("contagens") or []
                    return True, items, None
                return True, [], None
            return False, [], f"HTTP {resp.status_code}: {resp.text[:300]}"
        except Exception as exc:
            return False, [], str(exc)

    def download_contagem_file(
        self,
        url_arquivo: str,
        dest_path: str,
    ) -> "Tuple[bool, str]":
        """
        Faz download do arquivo de contagem (ZIP) para ``dest_path``.

        Usa o token de autorização configurado.

        Args:
            url_arquivo: URL do arquivo (campo ``url_arquivo`` da tabela contagens).
            dest_path:   Caminho local onde o arquivo será salvo.

        Returns:
            (sucesso, mensagem)
        """
        try:
            import requests
        except ImportError:
            return False, "Biblioteca 'requests' não instalada."

        headers = {"Authorization": self._authorization}
        try:
            resp = requests.get(url_arquivo, headers=headers, timeout=self.TIMEOUT, stream=True)
            if not resp.ok:
                try:
                    detail = resp.json().get("detail", resp.text)
                except Exception:
                    detail = resp.text or f"HTTP {resp.status_code}"
                return False, f"Erro ao baixar arquivo ({resp.status_code}): {detail}"

            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            with open(dest_path, "wb") as fh:
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        fh.write(chunk)
            return True, dest_path
        except Exception as exc:
            return False, f"Erro ao baixar arquivo: {exc}"

    @staticmethod
    def extract_cnpj_from_zip(zip_path: str) -> "Optional[str]":
        """
        Extrai o CNPJ do registro E do arquivo TXT contido no ZIP.

        Layout do registro E: ``|E|codempresa|nomeempresa|local|cnpj|``

        Args:
            zip_path: Caminho do arquivo ZIP.

        Returns:
            CNPJ encontrado (string) ou ``None``.
        """
        import zipfile as _zf

        try:
            with _zf.ZipFile(zip_path, "r") as zf:
                txt_names = [n for n in zf.namelist() if n.lower().endswith(".txt")]
                if not txt_names:
                    return None
                with zf.open(txt_names[0]) as tf:
                    for raw_line in tf:
                        try:
                            line = raw_line.decode("utf-8").strip()
                        except UnicodeDecodeError:
                            line = raw_line.decode("latin-1").strip()
                        # Registro E: |E|codempresa|nomeempresa|local|cnpj|
                        parts = line.split("|")
                        # partes: ['', 'E', codempresa, nomeempresa, local, cnpj, '']
                        if len(parts) >= 2 and parts[1].strip().upper() == "E":
                            if len(parts) >= 6:
                                return parts[5].strip()
                            return None
        except Exception:
            pass
        return None

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
