"""
export_service.py
=================
Serviço de exportação de carga para coletores de dados.

Layout do arquivo TXT:
- Registro E: Empresa
- Registro V: Vendedor/Usuário  
- Registro P: Produto
"""

import os
import zipfile
from typing import Optional, List, Dict, Any, Callable
from pathlib import Path
from datetime import datetime, date
from dataclasses import dataclass


@dataclass
class EmpresaInfo:
    """Informações da empresa para exportação."""
    codempresa: int
    nomeempresa: str
    local: str = ""
    cnpj: str = ""


@dataclass
class UsuarioInfo:
    """Informações do usuário para exportação."""
    codusuario: int
    nomeusuario: str
    id_celular: str = ""


@dataclass
class ProdutoExport:
    """Dados do produto para exportação."""
    codean: str
    codproduto: int
    descricaoproduto: str
    unidade: str
    casasdecimais: int
    controlalote: str  # 'S' ou 'N'
    numlote: str
    datafab: Optional[date]
    dataval: Optional[date]
    codgrupo: int
    nomegrupo: str
    localizacao: str
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProdutoExport":
        """Cria instância a partir de dicionário."""
        return cls(
            codean=str(data.get("codean", data.get("codeanunidade", ""))).split("/")[0],
            codproduto=data.get("codproduto", 0),
            descricaoproduto=data.get("descricaoproduto", data.get("descricao", "")),
            unidade=data.get("unidade", "UN"),
            casasdecimais=data.get("casasdecimais", 3),
            controlalote="1" if data.get("controlalote") or data.get("controlarlote") else "0",
            numlote=data.get("numlote", ""),
            datafab=cls._parse_date(data.get("datafabricacao", data.get("datafab"))),
            dataval=cls._parse_date(data.get("datavalidade", data.get("dataval"))),
            codgrupo=data.get("codgrupo", 0),
            nomegrupo=data.get("nomegrupo", ""),
            localizacao=(data.get("localizacao") or data.get("nomeLocalEstoque") or "").strip(),
        )
    
    @staticmethod
    def _parse_date(value) -> Optional[date]:
        """Converte valor para date."""
        if value is None:
            return None
        if isinstance(value, date):
            return value
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, str) and value:
            try:
                return datetime.strptime(value[:10], "%Y-%m-%d").date()
            except ValueError:
                try:
                    return datetime.strptime(value[:10], "%d/%m/%Y").date()
                except ValueError:
                    return None
        return None


class ExportService:
    """
    Serviço responsável pela exportação de carga para coletores de dados.
    
    Layout do arquivo:
    - Registro E: |E|codempresa|nomeempresa|local|
    - Registro V: |V|codusuario|nomeusuario|
    - Registro P: |P|CODEAN|CODPRODUTO|DESCRICAOPRODUTO|UNIDADE|CASASDECIMAIS|
                     CONTROLALOTESN|NUMLOTE|DATAFAB|DATAVAL|CODGRUPO|NOMEGRUPO|LOCALIZACAO|
    
    Formato de data: DDMMAAAA
    Nome do arquivo: CARGA-CODEMPRESA-CODUSUARIO-DATAHORA.txt
    """
    
    # Separador de campos
    SEPARATOR = "|"
    
    # Encoding do arquivo
    ENCODING = "utf-8"
    
    def __init__(self, output_dir: str = None):
        """
        Inicializa o serviço.
        
        Args:
            output_dir: Diretório de saída (padrão: pasta do usuário)
        """
        if output_dir:
            self._output_dir = output_dir
        else:
            # Padrão: Documents/CSCollectManager/Exports
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
    
    def generate_filename(
        self,
        codempresa: int,
        codusuario: int,
        data_hora: datetime = None
    ) -> str:
        """
        Gera nome do arquivo de carga.
        
        Formato: CARGA-CODEMPRESA-CODUSUARIO-DATAHORA.txt
        Exemplo: CARGA-1-001-100220260843.txt
        
        Args:
            codempresa: Código da empresa
            codusuario: Código do usuário
            data_hora: Data/hora (padrão: agora)
            
        Returns:
            Nome do arquivo
        """
        if data_hora is None:
            data_hora = datetime.now()
        
        # Formato: DDMMAAAAHHMM
        timestamp = data_hora.strftime("%d%m%Y%H%M")
        
        # Código do usuário com 3 dígitos
        cod_usuario_str = f"{codusuario:03d}"
        
        return f"CARGA-{codempresa}-{cod_usuario_str}-{timestamp}.txt"
    
    def format_date(self, dt: Optional[date]) -> str:
        """
        Formata data no padrão DDMMAAAA.
        
        Args:
            dt: Data a formatar
            
        Returns:
            String formatada ou vazio
        """
        if dt is None:
            return ""
        return dt.strftime("%d%m%Y")
    
    def build_registro_e(self, empresa: EmpresaInfo) -> str:
        """
        Monta registro E (Empresa).
        
        Layout: |E|codempresa|nomeempresa|local|
        
        Args:
            empresa: Informações da empresa
            
        Returns:
            Linha formatada
        """
        return self.SEPARATOR.join([
            "",  # Início com pipe
            "E",
            str(empresa.codempresa),
            empresa.nomeempresa,
            empresa.local,
            (empresa.cnpj or ""),
            ""   # Final com pipe
        ])
    
    def build_registro_v(self, usuario: UsuarioInfo) -> str:
        """
        Monta registro V (Vendedor/Usuário).
        
        Layout: |V|codusuario|nomeusuario|
        
        Args:
            usuario: Informações do usuário
            
        Returns:
            Linha formatada
        """
        return self.SEPARATOR.join([
            "",  # Início com pipe
            "V",
            str(usuario.codusuario).zfill(3),
            usuario.nomeusuario,
            usuario.id_celular or "",
            ""   # Final com pipe
        ])
    
    def build_registro_p(self, produto: ProdutoExport) -> str:
        """
        Monta registro P (Produto).
        
        Layout: |P|CODEAN|CODPRODUTO|DESCRICAOPRODUTO|UNIDADE|CASASDECIMAIS|
                   CONTROLALOTESN|NUMLOTE|DATAFAB|DATAVAL|CODGRUPO|NOMEGRUPO|LOCALIZACAO|
        
        Args:
            produto: Dados do produto
            
        Returns:
            Linha formatada
        """
        return self.SEPARATOR.join([
            "",  # Início com pipe
            "P",
            produto.codean,
            str(produto.codproduto),
            produto.descricaoproduto,
            produto.unidade,
            str(produto.casasdecimais),
            produto.controlalote,
            produto.numlote,
            self.format_date(produto.datafab),
            self.format_date(produto.dataval),
            str(produto.codgrupo),
            produto.nomegrupo,
            produto.localizacao.strip(),
            ""   # Final com pipe
        ])
    
    def export_carga(
        self,
        empresa: EmpresaInfo,
        usuario: UsuarioInfo,
        produtos: List[Dict[str, Any]],
        output_path: str = None,
        compress: bool = False,
        progress_callback: Optional[Callable[[int, str], None]] = None
    ) -> str:
        """
        Exporta carga completa para arquivo TXT.
        
        Args:
            empresa: Informações da empresa
            usuario: Informações do usuário
            produtos: Lista de produtos (dicionários)
            output_path: Caminho de saída (opcional, usa padrão)
            compress: Se True, compacta em ZIP
            progress_callback: Callback de progresso (percentual, mensagem)
            
        Returns:
            Caminho completo do arquivo gerado
            
        Raises:
            ValueError: Se não houver produtos
            IOError: Se falhar ao gravar arquivo
        """
        if not produtos:
            raise ValueError("Nenhum produto para exportar")
        
        # Define diretório de saída
        if output_path is None:
            output_path = self._output_dir
        
        # Cria diretório se não existir
        os.makedirs(output_path, exist_ok=True)
        
        # Gera nome do arquivo
        filename = self.generate_filename(empresa.codempresa, usuario.codusuario)
        filepath = os.path.join(output_path, filename)
        
        total = len(produtos)
        
        if progress_callback:
            progress_callback(0, "Iniciando exportação...")
        
        try:
            with open(filepath, 'w', encoding=self.ENCODING) as f:
                # Registro E - Empresa
                f.write(self.build_registro_e(empresa) + "\n")
                
                if progress_callback:
                    progress_callback(5, "Gravando dados da empresa...")
                
                # Registro V - Usuário/Vendedor
                f.write(self.build_registro_v(usuario) + "\n")
                
                if progress_callback:
                    progress_callback(10, "Gravando dados do usuário...")
                
                # Registros P - Produtos
                for i, prod_dict in enumerate(produtos):
                    produto = ProdutoExport.from_dict(prod_dict)
                    f.write(self.build_registro_p(produto) + "\n")
                    
                    if progress_callback and total > 0:
                        percentual = 10 + int((i + 1) / total * 85)
                        if (i + 1) % 100 == 0 or i == total - 1:
                            progress_callback(
                                percentual, 
                                f"Exportando produto {i + 1} de {total}..."
                            )
            
            if progress_callback:
                progress_callback(95, "Finalizando...")
            
            # Compacta se solicitado
            if compress:
                zip_path = filepath.replace('.txt', '.zip')
                self._compress_file(filepath, zip_path)
                os.remove(filepath)
                filepath = zip_path
            
            if progress_callback:
                progress_callback(100, "Exportação concluída!")
            
            return filepath
            
        except IOError as e:
            raise IOError(f"Erro ao gravar arquivo: {e}")
    
    def export_carga_from_selection(
        self,
        empresa: EmpresaInfo,
        usuario: UsuarioInfo,
        produtos: List[Dict[str, Any]],
        selected_codes: List[int],
        output_path: str = None,
        compress: bool = False,
        progress_callback: Optional[Callable[[int, str], None]] = None
    ) -> str:
        """
        Exporta apenas produtos selecionados.
        
        Args:
            empresa: Informações da empresa
            usuario: Informações do usuário
            produtos: Lista completa de produtos
            selected_codes: Códigos dos produtos selecionados
            output_path: Caminho de saída
            compress: Se True, compacta em ZIP
            progress_callback: Callback de progresso
            
        Returns:
            Caminho do arquivo gerado
        """
        # Filtra apenas produtos selecionados
        selected_set = set(selected_codes)
        produtos_filtrados = [
            p for p in produtos 
            if p.get("codproduto") in selected_set
        ]
        
        return self.export_carga(
            empresa=empresa,
            usuario=usuario,
            produtos=produtos_filtrados,
            output_path=output_path,
            compress=compress,
            progress_callback=progress_callback
        )
    
    def _compress_file(self, source_path: str, zip_path: str) -> None:
        """
        Compacta arquivo em ZIP.
        
        Args:
            source_path: Caminho do arquivo fonte
            zip_path: Caminho do ZIP de destino
        """
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.write(source_path, os.path.basename(source_path))
    
    def get_export_info(self, filepath: str) -> Dict[str, Any]:
        """
        Retorna informações sobre arquivo exportado.
        
        Args:
            filepath: Caminho do arquivo
            
        Returns:
            Dicionário com informações
        """
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Arquivo não encontrado: {filepath}")
        
        stat = os.stat(filepath)
        
        return {
            "filepath": filepath,
            "filename": os.path.basename(filepath),
            "size_bytes": stat.st_size,
            "size_formatted": self._format_size(stat.st_size),
            "created": datetime.fromtimestamp(stat.st_ctime),
            "modified": datetime.fromtimestamp(stat.st_mtime),
        }
    
    @staticmethod
    def _format_size(size_bytes: int) -> str:
        """Formata tamanho em bytes para exibição."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} TB"
    
    def count_records_in_file(self, filepath: str) -> Dict[str, int]:
        """
        Conta registros em arquivo de carga.
        
        Args:
            filepath: Caminho do arquivo
            
        Returns:
            Dicionário com contagem por tipo
        """
        counts = {"E": 0, "V": 0, "P": 0, "total": 0}
        
        with open(filepath, 'r', encoding=self.ENCODING) as f:
            for line in f:
                line = line.strip()
                if line.startswith("|E|"):
                    counts["E"] += 1
                elif line.startswith("|V|"):
                    counts["V"] += 1
                elif line.startswith("|P|"):
                    counts["P"] += 1
                counts["total"] += 1
        
        return counts


# ===== EXEMPLO DE USO =====
if __name__ == "__main__":
    # Dados de teste
    empresa = EmpresaInfo(
        codempresa=1,
        nomeempresa="Empresa Teste LTDA",
        local="Matriz"
    )
    
    usuario = UsuarioInfo(
        codusuario=1,
        nomeusuario="Administrador"
    )
    
    produtos = [
        {
            "codean": "7891234567890",
            "codproduto": 1,
            "descricaoproduto": "Produto Teste 1",
            "unidade": "UN",
            "casasdecimais": 3,
            "controlalote": False,
            "numlote": "",
            "datafabricacao": None,
            "datavalidade": None,
            "codgrupo": 1,
            "nomegrupo": "Bebidas",
            "localizacao": "A1-01"
        },
        {
            "codean": "7891234567891",
            "codproduto": 2,
            "descricaoproduto": "Produto Teste 2 com Lote",
            "unidade": "KG",
            "casasdecimais": 3,
            "controlalote": True,
            "numlote": "LT2024001",
            "datafabricacao": date(2024, 1, 15),
            "datavalidade": date(2025, 1, 15),
            "codgrupo": 2,
            "nomegrupo": "Alimentos",
            "localizacao": "B2-03"
        },
    ]
    
    # Exporta
    service = ExportService()
    
    def progress(pct, msg):
        print(f"[{pct:3d}%] {msg}")
    
    filepath = service.export_carga(
        empresa=empresa,
        usuario=usuario,
        produtos=produtos,
        progress_callback=progress
    )
    
    print(f"\nArquivo gerado: {filepath}")
    
    # Mostra conteúdo
    print("\nConteúdo do arquivo:")
    print("-" * 80)
    with open(filepath, 'r', encoding='utf-8') as f:
        print(f.read())
    
    # Info do arquivo
    info = service.get_export_info(filepath)
    print(f"\nTamanho: {info['size_formatted']}")
    
    counts = service.count_records_in_file(filepath)
    print(f"Registros: {counts}")
