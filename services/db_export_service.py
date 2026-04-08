"""
db_export_service.py
====================
Exportação de carga para SQLite (.db).

Mantém exatamente os mesmos registros e campos do TXT (E, V, P).
Cada exportação recebe:
  - assinatura : UUID4 único (identidade da exportação)
  - hash_conteudo: SHA-256 do conteúdo canônico (mesmas linhas que o TXT geraria)

O app mobile valida:
  1. versao_layout — compatibilidade de esquema
  2. assinatura   — UUID4 bem formado
  3. hash_conteudo — recalcular SHA-256 dos registros e comparar

Esquema de tabelas
------------------
exportacao  — metadados + assinatura + hash
empresa     — registro E
vendedor    — registro V
produtos    — registro P (uma linha por produto)
"""

import os
import shutil
import zipfile
from pathlib import Path
import uuid
import hashlib
import sqlite3
from typing import Optional, List, Dict, Any, Callable
from datetime import datetime

from services.export_service import EmpresaInfo, UsuarioInfo, ProdutoExport, ExportService
from utils.config import AppConfig
from utils.crypto import ensure_keypair, sign_file

# Versão do layout — incrementar se o esquema mudar
LAYOUT_VERSION = 1


class DbExportService:
    """
    Gera arquivo SQLite de carga com assinatura única por exportação.

    Campos por tabela
    -----------------
    exportacao : id, assinatura, hash_conteudo, versao_layout, gerado_em, total_produtos
    empresa    : codempresa, nomeempresa, local
    vendedor   : codusuario, nomeusuario
    produtos   : seq, codean, codproduto, descricaoproduto, unidade, casasdecimais,
                 controlalote, numlote, datafab, dataval, codgrupo, nomegrupo, localizacao
    """

    def __init__(self, output_dir: str = None):
        if output_dir:
            self._output_dir = output_dir
        else:
            self._output_dir = os.path.join(
                os.path.expanduser("~"),
                "Documents",
                "CSCollectManager",
                "Exports",
            )

    @property
    def output_dir(self) -> str:
        return self._output_dir

    @output_dir.setter
    def output_dir(self, value: str):
        self._output_dir = value

    # ------------------------------------------------------------------
    # Público
    # ------------------------------------------------------------------

    def generate_filename(
        self,
        codempresa: int,
        codusuario: int,
        data_hora: datetime = None,
    ) -> str:
        """
        Gera nome do arquivo DB.

        Formato: CARGA-CODEMPRESA-CODUSUARIO-DATAHORA.db
        Exemplo: CARGA-1-001-100220260843.db
        """
        if data_hora is None:
            data_hora = datetime.now()
        timestamp = data_hora.strftime("%d%m%Y%H%M")
        cod_usuario_str = f"{codusuario:03d}"
        return f"CARGA-{codempresa}-{cod_usuario_str}-{timestamp}.db"

    def export_carga(
        self,
        empresa: EmpresaInfo,
        usuario: UsuarioInfo,
        produtos: List[Dict[str, Any]],
        output_path: str = None,
        progress_callback: Optional[Callable[[int, str], None]] = None,
        include_photos: bool = False,
        photos_output_dir: Optional[str] = None,
    ) -> str:
        """
        Gera o arquivo .db equivalente ao TXT de carga.

        Args:
            empresa:           Dados da empresa (registro E).
            usuario:           Dados do vendedor (registro V).
            produtos:          Lista de dicts com dados dos produtos.
            output_path:       Diretório de saída (usa padrão se None).
            progress_callback: Chamado com (percentual_int, mensagem).

        Returns:
            Caminho completo do arquivo .db gerado.

        Raises:
            ValueError: se a lista de produtos estiver vazia.
            IOError:    se não for possível gravar o arquivo.
        """
        if not produtos:
            raise ValueError("Nenhum produto para exportar")

        if output_path is None:
            output_path = self._output_dir

        os.makedirs(output_path, exist_ok=True)

        now = datetime.now()
        filename = self.generate_filename(empresa.codempresa, usuario.codusuario, now)
        filepath = os.path.join(output_path, filename)

        total = len(produtos)

        if progress_callback:
            progress_callback(0, "Iniciando exportação DB...")

        # Converte dicts → ProdutoExport (mesma lógica do TXT)
        txt_svc = ExportService()
        produtos_exp: List[ProdutoExport] = [ProdutoExport.from_dict(p) for p in produtos]

        if progress_callback:
            progress_callback(5, "Calculando assinatura...")

        # Assinatura única + hash de conteúdo
        assinatura = str(uuid.uuid4())
        hash_conteudo = self._compute_hash(txt_svc, empresa, usuario, produtos_exp)

        # Remove arquivo anterior se existir (mesma pasta, mesmo nome improvável mas seguro)
        if os.path.exists(filepath):
            os.remove(filepath)

        try:
            conn = sqlite3.connect(filepath)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")

            try:
                cur = conn.cursor()
                self._create_schema(cur)
                conn.commit()

                # --- exportacao ---
                cur.execute(
                    """INSERT INTO exportacao
                           (assinatura, hash_conteudo, versao_layout, gerado_em, total_produtos)
                       VALUES (?, ?, ?, ?, ?)""",
                    (assinatura, hash_conteudo, LAYOUT_VERSION, now.isoformat(), total),
                )

                # --- empresa (registro E) ---
                cur.execute(
                    "INSERT INTO empresa (tipo, codempresa, nomeempresa, local, cnpj) VALUES (?, ?, ?, ?, ?)",
                    ("E", str(empresa.codempresa), empresa.nomeempresa, empresa.local, getattr(empresa, 'cnpj', '') or ''),
                )

                # --- vendedor (registro V) ---
                cur.execute(
                    "INSERT INTO vendedor (tipo, codusuario, nomeusuario, id_celular) VALUES (?, ?, ?, ?)",
                    ("V", str(usuario.codusuario).zfill(3), usuario.nomeusuario, getattr(usuario, 'id_celular', '') or ''),
                )

                if progress_callback:
                    progress_callback(10, "Gravando produtos no DB...")

                # --- produtos (registro P) ---
                batch: list = []
                BATCH_SIZE = 200

                for i, p in enumerate(produtos_exp):
                    batch.append((
                        "P",
                        p.codean,
                        str(p.codproduto),
                        p.descricaoproduto,
                        p.unidade,
                        p.casasdecimais,
                        p.controlalote,
                        p.numlote,
                        txt_svc.format_date(p.datafab),
                        txt_svc.format_date(p.dataval),
                        str(p.codgrupo),
                        p.nomegrupo,
                        p.localizacao.strip(),
                    ))

                    if len(batch) >= BATCH_SIZE:
                        cur.executemany(
                            """INSERT INTO produtos
                               (tipo, codean, codproduto, descricaoproduto, unidade, casasdecimais,
                                controlalote, numlote, datafab, dataval,
                                codgrupo, nomegrupo, localizacao)
                               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                            batch,
                        )
                        conn.commit()
                        batch.clear()

                        if progress_callback and total > 0:
                            pct = 10 + int((i + 1) / total * 85)
                            progress_callback(pct, f"Gravando produto {i + 1} de {total}...")

                # flush restante
                if batch:
                    cur.executemany(
                        """INSERT INTO produtos
                           (tipo, codean, codproduto, descricaoproduto, unidade, casasdecimais,
                            controlalote, numlote, datafab, dataval,
                            codgrupo, nomegrupo, localizacao)
                           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        batch,
                    )
                    conn.commit()

            finally:
                conn.close()

        except Exception as e:
            # Remove arquivo corrompido
            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                except OSError:
                    pass
            raise IOError(f"Erro ao gravar arquivo DB: {e}") from e

        if progress_callback:
            progress_callback(100, "Exportação DB concluída!")

        # Tenta assinar o arquivo DB gerado (arquivo .sig separado)
        sig_path = None
        try:
            priv_path = AppConfig.get_private_key_path()
            pub_path = AppConfig.get_public_key_path()
            ensure_keypair(priv_path, pub_path)
            sig_path = sign_file(priv_path, filepath)
            # opcional: informar progresso sobre assinatura
            if progress_callback:
                progress_callback(95, f"Assinatura gravada: {os.path.basename(sig_path)}")
        except Exception:
            # Não interrompe o fluxo de exportação se a assinatura falhar
            if progress_callback:
                progress_callback(95, "Falha ao assinar arquivo (assinatura ignorada).")

        # Empacota os arquivos gerados (.db e .sig se existir) em um ZIP
        try:
            zip_path = str(Path(filepath).with_suffix('.zip'))
            with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
                zf.write(filepath, arcname=Path(filepath).name)
                if sig_path and os.path.exists(sig_path):
                    zf.write(sig_path, arcname=Path(sig_path).name)

                # Se solicitado, inclui também as fotos extraídas (não compactadas junto com o DB,
                # mas gravadas em pasta separada dentro do diretório de saída). Isso evita alterar
                # o ZIP da carga (que é consumido pelo coletor) enquanto mantém as fotos disponíveis.
                if include_photos:
                    try:
                        from services.extrair_imagens import exportar_imagens_para_pasta
                        photos_dest = photos_output_dir or os.path.join(output_path, 'Fotos')
                        # produtos é a lista de dicts originais; extrai codproduto
                        cods = [str(p.get('codproduto')) for p in produtos if p.get('codproduto')]
                        saved = exportar_imagens_para_pasta(cods, photos_dest)
                        # Se houver fotos salvas, adiciona pasta compactada separadamente
                        if saved:
                            # Compacta a pasta de fotos em um ZIP auxiliar dentro do output
                            photos_zip = os.path.join(output_path, 'Fotos.zip')
                            with zipfile.ZipFile(photos_zip, 'w', zipfile.ZIP_DEFLATED) as pzf:
                                for fpath in saved:
                                    try:
                                        pzf.write(fpath, arcname=os.path.basename(fpath))
                                    except Exception:
                                        continue
                            # Inclui o Fotos.zip no ZIP final
                            if os.path.exists(photos_zip):
                                zf.write(photos_zip, arcname=os.path.basename(photos_zip))
                                try:
                                    os.remove(photos_zip)
                                except Exception:
                                    pass
                            # Remove a pasta descompactada de fotos
                            try:
                                shutil.rmtree(photos_dest, ignore_errors=True)
                            except Exception:
                                pass
                    except Exception:
                        # Não interrompe a exportação se falhar a extração de fotos
                        pass

            # Remove arquivos originais para deixar apenas o zip (comportamento opcional)
            try:
                os.remove(filepath)
            except Exception:
                pass
            if sig_path and os.path.exists(sig_path):
                try:
                    os.remove(sig_path)
                except Exception:
                    pass

            if progress_callback:
                progress_callback(100, f"Exportação empacotada: {os.path.basename(zip_path)}")

            return zip_path
        except Exception:
            # Se empacotamento falhar, retorna o .db original
            if progress_callback:
                progress_callback(100, "Falha ao empacotar arquivos (retornando .db).")
            return filepath

        return filepath

    # ------------------------------------------------------------------
    # Privado
    # ------------------------------------------------------------------

    @staticmethod
    def _create_schema(cur: sqlite3.Cursor) -> None:
        """Cria tabelas do banco de dados."""
        cur.executescript("""
            CREATE TABLE IF NOT EXISTS exportacao (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                assinatura     TEXT    NOT NULL,
                hash_conteudo  TEXT    NOT NULL,
                versao_layout  INTEGER NOT NULL,
                gerado_em      TEXT    NOT NULL,
                total_produtos INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS empresa (
                tipo        TEXT    NOT NULL,
                codempresa  TEXT    NOT NULL,
                nomeempresa TEXT    NOT NULL,
                local       TEXT    NOT NULL,
                cnpj        TEXT    NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS vendedor (
                tipo        TEXT NOT NULL,
                codusuario  TEXT NOT NULL,
                nomeusuario TEXT NOT NULL,
                id_celular  TEXT    NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS produtos (
                seq              INTEGER PRIMARY KEY AUTOINCREMENT,
                tipo             TEXT    NOT NULL,
                codean           TEXT    NOT NULL,
                codproduto       TEXT NOT NULL,
                descricaoproduto TEXT    NOT NULL,
                unidade          TEXT    NOT NULL,
                casasdecimais    INTEGER NOT NULL DEFAULT 3,
                controlalote     TEXT    NOT NULL DEFAULT '0',
                numlote          TEXT    NOT NULL DEFAULT '',
                datafab          TEXT    NOT NULL DEFAULT '',
                dataval          TEXT    NOT NULL DEFAULT '',
                codgrupo         TEXT NOT NULL DEFAULT '0',
                nomegrupo        TEXT    NOT NULL DEFAULT '',
                localizacao      TEXT    NOT NULL DEFAULT ''
            );

            CREATE INDEX IF NOT EXISTS idx_produtos_codean
                ON produtos (codean);

            CREATE INDEX IF NOT EXISTS idx_produtos_codproduto
                ON produtos (codproduto);
        """)

    @staticmethod
    def _compute_hash(
        txt_svc: ExportService,
        empresa: EmpresaInfo,
        usuario: UsuarioInfo,
        produtos: List[ProdutoExport],
    ) -> str:
        """
        Calcula SHA-256 do conteúdo canônico.

        Usa exatamente as mesmas linhas que o TXT geraria, garantindo que
        o app mobile possa recomputar o hash a partir das tabelas do DB.
        """
        lines: List[str] = [
            txt_svc.build_registro_e(empresa),
            txt_svc.build_registro_v(usuario),
        ]
        for p in produtos:
            lines.append(txt_svc.build_registro_p(p))

        canonical = "\n".join(lines)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
