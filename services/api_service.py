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
from typing import Callable, Optional, Tuple

# Status que valem a pena reesperar: o serviço está fora do ar, reiniciando ou
# acordando, e tende a voltar sozinho em segundos.
_STATUS_TRANSITORIOS = (502, 503, 504)

# Mensagens por status para respostas sem corpo útil (ex.: página HTML do
# Cloudflare, ou corpo vazio do proxy quando a origem está fora).
_MENSAGENS_STATUS = {
    429: ("Muitas tentativas seguidas — o servidor bloqueou temporariamente. "
          "Aguarde alguns minutos antes de tentar de novo."),
    502: "Servidor temporariamente indisponível (falha no gateway).",
    503: "Serviço temporariamente indisponível — o servidor pode estar fora do ar ou reiniciando.",
    504: "O servidor demorou demais para responder (tempo esgotado no gateway).",
    401: "Não autorizado — verifique o token da API.",
    403: "Acesso negado — verifique o token da API.",
    404: "Recurso não encontrado no servidor.",
}

_LIMITE_TEXTO_ERRO = 300


def _descrever_erro_http(resp) -> str:
    """Resume a resposta de erro numa mensagem curta e legível.

    Existe porque despejar `resp.text` na interface é inútil e destrutivo: o
    Cloudflare responde com uma página de challenge de vários KB, que não diz
    nada ao usuário e estica o diálogo a ponto de quebrar o layout.

    Ordem: `detail` do FastAPI → mensagem conhecida do status → texto truncado.
    """
    status = getattr(resp, "status_code", 0)

    # 1. Erro estruturado da própria API (FastAPI usa {"detail": ...}).
    try:
        detalhe = (resp.json() or {}).get("detail")
        if detalhe:
            return str(detalhe)[:_LIMITE_TEXTO_ERRO]
    except Exception:
        pass

    corpo = (getattr(resp, "text", "") or "").strip()
    tipo = str((getattr(resp, "headers", {}) or {}).get("content-type", "")).lower()
    parece_html = corpo[:15].lower().startswith(("<!doctype", "<html")) or "html" in tipo

    # 2. Corpo vazio ou página HTML (challenge/erro do proxy): o corpo não
    #    acrescenta nada, então usa a mensagem do status.
    if not corpo or parece_html:
        return _MENSAGENS_STATUS.get(status, f"HTTP {status}")

    # 3. Texto simples — trunca para não estourar a interface.
    return corpo[:_LIMITE_TEXTO_ERRO]


class ApiService:
    """
    Serviço para envio de cargas (arquivos ZIP) para a API CSCollect.

    Utiliza ``requests`` para realizar requisições HTTP.
    """

    UPLOAD_PATH = "/upload"
    TIMEOUT = 60  # segundos

    # Tempo total que o envio espera a API voltar antes de desistir e devolver
    # a decisão ao usuário (tentar de novo ou cancelar).
    JANELA_ESPERA_SEG = 60
    # Espaçamento entre tentativas dentro da janela. Ritmo contido de propósito:
    # tentativas em rajada é o que faz o Cloudflare responder 429.
    INTERVALO_ESPERA_SEG = 10

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

    def upload_file(
        self,
        filepath: str,
        cnpj: Optional[str] = None,
        codvendedor: Optional[str] = None,
        idcelular: Optional[str] = None,
        progresso: Optional[Callable[[str], None]] = None,
    ) -> Tuple[bool, str]:
        """
        Envia um arquivo ZIP para o endpoint ``/upload`` da API.

        Em erro transitório (serviço fora do ar, reiniciando ou sem conexão), a
        chamada continua esperando a API voltar por até ``JANELA_ESPERA_SEG``
        segundos antes de desistir — em vez de falhar de imediato e levar o
        usuário a clicar "Tentar novamente" em rajada, o que faz o servidor
        responder 429.

        Erros permanentes (401/403/400/404) e o próprio 429 encerram na hora:
        repetir não ajuda e, no caso do 429, piora.

        Args:
            filepath:   Caminho completo do arquivo a enviar.
            progresso:  Callback opcional para acompanhar a espera; recebe uma
                        mensagem pronta para exibição. Chamado da thread que
                        executa o upload.

        Returns:
            Tupla ``(sucesso, mensagem)``.
        """
        try:
            import requests
        except ImportError:
            return False, "Biblioteca 'requests' não instalada. Execute: pip install requests"

        if not os.path.isfile(filepath):
            return False, f"Arquivo não encontrado: {filepath}"

        import logging
        import time

        log = logging.getLogger("CSCollect.services.api_service")
        url = f"{self._base_url}{self.UPLOAD_PATH}"
        headers = {"Authorization": self._authorization}
        filename = os.path.basename(filepath)

        _tok = self._authorization or ""
        log.debug(
            "Upload para %s | token: %d chars, prefixo '%s'",
            url, len(_tok), _tok[:8] if _tok else "(vazio)",
        )

        data = {}
        if cnpj:
            data["cnpj"] = cnpj
        if codvendedor:
            data["codvendedor"] = codvendedor
        if idcelular:
            data["idcelular"] = idcelular

        def _avisar(msg: str):
            if progresso:
                try:
                    progresso(msg)
                except Exception:
                    pass

        inicio = time.monotonic()
        tentativa = 0
        ultima_msg = ""

        while True:
            tentativa += 1
            espera = self.INTERVALO_ESPERA_SEG
            try:
                # O arquivo é reaberto a cada tentativa: um handle já consumido
                # pela tentativa anterior enviaria corpo vazio.
                with open(filepath, "rb") as fh:
                    resp = requests.post(
                        url,
                        files={"file": (filename, fh)},
                        data=data if data else None,
                        headers=headers,
                        timeout=self.TIMEOUT,
                    )

                log.debug("Upload tentativa %d → HTTP %s", tentativa, resp.status_code)

                if resp.ok:
                    try:
                        corpo = resp.json()
                        return True, f"Arquivo '{corpo.get('arquivo', filename)}' enviado com sucesso."
                    except Exception:
                        return True, f"Arquivo enviado com sucesso. (HTTP {resp.status_code})"

                ultima_msg = f"Erro da API ({resp.status_code}): {_descrever_erro_http(resp)}"

                if resp.status_code not in _STATUS_TRANSITORIOS:
                    # Inclui o 429: insistir é exatamente o que agrava o bloqueio.
                    log.warning("Upload falhou sem nova tentativa: %s", ultima_msg)
                    return False, ultima_msg

                # `Retry-After` do servidor tem prioridade sobre o intervalo padrão.
                try:
                    cabecalho = (resp.headers or {}).get("Retry-After")
                    if cabecalho:
                        espera = max(1, min(int(float(cabecalho)), self.JANELA_ESPERA_SEG))
                except Exception:
                    pass

            except requests.exceptions.ConnectionError:
                ultima_msg = "Não foi possível conectar à API. Verifique a URL e a conexão com a internet."
            except requests.exceptions.Timeout:
                ultima_msg = f"Tempo esgotado após {self.TIMEOUT}s. A API pode estar indisponível."
            except Exception as exc:
                log.warning("Upload falhou com erro inesperado: %s", exc)
                return False, f"Erro inesperado ao enviar: {exc}"

            decorrido = time.monotonic() - inicio
            restante = self.JANELA_ESPERA_SEG - decorrido
            if restante <= 0:
                log.warning(
                    "Upload desistiu após %.0fs e %d tentativa(s): %s",
                    decorrido, tentativa, ultima_msg,
                )
                return False, (
                    f"A API não respondeu em {self.JANELA_ESPERA_SEG}s "
                    f"({tentativa} tentativa(s)).\n{ultima_msg}"
                )

            espera = min(espera, restante)
            _avisar(
                f"⏳  Aguardando a API responder... {int(decorrido)}s de "
                f"{self.JANELA_ESPERA_SEG}s (tentativa {tentativa})"
            )
            time.sleep(espera)

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
            return False, None, f"HTTP {resp.status_code}: {_descrever_erro_http(resp)}"
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
            return False, f"Erro ao remover registro ({resp.status_code}): {_descrever_erro_http(resp)}"
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
        """Remove contagem via DELETE /contagem/{id} na API HTTP."""
        try:
            import requests
        except ImportError:
            return False, "Biblioteca 'requests' não instalada."

        url = f"{self._base_url}/contagem/{contagem_id}"
        headers = {"Authorization": self._authorization}
        try:
            resp = requests.delete(url, headers=headers, timeout=self.TIMEOUT)
            if resp.ok:
                return True, "Registro removido com sucesso."
            return False, f"Erro ao remover registro ({resp.status_code}): {_descrever_erro_http(resp)}"
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
        """Lista contagens via GET /contagens?cnpj=... na API HTTP (fallback)."""
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
            # 404 significa que não há contagens para o CNPJ informado — trata como lista vazia
            if resp.status_code == 404:
                return True, [], None
            return False, [], f"HTTP {resp.status_code}: {_descrever_erro_http(resp)}"
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
                detail = _descrever_erro_http(resp)
                if resp.status_code == 404:
                    detail = (
                        f"{detail}\n\n"
                        "O arquivo não está mais disponível no servidor. Solicite a reexportação "
                        "da contagem para gerar um novo arquivo e reenviá-lo. O registro atual "
                        "será removido ao confirmar o problema."
                    )
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

    @staticmethod
    def validate_sig(zip_path: str, token_cliente: str) -> dict:
        """
        Valida o arquivo ``.sig`` contido no ZIP exportado pelo CSCollect.

        O ``.sig`` é um JSON com dois campos raiz::

            {
              "assinatura": "<hex HMAC-SHA256 do payload>",
              "payload": { ... }
            }

        A assinatura HMAC-SHA256 é calculada sobre o JSON canônico do payload
        (sort_keys=True, separators=(',', ':'), UTF-8).  A chave HMAC é o
        ``token_cliente`` (campo ``serial`` da licença).

        Args:
            zip_path:       Caminho do arquivo ZIP.
            token_cliente:  Token da licença (campo ``serial`` / autorização).

        Returns:
            dict com:
                ok      (bool)  – True se assinatura e hashes são válidos.
                erros   (list)  – Lista de mensagens de erro.
                payload (dict)  – Payload do .sig (mesmo se inválido).
        """
        import hashlib as _hl
        import hmac as _hmac
        import json as _json
        import zipfile as _zf

        erros: list = []
        payload: dict = {}

        try:
            with _zf.ZipFile(zip_path, "r") as zf:
                names = zf.namelist()

                # 1. Localizar o .sig
                sig_names = [n for n in names if n.lower().endswith(".sig")]
                if not sig_names:
                    return {"ok": False, "erros": ["Arquivo .sig não encontrado no ZIP"], "payload": {}}

                sig_content = zf.read(sig_names[0]).decode("utf-8")
                doc = _json.loads(sig_content)
                payload    = doc.get("payload", {})
                assinatura = doc.get("assinatura", "")

                # 2. JSON canônico do payload
                payload_json  = _json.dumps(payload, sort_keys=True, ensure_ascii=False,
                                            separators=(",", ":"))
                payload_bytes = payload_json.encode("utf-8")

                # 3. Validar HMAC
                # A chave HMAC é o token da licença do cliente (campo 'token' do .key
                # = campo 'serial' no payload).  Se token_cliente não for fornecido,
                # extrai o 'serial' diretamente do payload como fallback.
                hmac_key = token_cliente or payload.get("serial", "")
                if hmac_key:
                    expected_sig = _hmac.new(
                        hmac_key.encode("utf-8"),
                        payload_bytes,
                        _hl.sha256,
                    ).hexdigest()
                    if not _hmac.compare_digest(expected_sig, assinatura):
                        # O token local pode simplesmente ter sido substituído
                        # depois que o arquivo foi assinado (troca de plano /
                        # renovação regeram o token). Só o servidor consegue
                        # dizer se o serial do arquivo é um token legítimo,
                        # pois só ele tem a MASTER_KEY.
                        autentico, motivo_online = ApiService._confirmar_sig_no_servidor(doc)
                        if not autentico:
                            erros.append(ApiService._diagnosticar_hmac_invalido(
                                token_local=token_cliente,
                                payload=payload,
                                payload_bytes=payload_bytes,
                                assinatura=assinatura,
                                motivo_servidor=motivo_online,
                            ))
                else:
                    erros.append("Token de licença ausente — não foi possível validar a assinatura HMAC")

                # 4. Helper SHA-256 de uma entrada do ZIP
                def _sha256_entry(name: str) -> str:
                    h = _hl.sha256()
                    with zf.open(name) as f:
                        for chunk in iter(lambda: f.read(65536), b""):
                            h.update(chunk)
                    return h.hexdigest()

                # 4a. Arquivo de dados: .db (formato atual) ou .txt (formato legado)
                db_names = [n for n in names if n.lower().endswith(".db")]
                txt_names = [n for n in names if n.lower().endswith(".txt")]

                if db_names:
                    h = _sha256_entry(db_names[0])
                    if h != payload.get("hash_db", ""):
                        erros.append(
                            f"Hash DB diverge — esperado={payload.get('hash_db')} calculado={h}"
                        )
                elif txt_names:
                    h = _sha256_entry(txt_names[0])
                    if h != payload.get("hash_txt", ""):
                        erros.append(
                            f"Hash TXT diverge — esperado={payload.get('hash_txt')} calculado={h}"
                        )
                else:
                    erros.append("Arquivo de dados (.db ou .txt) não encontrado no ZIP")

                # 4b. PDF (opcional)
                pdf_names = [n for n in names if n.lower().endswith(".pdf")]
                if pdf_names and payload.get("hash_pdf"):
                    h = _sha256_entry(pdf_names[0])
                    if h != payload["hash_pdf"]:
                        erros.append(
                            f"Hash PDF diverge — esperado={payload['hash_pdf']} calculado={h}"
                        )

                # 4c. Fotos
                for arcname, expected_hash in (payload.get("hash_fotos") or {}).items():
                    if arcname in names:
                        h = _sha256_entry(arcname)
                        if h != expected_hash:
                            erros.append(
                                f"Hash foto diverge [{arcname}] — esperado={expected_hash} calculado={h}"
                            )
                    else:
                        erros.append(f"Foto declarada no .sig não encontrada no ZIP: {arcname}")

        except Exception as exc:
            erros.append(f"Erro ao processar .sig: {exc}")

        return {"ok": len(erros) == 0, "erros": erros, "payload": payload}

    @staticmethod
    def _confirmar_sig_no_servidor(doc: dict) -> Tuple[bool, str]:
        """Pergunta à API se o `.sig` foi assinado por um token legítimo.

        Usado quando o HMAC não confere com o token local — o caso normal é o
        token ter sido regerado depois que o arquivo foi assinado. A API
        verifica a assinatura do próprio serial com a MASTER_KEY, que nunca
        sai do servidor.

        Retorna ``(autentico, motivo)``. Qualquer falha (API antiga, sem rede,
        MASTER_KEY ausente) devolve ``False``: na dúvida, o arquivo continua
        rejeitado.
        """
        api = ApiService.from_config()
        if api is None:
            return False, "API não configurada"

        try:
            import requests
        except ImportError:
            return False, "biblioteca 'requests' não instalada"

        url = f"{api._base_url}/validar-sig"
        try:
            resp = requests.post(
                url,
                json={"assinatura": doc.get("assinatura", ""), "payload": doc.get("payload", {})},
                headers={"Authorization": api._authorization},
                timeout=ApiService.TIMEOUT,
            )
        except Exception as e:
            return False, f"não foi possível consultar o servidor ({e})"

        if resp.status_code == 404:
            return False, "servidor ainda não publicou o endpoint /validar-sig"
        if resp.status_code != 200:
            return False, f"servidor respondeu {resp.status_code}"

        try:
            data = resp.json()
        except Exception:
            return False, "resposta inválida do servidor"

        if data.get("ok"):
            return True, ""
        return False, str(data.get("mensagem") or data.get("motivo") or "assinatura recusada pelo servidor")

    @staticmethod
    def _decodificar_token_licenca(token: str) -> dict:
        """Extrai o JSON de dentro de um token de licença.

        O token é base64 (padrão ou urlsafe) de ``<json><assinatura binária>``.
        Retorna ``{}`` se não for possível decodificar — este helper serve só
        para melhorar mensagens de erro e nunca deve alterar o resultado da
        validação.
        """
        import base64 as _b64
        import json as _json

        bruto = None
        for decoder in (_b64.b64decode, _b64.urlsafe_b64decode):
            for pad in range(4):
                try:
                    bruto = decoder((token or "") + "=" * pad)
                    break
                except Exception:
                    continue
            if bruto is not None:
                break
        if not bruto:
            return {}

        # O JSON vem primeiro; o resto são os bytes da assinatura.
        profundidade = 0
        for i, b in enumerate(bruto):
            if b == 0x7B:
                profundidade += 1
            elif b == 0x7D:
                profundidade -= 1
                if profundidade == 0:
                    try:
                        return _json.loads(bruto[:i + 1].decode("utf-8"))
                    except Exception:
                        return {}
        return {}

    @staticmethod
    def _diagnosticar_hmac_invalido(
        token_local: str,
        payload: dict,
        payload_bytes: bytes,
        assinatura: str,
        motivo_servidor: str = "",
    ) -> str:
        """Explica *por que* o HMAC não conferiu.

        A causa mais comum não é adulteração, e sim licença renovada: o coletor
        recebe o token novo e assina com ele, enquanto o .key do desktop ainda
        tem o token anterior. Distinguir os dois casos evita diagnosticar
        corrupção de arquivo onde o problema é licença desatualizada.
        """
        import hashlib as _hl
        import hmac as _hmac

        generico = "Assinatura HMAC inválida — token não confere ou payload adulterado"

        serial = (payload or {}).get("serial", "")
        if not serial or not token_local:
            return generico

        # O .sig é internamente consistente? Se o HMAC fecha com o serial do
        # próprio payload, o arquivo não foi adulterado — o que não confere é
        # a chave local.
        confere_com_serial = _hmac.compare_digest(
            _hmac.new(serial.encode("utf-8"), payload_bytes, _hl.sha256).hexdigest(),
            assinatura,
        )
        if not confere_com_serial:
            return generico

        local = ApiService._decodificar_token_licenca(token_local)
        remoto = ApiService._decodificar_token_licenca(serial)
        val_local = str(local.get("validade") or "")
        val_remoto = str(remoto.get("validade") or "")

        sufixo = f" (servidor: {motivo_servidor})" if motivo_servidor else ""

        if val_local and val_remoto and val_local < val_remoto:
            return (
                "Licença do desktop desatualizada — o arquivo foi assinado com um "
                f"token mais recente (licença até {val_remoto}) do que o instalado "
                f"nesta máquina (até {val_local}). O arquivo NÃO está adulterado. "
                "Atualize a licença em 'Verificar licença agora' na tela de login e "
                f"baixe o arquivo novamente.{sufixo}"
            )

        return (
            "Assinatura HMAC inválida — o arquivo é internamente consistente, mas "
            "foi assinado com um token de licença diferente do instalado nesta "
            "máquina, e o servidor não confirmou a autenticidade dele."
            f"{sufixo}"
        )

    @staticmethod
    # ------------------------------------------------------------------

    @staticmethod
    def from_config() -> Optional["ApiService"]:
        """
        Cria uma instância a partir das configurações salvas em ``user_settings.json``.

        Returns:
            ``ApiService`` configurado, ou ``None`` se URL/token não estiverem definidos.
        """
        from utils.config import AppConfig
        try:
            url = AppConfig.get_api_url()
            token = AppConfig.get_api_authorization()
        except Exception as e:
            import logging
            logging.getLogger("ApiService").error(
                f"from_config: falha ao ler configuração da API (possível erro de descriptografia): {e}"
            )
            return None
        if url and token:
            return ApiService(base_url=url, authorization=token)
        return None
