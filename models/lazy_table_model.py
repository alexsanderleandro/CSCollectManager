"""
lazy_table_model.py
===================
Modelo de tabela com lazy loading para alta performance.

Suporta:
- 50.000+ registros
- Carregamento sob demanda
- Paginação virtual
- Cache de dados
"""

from typing import List, Dict, Any, Optional, Callable
from datetime import date, datetime

from PySide6.QtCore import (
    Qt, QAbstractTableModel, QModelIndex,
    QSortFilterProxyModel, Signal, QTimer
)
from PySide6.QtGui import QColor, QBrush, QFont
from dataclasses import dataclass


@dataclass
class ProductData:
    """Estrutura de dados para produto (otimizada)."""
    codproduto: int
    descricaoproduto: str
    codeanunidade: str
    codgrupo: int
    nomegrupo: str
    nomeLocalEstoque: str
    numlote: str
    datafabricacao: Optional[date]
    datavalidade: Optional[date]
    # Campos adicionais
    estoque: float = 0.0
    customedio: float = 0.0
    precovenda: float = 0.0
    
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
            estoque=float(data.get("estoque", 0) or 0),
            customedio=float(data.get("customedio", 0) or 0),
            precovenda=float(data.get("precovenda", 0) or 0),
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


class LazyTableModel(QAbstractTableModel):
    """
    Modelo de tabela com lazy loading.
    
    Otimizado para:
    - 50.000+ registros
    - Carregamento incremental
    - Cache inteligente
    - Atualização eficiente da UI
    
    Signals:
        data_changed: Emitido quando dados mudam
        loading_started: Início do carregamento
        loading_finished: Fim do carregamento (total)
        loading_progress: Progresso (loaded, total)
        request_more_data: Solicita mais dados (offset)
    """
    
    data_changed = Signal()
    loading_started = Signal()
    loading_finished = Signal(int)
    loading_progress = Signal(int, int)
    request_more_data = Signal(int)  # offset
    
    # Definição das colunas
    COLUMNS = [
        ("codproduto",        "Código",           80),
        ("descricaoproduto",  "Descrição",        300),
        ("codeanunidade",     "Cód. EAN", 130),
        ("codgrupo",          "Cód. grupo",        110),
        ("nomegrupo",         "Grupo",             150),
        ("nomeLocalEstoque",  "Local estoque",     130),
        ("numlote",           "Lote",              110),
        ("datafabricacao",    "Data fabricação",   120),
        ("datavalidade",      "Data validade",      100),
    ]
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Dados
        self._data: List[ProductData] = []
        self._raw_data: List[Dict[str, Any]] = []  # Preserva dicts originais para exportação
        self._total_records = 0
        self._loaded_records = 0
        self._is_loading = False
        
        # Configuração de colunas
        self._column_keys = [col[0] for col in self.COLUMNS]
        self._column_headers = [col[1] for col in self.COLUMNS]
        self._column_widths = [col[2] for col in self.COLUMNS]
        self._col_count = len(self.COLUMNS)
        
        # Cores para destaque
        self._color_expired = QColor("#ff6b6b")
        self._color_near_expiry = QColor("#ffa94d")
        self._color_ok = QColor("#69db7c")
        
        # Lazy loading config
        self._page_size = 1000
        self._load_threshold = 500  # Carregar mais quando restam X registros
        self._prefetch_enabled = True
    
    @property
    def total_records(self) -> int:
        """Total de registros disponíveis."""
        return self._total_records
    
    @property
    def loaded_records(self) -> int:
        """Registros já carregados."""
        return self._loaded_records
    
    @property
    def is_fully_loaded(self) -> bool:
        """Verifica se todos os dados estão carregados."""
        return self._loaded_records >= self._total_records
    
    @property
    def is_loading(self) -> bool:
        """Verifica se está carregando."""
        return self._is_loading
    
    def set_page_size(self, size: int):
        """Define tamanho da página de carregamento."""
        self._page_size = max(100, size)
    
    def set_load_threshold(self, threshold: int):
        """Define limiar para carregar mais dados."""
        self._load_threshold = max(50, threshold)
    
    # ==========================================
    # QAbstractTableModel Implementation
    # ==========================================
    
    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        """Retorna número de linhas carregadas."""
        if parent.isValid():
            return 0
        return self._loaded_records
    
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
        
        if row < 0 or row >= self._loaded_records:
            return None
        if col < 0 or col >= self._col_count:
            return None
        
        # Verifica se precisa carregar mais (lazy loading)
        if self._prefetch_enabled and not self._is_loading:
            remaining = self._loaded_records - row
            if remaining < self._load_threshold and not self.is_fully_loaded:
                self.request_more_data.emit(self._loaded_records)
        
        product = self._data[row]
        column_key = self._column_keys[col]
        
        if role == Qt.ItemDataRole.DisplayRole:
            return self._get_display_value(product, column_key)
        
        elif role == Qt.ItemDataRole.TextAlignmentRole:
            if column_key == "codproduto":
                return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            elif column_key in (
                "codeanunidade", "codgrupo", "nomegrupo",
                "nomeLocalEstoque", "numlote",
                "datafabricacao", "datavalidade",
            ):
                return Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter
            return Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        
        elif role == Qt.ItemDataRole.ForegroundRole:
            if column_key == "datavalidade" and product.datavalidade:
                return self._get_expiry_color(product.datavalidade)
        
        elif role == Qt.ItemDataRole.UserRole:
            return product
        
        elif role == Qt.ItemDataRole.UserRole + 1:
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
        
        elif role == Qt.ItemDataRole.TextAlignmentRole:
            if orientation == Qt.Orientation.Horizontal and 0 <= section < self._col_count:
                key = self._column_keys[section]
                if key == "codproduto":
                    return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                elif key in (
                    "codeanunidade", "codgrupo", "nomegrupo",
                    "nomeLocalEstoque", "numlote",
                    "datafabricacao", "datavalidade",
                ):
                    return Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter
                return Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter

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
    
    # ==========================================
    # Data Management Methods
    # ==========================================
    
    def set_total_records(self, total: int):
        """Define total de registros esperados."""
        self._total_records = total
    
    def begin_loading(self):
        """Inicia ciclo de carregamento."""
        self._is_loading = True
        self.loading_started.emit()
    
    def end_loading(self):
        """Finaliza ciclo de carregamento."""
        self._is_loading = False
        self.loading_finished.emit(self._loaded_records)
        self.data_changed.emit()
    
    def clear(self):
        """Limpa todos os dados."""
        self.beginResetModel()
        self._data.clear()
        self._raw_data.clear()
        self._loaded_records = 0
        self._total_records = 0
        self.endResetModel()
        self.data_changed.emit()
    
    def set_data(self, products: List[Dict[str, Any]], total: int = None):
        """
        Define dados do modelo (substitui existentes).
        
        Args:
            products: Lista de dicionários
            total: Total de registros (opcional)
        """
        self.beginResetModel()
        
        self._raw_data = list(products)  # Preserva dicts originais
        self._data = [ProductData.from_dict(p) for p in products]
        self._loaded_records = len(self._data)
        self._total_records = total if total is not None else self._loaded_records
        
        self.endResetModel()
        self.loading_progress.emit(self._loaded_records, self._total_records)
        self.data_changed.emit()
    
    def append_data(self, products: List[Dict[str, Any]]):
        """
        Adiciona dados (carregamento incremental).
        
        Args:
            products: Lista de dicionários
        """
        if not products:
            return
        
        first_row = self._loaded_records
        last_row = first_row + len(products) - 1
        
        self.beginInsertRows(QModelIndex(), first_row, last_row)
        
        self._raw_data.extend(products)  # Preserva dicts originais
        new_data = [ProductData.from_dict(p) for p in products]
        self._data.extend(new_data)
        self._loaded_records = len(self._data)
        
        self.endInsertRows()
        self.loading_progress.emit(self._loaded_records, self._total_records)
    
    def get_product(self, row: int) -> Optional[ProductData]:
        """Retorna produto por índice."""
        if 0 <= row < self._loaded_records:
            return self._data[row]
        return None
    
    def get_all_products(self) -> List[ProductData]:
        """Retorna todos os produtos carregados."""
        return self._data.copy()
    
    def get_selected_products(self, rows: List[int]) -> List[ProductData]:
        """Retorna produtos das linhas selecionadas."""
        return [self._data[r] for r in rows if 0 <= r < self._loaded_records]
    
    def get_all_codprodutos(self) -> List[int]:
        """Retorna lista de códigos de todos os produtos."""
        return [p.codproduto for p in self._data]

    def get_selected_dicts(self, rows: List[int]) -> List[Dict[str, Any]]:
        """
        Retorna dicts originais das linhas selecionadas.
        
        Usa os dados brutos preservados na carga para não perder
        campos como 'unidade', 'codfornecedor', etc.
        
        Args:
            rows: Linhas selecionadas (índices do modelo fonte)
        """
        return [
            self._raw_data[r]
            for r in rows
            if 0 <= r < len(self._raw_data)
        ]

    def get_all_dicts(self) -> List[Dict[str, Any]]:
        """Retorna todos os dicts originais carregados."""
        return self._raw_data.copy()


class LazySortFilterProxyModel(QSortFilterProxyModel):
    """
    Proxy model com suporte a lazy loading.
    
    Mantém performance mesmo com filtros aplicados.
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self._filter_text = ""
        self._filter_columns: List[int] = []
        self._filter_timer = QTimer()
        self._filter_timer.setSingleShot(True)
        self._filter_timer.timeout.connect(self._apply_filter)
        self._pending_filter = ""
        
        # Configuração
        self.setSortRole(Qt.ItemDataRole.UserRole + 1)
        self.setDynamicSortFilter(False)  # Desativa para performance
        self.setSortCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
    
    def set_filter_text(self, text: str, delay_ms: int = 300):
        """
        Define texto do filtro com debounce.
        
        Args:
            text: Texto a filtrar
            delay_ms: Delay em milissegundos
        """
        self._pending_filter = text.lower()
        self._filter_timer.start(delay_ms)
    
    def set_filter_text_immediate(self, text: str):
        """Define filtro imediatamente sem debounce."""
        self._filter_text = text.lower()
        self.invalidateFilter()
    
    def _apply_filter(self):
        """Aplica filtro pendente."""
        self._filter_text = self._pending_filter
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
        
        if left_data is None and right_data is None:
            return False
        if left_data is None:
            return True
        if right_data is None:
            return False
        
        if isinstance(left_data, (int, float)) and isinstance(right_data, (int, float)):
            return left_data < right_data
        
        if isinstance(left_data, date) and isinstance(right_data, date):
            return left_data < right_data
        
        return str(left_data).lower() < str(right_data).lower()
    
    def sort(self, column: int, order: Qt.SortOrder = Qt.SortOrder.AscendingOrder):
        """Ordena dados."""
        self.setDynamicSortFilter(False)
        super().sort(column, order)
    
    def get_source_rows(self, proxy_rows: List[int]) -> List[int]:
        """Converte índices do proxy para índices da fonte."""
        return [self.mapToSource(self.index(r, 0)).row() for r in proxy_rows]
