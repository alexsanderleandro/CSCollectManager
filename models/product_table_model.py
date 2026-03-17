"""
product_table_model.py
======================
Modelo de dados para QTableView de produtos.
Otimizado para alta performance com milhares de registros.
"""

from typing import List, Dict, Any, Optional
from PySide6.QtCore import (
    Qt, QAbstractTableModel, QModelIndex, 
    QSortFilterProxyModel, Signal
)
from PySide6.QtGui import QColor, QBrush, QFont
from dataclasses import dataclass
from datetime import date, datetime


@dataclass
class ProductData:
    """Estrutura de dados para produto."""
    codproduto: int
    descricaoproduto: str
    codeanunidade: str
    codgrupo: int
    nomegrupo: str
    nomeLocalEstoque: str
    numlote: str
    datafabricacao: Optional[date]
    datavalidade: Optional[date]
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProductData":
        """Cria instância a partir de dicionário."""
        return cls(
            codproduto=data.get("codproduto", 0),
            descricaoproduto=data.get("descricaoproduto", ""),
            codeanunidade=data.get("codeanunidade", ""),
            codgrupo=data.get("codgrupo", 0),
            nomegrupo=data.get("nomegrupo", ""),
            nomeLocalEstoque=data.get("nomeLocalEstoque", ""),
            numlote=data.get("numlote", ""),
            datafabricacao=cls._parse_date(data.get("datafabricacao")),
            datavalidade=cls._parse_date(data.get("datavalidade")),
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


class ProductTableModel(QAbstractTableModel):
    """
    Modelo de tabela para produtos.
    
    Otimizado para:
    - Alta performance com milhares de registros
    - Acesso direto aos dados sem cópia
    - Atualização eficiente
    
    Signals:
        data_changed: Emitido quando dados são alterados
    """
    
    data_changed = Signal()
    
    # Definição das colunas
    COLUMNS = [
        ("codproduto", "Código", 80),
        ("descricaoproduto", "Descrição", 300),
        ("codeanunidade", "Cód. EAN/Unidade", 120),
        ("codgrupo", "Cód. Grupo", 80),
        ("nomegrupo", "Grupo", 150),
        ("nomeLocalEstoque", "Local Estoque", 150),
        ("numlote", "Lote", 100),
        ("datafabricacao", "Dt. Fabricação", 100),
        ("datavalidade", "Dt. Validade", 100),
    ]
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._data: List[ProductData] = []
        self._column_keys = [col[0] for col in self.COLUMNS]
        self._column_headers = [col[1] for col in self.COLUMNS]
        self._column_widths = [col[2] for col in self.COLUMNS]
        
        # Cache para performance
        self._row_count = 0
        self._col_count = len(self.COLUMNS)
        
        # Cores para destaque
        self._color_expired = QColor("#ff6b6b")  # Vermelho para vencido
        self._color_near_expiry = QColor("#ffa94d")  # Laranja para próximo do vencimento
        self._color_ok = QColor("#69db7c")  # Verde para OK
    
    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        """Retorna número de linhas."""
        if parent.isValid():
            return 0
        return self._row_count
    
    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        """Retorna número de colunas."""
        if parent.isValid():
            return 0
        return self._col_count
    
    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        """Retorna dados para exibição."""
        if not index.isValid():
            return None
        
        row = index.row()
        col = index.column()
        
        if row < 0 or row >= self._row_count:
            return None
        if col < 0 or col >= self._col_count:
            return None
        
        product = self._data[row]
        column_key = self._column_keys[col]
        
        if role == Qt.ItemDataRole.DisplayRole:
            return self._get_display_value(product, column_key)
        
        elif role == Qt.ItemDataRole.TextAlignmentRole:
            # Alinhamento por tipo de coluna
            if column_key in ("codproduto", "codgrupo"):
                return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            elif column_key in ("datafabricacao", "datavalidade"):
                return Qt.AlignmentFlag.AlignCenter
            return Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        
        elif role == Qt.ItemDataRole.ForegroundRole:
            # Cor para data de validade
            if column_key == "datavalidade" and product.datavalidade:
                return self._get_expiry_color(product.datavalidade)
        
        elif role == Qt.ItemDataRole.UserRole:
            # Retorna o objeto completo para uso externo
            return product
        
        elif role == Qt.ItemDataRole.UserRole + 1:
            # Retorna valor raw para ordenação
            return getattr(product, column_key, None)
        
        return None
    
    def _get_display_value(self, product: ProductData, column_key: str) -> str:
        """Retorna valor formatado para exibição."""
        value = getattr(product, column_key, None)
        
        if value is None:
            return ""
        
        if column_key in ("datafabricacao", "datavalidade"):
            if isinstance(value, date):
                return value.strftime("%d/%m/%Y")
            return ""
        
        return str(value)
    
    def _get_expiry_color(self, expiry_date: date) -> QBrush:
        """Retorna cor baseada na data de validade."""
        today = date.today()
        
        if expiry_date < today:
            return QBrush(self._color_expired)
        
        days_to_expiry = (expiry_date - today).days
        if days_to_expiry <= 30:
            return QBrush(self._color_near_expiry)
        
        return QBrush(self._color_ok)
    
    def headerData(
        self, 
        section: int, 
        orientation: Qt.Orientation, 
        role: int = Qt.ItemDataRole.DisplayRole
    ):
        """Retorna dados do cabeçalho."""
        if role == Qt.ItemDataRole.DisplayRole:
            if orientation == Qt.Orientation.Horizontal:
                if 0 <= section < self._col_count:
                    return self._column_headers[section]
            else:
                return str(section + 1)
        
        elif role == Qt.ItemDataRole.FontRole:
            if orientation == Qt.Orientation.Horizontal:
                font = QFont()
                font.setBold(True)
                return font
        
        return None
    
    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        """Retorna flags do item."""
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
    
    def get_column_width(self, column: int) -> int:
        """Retorna largura sugerida da coluna."""
        if 0 <= column < len(self._column_widths):
            return self._column_widths[column]
        return 100
    
    def get_column_key(self, column: int) -> str:
        """Retorna chave da coluna."""
        if 0 <= column < len(self._column_keys):
            return self._column_keys[column]
        return ""
    
    # ===== MÉTODOS DE MANIPULAÇÃO DE DADOS =====
    
    def set_data(self, products: List[Dict[str, Any]]):
        """
        Define dados do modelo.
        
        Args:
            products: Lista de dicionários com dados dos produtos
        """
        self.beginResetModel()
        
        # Converte dicionários para objetos
        self._data = [ProductData.from_dict(p) for p in products]
        self._row_count = len(self._data)
        
        self.endResetModel()
        self.data_changed.emit()
    
    def append_data(self, products: List[Dict[str, Any]]):
        """
        Adiciona dados ao modelo (para carregamento incremental).
        
        Args:
            products: Lista de dicionários com dados dos produtos
        """
        if not products:
            return
        
        first_row = self._row_count
        last_row = first_row + len(products) - 1
        
        self.beginInsertRows(QModelIndex(), first_row, last_row)
        
        new_data = [ProductData.from_dict(p) for p in products]
        self._data.extend(new_data)
        self._row_count = len(self._data)
        
        self.endInsertRows()
        self.data_changed.emit()
    
    def clear(self):
        """Limpa todos os dados."""
        self.beginResetModel()
        self._data.clear()
        self._row_count = 0
        self.endResetModel()
        self.data_changed.emit()
    
    def get_product(self, row: int) -> Optional[ProductData]:
        """Retorna produto por índice de linha."""
        if 0 <= row < self._row_count:
            return self._data[row]
        return None
    
    def get_all_products(self) -> List[ProductData]:
        """Retorna todos os produtos."""
        return self._data.copy()


class ProductSortFilterProxyModel(QSortFilterProxyModel):
    """
    Proxy model para ordenação e filtro de produtos.
    
    Suporta:
    - Ordenação por qualquer coluna
    - Filtro por texto em múltiplas colunas
    - Performance otimizada
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._filter_text = ""
        self._filter_columns = []  # Colunas para aplicar filtro
        
        # Configura ordenação
        self.setSortRole(Qt.ItemDataRole.UserRole + 1)
        self.setDynamicSortFilter(True)
        self.setSortCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
    
    def set_filter_text(self, text: str):
        """Define texto do filtro."""
        self._filter_text = text.lower()
        self.invalidateFilter()
    
    def set_filter_columns(self, columns: List[int]):
        """Define colunas onde o filtro será aplicado."""
        self._filter_columns = columns
        self.invalidateFilter()
    
    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        """Verifica se linha passa no filtro."""
        if not self._filter_text:
            return True
        
        source_model = self.sourceModel()
        if not source_model:
            return True
        
        # Se nenhuma coluna específica, busca em todas
        columns_to_check = self._filter_columns or range(source_model.columnCount())
        
        for col in columns_to_check:
            index = source_model.index(source_row, col, source_parent)
            data = source_model.data(index, Qt.ItemDataRole.DisplayRole)
            if data and self._filter_text in str(data).lower():
                return True
        
        return False
    
    def lessThan(self, left: QModelIndex, right: QModelIndex) -> bool:
        """Comparação para ordenação."""
        left_data = self.sourceModel().data(left, Qt.ItemDataRole.UserRole + 1)
        right_data = self.sourceModel().data(right, Qt.ItemDataRole.UserRole + 1)
        
        # Trata None
        if left_data is None and right_data is None:
            return False
        if left_data is None:
            return True
        if right_data is None:
            return False
        
        # Compara por tipo
        if isinstance(left_data, (int, float)) and isinstance(right_data, (int, float)):
            return left_data < right_data
        
        if isinstance(left_data, date) and isinstance(right_data, date):
            return left_data < right_data
        
        # Compara como string
        return str(left_data).lower() < str(right_data).lower()
