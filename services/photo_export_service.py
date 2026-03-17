"""
photo_export_service.py
=======================
Serviço de exportação de fotos de produtos.

Exporta imagens dos anexos de produtos para arquivo ZIP.
"""

import os
import io
import zipfile
from typing import Optional, List, Dict, Any, Callable, Tuple
from datetime import datetime
from dataclasses import dataclass

from database.connection import get_session
from sqlalchemy import text

# Pillow para manipulação de imagens
try:
    from PIL import Image
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False
    print("AVISO: Pillow não instalado. Instale com: pip install Pillow")


@dataclass
class PhotoInfo:
    """Informações de uma foto exportada."""
    codean: str
    codproduto: int
    filename: str
    format: str
    size_bytes: int


class PhotoExportService:
    """
    Serviço para exportação de fotos de produtos.
    
    Funcionalidades:
    - Consulta anexos de produtos no banco
    - Detecta tipo de imagem pelos magic bytes
    - Converte para JPG ou PNG
    - Compacta em arquivo ZIP
    """
    
    # Magic bytes para detecção de formato
    IMAGE_SIGNATURES = {
        b'\xff\xd8\xff': ('jpeg', '.jpg'),
        b'\x89PNG\r\n\x1a\n': ('png', '.png'),
        b'GIF87a': ('gif', '.gif'),
        b'GIF89a': ('gif', '.gif'),
        b'BM': ('bmp', '.bmp'),
        b'RIFF': ('webp', '.webp'),  # WebP começa com RIFF....WEBP
        b'II*\x00': ('tiff', '.tif'),  # TIFF little-endian
        b'MM\x00*': ('tiff', '.tif'),  # TIFF big-endian
    }
    
    # Query para buscar anexos
    _QUERY_ANEXOS = """
        SELECT 
            p.codproduto,
            COALESCE(p.codean, '') AS codean,
            p.unidade,
            COALESCE(p.codean, '') + 
                CASE WHEN p.unidade IS NOT NULL AND p.unidade <> '' 
                     THEN '/' + p.unidade 
                     ELSE '' 
                END AS codeanunidade,
            a.codanexo,
            a.arquivoanexo,
            a.descricao,
            a.tipo
        FROM produtosanexos a
        INNER JOIN produtos p ON p.codproduto = a.codproduto
        WHERE p.ativo = 1
          AND COALESCE(p.codean, '') <> ''
          AND a.arquivoanexo IS NOT NULL
    """
    
    def __init__(self, output_dir: str = None):
        """
        Inicializa o serviço.
        
        Args:
            output_dir: Diretório de saída (padrão: Documents/CSCollectManager/Exports)
        """
        if output_dir:
            self._output_dir = output_dir
        else:
            self._output_dir = os.path.join(
                os.path.expanduser("~"),
                "Documents",
                "CSCollectManager",
                "Exports"
            )
    
    @property
    def output_dir(self) -> str:
        """Retorna diretório de saída."""
        return self._output_dir
    
    @output_dir.setter
    def output_dir(self, value: str):
        """Define diretório de saída."""
        self._output_dir = value
    
    def detect_image_format(self, data: bytes) -> Tuple[str, str]:
        """
        Detecta formato da imagem pelos primeiros bytes (magic bytes).
        
        Args:
            data: Bytes da imagem
            
        Returns:
            Tupla (formato, extensão) ou ('unknown', '.bin')
        """
        if not data:
            return ('unknown', '.bin')
        
        # Verifica cada assinatura conhecida
        for signature, (fmt, ext) in self.IMAGE_SIGNATURES.items():
            if data[:len(signature)] == signature:
                # Verificação especial para WebP
                if fmt == 'webp' and len(data) >= 12:
                    if data[8:12] != b'WEBP':
                        continue
                return (fmt, ext)
        
        return ('unknown', '.bin')
    
    def convert_to_jpg(self, data: bytes, quality: int = 85) -> bytes:
        """
        Converte imagem para JPEG.
        
        Args:
            data: Bytes da imagem original
            quality: Qualidade do JPEG (1-100)
            
        Returns:
            Bytes da imagem convertida
        """
        if not PILLOW_AVAILABLE:
            raise RuntimeError("Pillow não disponível para conversão de imagem")
        
        try:
            # Abre a imagem
            img = Image.open(io.BytesIO(data))
            
            # Converte para RGB se necessário (PNG com alpha, etc)
            if img.mode in ('RGBA', 'LA', 'P'):
                # Cria fundo branco
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = background
            elif img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Salva como JPEG
            output = io.BytesIO()
            img.save(output, format='JPEG', quality=quality, optimize=True)
            return output.getvalue()
            
        except Exception as e:
            raise RuntimeError(f"Erro ao converter imagem para JPEG: {e}")
    
    def convert_to_png(self, data: bytes) -> bytes:
        """
        Converte imagem para PNG.
        
        Args:
            data: Bytes da imagem original
            
        Returns:
            Bytes da imagem convertida
        """
        if not PILLOW_AVAILABLE:
            raise RuntimeError("Pillow não disponível para conversão de imagem")
        
        try:
            img = Image.open(io.BytesIO(data))
            output = io.BytesIO()
            img.save(output, format='PNG', optimize=True)
            return output.getvalue()
            
        except Exception as e:
            raise RuntimeError(f"Erro ao converter imagem para PNG: {e}")
    
    def get_anexos_from_db(
        self, 
        codprodutos: List[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Busca anexos de produtos no banco de dados.
        
        Args:
            codprodutos: Lista de códigos de produtos (opcional, todos se None)
            
        Returns:
            Lista de dicionários com dados dos anexos
        """
        query = self._QUERY_ANEXOS
        params = {}
        
        if codprodutos:
            placeholders = ", ".join([f":cod_{i}" for i in range(len(codprodutos))])
            query += f" AND p.codproduto IN ({placeholders})"
            for i, cod in enumerate(codprodutos):
                params[f"cod_{i}"] = cod
        
        query += " ORDER BY p.codproduto, a.codanexo"
        
        try:
            with get_session() as session:
                result = session.execute(text(query), params)
                
                anexos = []
                for row in result:
                    anexos.append({
                        "codproduto": row.codproduto,
                        "codean": row.codean,
                        "unidade": row.unidade,
                        "codeanunidade": row.codeanunidade,
                        "codanexo": row.codanexo,
                        "arquivoanexo": row.arquivoanexo,
                        "descricao": row.descricao,
                        "tipo": row.tipo,
                    })
                
                return anexos
                
        except Exception as e:
            print(f"Erro ao buscar anexos: {e}")
            raise
    
    def export_photos_to_zip(
        self,
        codprodutos: List[int] = None,
        output_path: str = None,
        filename: str = "Fotos.zip",
        convert_to: str = "jpg",
        quality: int = 85,
        progress_callback: Optional[Callable[[int, str], None]] = None
    ) -> Tuple[str, List[PhotoInfo]]:
        """
        Exporta fotos de produtos para arquivo ZIP.
        
        Args:
            codprodutos: Lista de códigos de produtos (None = todos)
            output_path: Diretório de saída (usa padrão se None)
            filename: Nome do arquivo ZIP
            convert_to: Formato de saída ('jpg' ou 'png')
            quality: Qualidade JPEG (1-100)
            progress_callback: Callback de progresso (percentual, mensagem)
            
        Returns:
            Tupla (caminho do ZIP, lista de PhotoInfo)
        """
        if convert_to not in ('jpg', 'png'):
            raise ValueError("convert_to deve ser 'jpg' ou 'png'")
        
        if output_path is None:
            output_path = self._output_dir
        
        # Cria diretório se não existir
        os.makedirs(output_path, exist_ok=True)
        
        zip_path = os.path.join(output_path, filename)
        
        if progress_callback:
            progress_callback(0, "Consultando anexos no banco...")
        
        # Busca anexos
        anexos = self.get_anexos_from_db(codprodutos)
        total = len(anexos)
        
        if total == 0:
            raise ValueError("Nenhum anexo encontrado para exportar")
        
        if progress_callback:
            progress_callback(5, f"Encontrados {total} anexos. Processando...")
        
        exported_photos: List[PhotoInfo] = []
        processed_codeans = set()  # Para evitar duplicatas
        
        try:
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                for i, anexo in enumerate(anexos):
                    codean = anexo["codean"]
                    codproduto = anexo["codproduto"]
                    data = anexo["arquivoanexo"]
                    
                    # Pula se não tem dados
                    if not data:
                        continue
                    
                    # Pula se já processou este código EAN (pega só primeira foto)
                    if codean in processed_codeans:
                        continue
                    
                    processed_codeans.add(codean)
                    
                    try:
                        # Detecta formato original
                        original_format, original_ext = self.detect_image_format(data)
                        
                        # Determina nome e extensão do arquivo de saída
                        if convert_to == 'jpg':
                            output_ext = '.jpg'
                            # Converte para JPEG se não for
                            if original_format != 'jpeg':
                                if PILLOW_AVAILABLE:
                                    data = self.convert_to_jpg(data, quality)
                                # Se Pillow não disponível, mantém original
                        else:  # png
                            output_ext = '.png'
                            if original_format != 'png':
                                if PILLOW_AVAILABLE:
                                    data = self.convert_to_png(data)
                        
                        # Nome do arquivo: codean.jpg (remove caracteres inválidos)
                        safe_codean = "".join(
                            c for c in codean 
                            if c.isalnum() or c in '-_'
                        )
                        if not safe_codean:
                            safe_codean = f"produto_{codproduto}"
                        
                        output_filename = f"{safe_codean}{output_ext}"
                        
                        # Adiciona ao ZIP
                        zf.writestr(output_filename, data)
                        
                        # Registra foto exportada
                        exported_photos.append(PhotoInfo(
                            codean=codean,
                            codproduto=codproduto,
                            filename=output_filename,
                            format=convert_to,
                            size_bytes=len(data)
                        ))
                        
                    except Exception as e:
                        print(f"Erro ao processar anexo {codproduto}/{codean}: {e}")
                        continue
                    
                    # Atualiza progresso
                    if progress_callback and total > 0:
                        percentual = 5 + int((i + 1) / total * 90)
                        if (i + 1) % 50 == 0 or i == total - 1:
                            progress_callback(
                                percentual,
                                f"Processando foto {i + 1} de {total}..."
                            )
            
            if progress_callback:
                progress_callback(100, f"Exportação concluída! {len(exported_photos)} fotos.")
            
            return zip_path, exported_photos
            
        except Exception as e:
            # Remove ZIP parcial em caso de erro
            if os.path.exists(zip_path):
                os.remove(zip_path)
            raise RuntimeError(f"Erro ao criar arquivo ZIP: {e}")
    
    def export_photos_for_products(
        self,
        produtos: List[Dict[str, Any]],
        output_path: str = None,
        filename: str = "Fotos.zip",
        convert_to: str = "jpg",
        quality: int = 85,
        progress_callback: Optional[Callable[[int, str], None]] = None
    ) -> Tuple[str, List[PhotoInfo]]:
        """
        Exporta fotos para lista de produtos (dicionários).
        
        Args:
            produtos: Lista de produtos (com 'codproduto')
            output_path: Diretório de saída
            filename: Nome do arquivo ZIP
            convert_to: Formato de saída
            quality: Qualidade JPEG
            progress_callback: Callback de progresso
            
        Returns:
            Tupla (caminho do ZIP, lista de PhotoInfo)
        """
        codprodutos = [p.get("codproduto") for p in produtos if p.get("codproduto")]
        
        return self.export_photos_to_zip(
            codprodutos=codprodutos,
            output_path=output_path,
            filename=filename,
            convert_to=convert_to,
            quality=quality,
            progress_callback=progress_callback
        )
    
    def get_zip_info(self, zip_path: str) -> Dict[str, Any]:
        """
        Retorna informações sobre arquivo ZIP de fotos.
        
        Args:
            zip_path: Caminho do arquivo ZIP
            
        Returns:
            Dicionário com informações
        """
        if not os.path.exists(zip_path):
            raise FileNotFoundError(f"Arquivo não encontrado: {zip_path}")
        
        stat = os.stat(zip_path)
        
        with zipfile.ZipFile(zip_path, 'r') as zf:
            files = zf.namelist()
            total_uncompressed = sum(info.file_size for info in zf.infolist())
        
        return {
            "filepath": zip_path,
            "filename": os.path.basename(zip_path),
            "size_bytes": stat.st_size,
            "size_formatted": self._format_size(stat.st_size),
            "file_count": len(files),
            "files": files,
            "uncompressed_size": total_uncompressed,
            "uncompressed_formatted": self._format_size(total_uncompressed),
            "compression_ratio": (
                f"{(1 - stat.st_size / total_uncompressed) * 100:.1f}%"
                if total_uncompressed > 0 else "0%"
            ),
            "created": datetime.fromtimestamp(stat.st_ctime),
        }
    
    @staticmethod
    def _format_size(size_bytes: int) -> str:
        """Formata tamanho em bytes para exibição."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} TB"


# ===== EXEMPLO DE USO =====
if __name__ == "__main__":
    # Teste com dados simulados (sem banco)
    print("PhotoExportService - Teste")
    print("=" * 50)
    
    service = PhotoExportService()
    
    # Teste de detecção de formato
    test_signatures = [
        (b'\xff\xd8\xff\xe0\x00\x10JFIF', "JPEG"),
        (b'\x89PNG\r\n\x1a\n\x00\x00', "PNG"),
        (b'GIF89a\x00\x00', "GIF"),
        (b'BM\x00\x00\x00\x00', "BMP"),
        (b'RIFF\x00\x00\x00\x00WEBP', "WebP"),
    ]
    
    print("\nTeste de detecção de formato:")
    for data, expected in test_signatures:
        fmt, ext = service.detect_image_format(data)
        print(f"  {expected}: detectado como {fmt} ({ext})")
    
    print(f"\nDiretório de saída: {service.output_dir}")
    print(f"Pillow disponível: {PILLOW_AVAILABLE}")
