"""
database_models.py
==================
Modelos SQLAlchemy para as tabelas do SQL Server.

Utiliza SQLAlchemy Declarative ORM para mapeamento objeto-relacional.
"""

from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List

from sqlalchemy import (
    Column, Integer, String, Numeric, DateTime, Date,
    Boolean, Text, ForeignKey, Index, SmallInteger,
    Float, LargeBinary, UniqueConstraint
)
from sqlalchemy.orm import relationship, declarative_base, Mapped, mapped_column
from sqlalchemy.ext.hybrid import hybrid_property

# Base declarativa
Base = declarative_base()


# ============================================================================
# Tabela: empresas
# ============================================================================

class Empresa(Base):
    """Modelo para tabela empresas."""
    
    __tablename__ = "empresas"
    
    # Chave primária
    codempresa = Column(Integer, primary_key=True, autoincrement=False)
    
    # Dados da empresa
    nomeempresa = Column(String(100), nullable=False)
    razaosocial = Column(String(100), nullable=True)
    cnpj = Column(String(20), nullable=True)
    inscricaoestadual = Column(String(20), nullable=True)
    inscricaomunicipal = Column(String(20), nullable=True)
    
    # Endereço
    endereco = Column(String(100), nullable=True)
    numero = Column(String(20), nullable=True)
    complemento = Column(String(50), nullable=True)
    bairro = Column(String(50), nullable=True)
    cidade = Column(String(50), nullable=True)
    uf = Column(String(2), nullable=True)
    cep = Column(String(10), nullable=True)
    
    # Contato
    telefone = Column(String(20), nullable=True)
    email = Column(String(100), nullable=True)
    
    # Controle
    inativosn = Column(SmallInteger, default=0)
    datacadastro = Column(DateTime, default=datetime.now)
    
    # Relacionamentos
    produtos_estoque = relationship("ProdutoEstoque", back_populates="empresa")
    
    def __repr__(self):
        return f"<Empresa(codempresa={self.codempresa}, nome='{self.nomeempresa}')>"


# ============================================================================
# Tabela: usuarios
# ============================================================================

class Usuario(Base):
    """Modelo para tabela usuarios."""
    
    __tablename__ = "usuarios"
    
    # Chave primária
    codusuario = Column(Integer, primary_key=True, autoincrement=True)
    
    # Dados do usuário
    nomeusuario = Column(String(50), nullable=False, unique=True)
    senha = Column(String(100), nullable=True)
    nomecompleto = Column(String(100), nullable=True)
    email = Column(String(100), nullable=True)
    
    # Permissões
    pdvgerentesn = Column(SmallInteger, default=0)
    administradorsn = Column(SmallInteger, default=0)
    
    # Controle
    inativosn = Column(SmallInteger, default=0)
    datacadastro = Column(DateTime, default=datetime.now)
    ultimoacesso = Column(DateTime, nullable=True)
    
    def __repr__(self):
        return f"<Usuario(codusuario={self.codusuario}, nome='{self.nomeusuario}')>"
    
    @hybrid_property
    def is_active(self) -> bool:
        """Verifica se usuário está ativo."""
        return self.inativosn == 0
    
    @hybrid_property
    def is_manager(self) -> bool:
        """Verifica se usuário é gerente."""
        return self.pdvgerentesn == 1


# ============================================================================
# Tabela: vendedores
# ============================================================================

class Vendedor(Base):
    """Modelo para tabela vendedores."""
    
    __tablename__ = "vendedores"
    
    # Chave primária
    codvendedor = Column(Integer, primary_key=True, autoincrement=True)
    
    # Dados do vendedor
    nomevendedor = Column(String(100), nullable=False)
    apelido = Column(String(50), nullable=True)
    cpf = Column(String(14), nullable=True)
    rg = Column(String(20), nullable=True)
    
    # Contato
    telefone = Column(String(20), nullable=True)
    celular = Column(String(20), nullable=True)
    email = Column(String(100), nullable=True)
    
    # Endereço
    endereco = Column(String(100), nullable=True)
    bairro = Column(String(50), nullable=True)
    cidade = Column(String(50), nullable=True)
    uf = Column(String(2), nullable=True)
    cep = Column(String(10), nullable=True)
    
    # Comissão
    percentualcomissao = Column(Numeric(10, 4), default=0)
    
    # Controle
    inativosn = Column(SmallInteger, default=0)
    datacadastro = Column(DateTime, default=datetime.now)
    
    # Vínculo com usuário (opcional)
    codusuario = Column(Integer, ForeignKey("usuarios.codusuario"), nullable=True)
    
    def __repr__(self):
        return f"<Vendedor(codvendedor={self.codvendedor}, nome='{self.nomevendedor}')>"


# ============================================================================
# Tabela: tipocliente
# ============================================================================

class TipoCliente(Base):
    """Modelo para tabela tipocliente."""
    
    __tablename__ = "tipocliente"
    
    # Chave primária
    codtipocliente = Column(Integer, primary_key=True, autoincrement=True)
    
    # Dados
    descricao = Column(String(50), nullable=False)
    percentualdesconto = Column(Numeric(10, 4), default=0)
    percentualacrescimo = Column(Numeric(10, 4), default=0)
    
    # Controle
    inativosn = Column(SmallInteger, default=0)
    
    def __repr__(self):
        return f"<TipoCliente(codtipocliente={self.codtipocliente}, descricao='{self.descricao}')>"


# ============================================================================
# Tabela: tipoproduto
# ============================================================================

class TipoProduto(Base):
    """Modelo para tabela tipoproduto."""
    
    __tablename__ = "tipoproduto"
    
    # Chave primária
    codtipoproduto = Column(Integer, primary_key=True, autoincrement=True)
    
    # Dados
    descricao = Column(String(50), nullable=False)
    sigla = Column(String(5), nullable=True)
    
    # Configurações
    controlaestoque = Column(SmallInteger, default=1)
    permitevenda = Column(SmallInteger, default=1)
    
    # Controle
    inativosn = Column(SmallInteger, default=0)
    
    # Relacionamentos
    produtos = relationship("Produto", back_populates="tipo_produto")
    
    def __repr__(self):
        return f"<TipoProduto(codtipoproduto={self.codtipoproduto}, descricao='{self.descricao}')>"


# ============================================================================
# Tabela: GrupoEstoque
# ============================================================================

class GrupoEstoque(Base):
    """Modelo para tabela GrupoEstoque."""
    
    __tablename__ = "grupoestoque"
    
    # Chave primária
    codgrupo = Column(Integer, primary_key=True, autoincrement=True)
    
    # Dados do grupo
    descricaogrupo = Column(String(100), nullable=False)
    sigla = Column(String(10), nullable=True)
    
    # Hierarquia (grupo pai)
    codgrupopai = Column(Integer, ForeignKey("grupoestoque.codgrupo"), nullable=True)
    
    # Configurações
    margempadrao = Column(Numeric(10, 4), default=0)
    comissaopadrao = Column(Numeric(10, 4), default=0)
    
    # Controle
    inativosn = Column(SmallInteger, default=0)
    datacadastro = Column(DateTime, default=datetime.now)
    
    # Relacionamentos
    grupo_pai = relationship("GrupoEstoque", remote_side=[codgrupo], backref="subgrupos")
    produtos = relationship("Produto", back_populates="grupo")
    
    def __repr__(self):
        return f"<GrupoEstoque(codgrupo={self.codgrupo}, descricao='{self.descricaogrupo}')>"


# ============================================================================
# Tabela: LocalEstoque
# ============================================================================

class LocalEstoque(Base):
    """Modelo para tabela LocalEstoque."""
    
    __tablename__ = "localestoque"
    
    # Chave primária
    codlocal = Column(Integer, primary_key=True, autoincrement=True)
    
    # Dados do local
    descricaolocal = Column(String(100), nullable=False)
    sigla = Column(String(10), nullable=True)
    
    # Endereço/localização física
    corredor = Column(String(20), nullable=True)
    prateleira = Column(String(20), nullable=True)
    posicao = Column(String(20), nullable=True)
    
    # Empresa (se for por empresa)
    codempresa = Column(Integer, ForeignKey("empresas.codempresa"), nullable=True)
    
    # Tipo de local
    tipolocal = Column(String(20), nullable=True)  # 'DEPOSITO', 'LOJA', 'VITRINE', etc.
    
    # Controle
    inativosn = Column(SmallInteger, default=0)
    datacadastro = Column(DateTime, default=datetime.now)
    
    def __repr__(self):
        return f"<LocalEstoque(codlocal={self.codlocal}, descricao='{self.descricaolocal}')>"


# ============================================================================
# Tabela: produtos
# ============================================================================

class Produto(Base):
    """Modelo para tabela produtos."""
    
    __tablename__ = "produtos"
    
    # Chave primária
    codproduto = Column(Integer, primary_key=True, autoincrement=True)
    
    # Descrições
    descricaoproduto = Column(String(200), nullable=False)
    descricaoreduzida = Column(String(50), nullable=True)
    descricaoetiqueta = Column(String(100), nullable=True)
    
    # Unidades
    unidade = Column(String(5), nullable=True, default="UN")
    unidadecompra = Column(String(5), nullable=True)
    fatorconversao = Column(Numeric(15, 6), default=1)
    
    # Códigos
    codigobarras = Column(String(50), nullable=True, index=True)
    codeanunidade = Column(String(14), nullable=True)
    codigofabricante = Column(String(50), nullable=True)
    referencia = Column(String(50), nullable=True)
    
    # Classificação
    codgrupo = Column(Integer, ForeignKey("grupoestoque.codgrupo"), nullable=True)
    codtipoproduto = Column(Integer, ForeignKey("tipoproduto.codtipoproduto"), nullable=True)
    
    # Preços
    precocusto = Column(Numeric(18, 6), default=0)
    precocompra = Column(Numeric(18, 6), default=0)
    precovenda = Column(Numeric(18, 6), default=0)
    precoatacado = Column(Numeric(18, 6), default=0)
    margemlucro = Column(Numeric(10, 4), default=0)
    
    # Estoque
    controlaestoque = Column(SmallInteger, default=1)
    estoqueminimo = Column(Numeric(15, 4), default=0)
    estoquemaximo = Column(Numeric(15, 4), default=0)
    
    # Peso
    pesobruto = Column(Numeric(15, 6), default=0)
    pesoliquido = Column(Numeric(15, 6), default=0)
    pesovariavel = Column(SmallInteger, default=0)
    
    # Fiscal
    ncm = Column(String(10), nullable=True)
    cest = Column(String(10), nullable=True)
    cfop = Column(String(5), nullable=True)
    cst = Column(String(5), nullable=True)
    origem = Column(String(1), nullable=True, default="0")
    
    # Alíquotas
    aliquotaicms = Column(Numeric(10, 4), default=0)
    aliquotaipi = Column(Numeric(10, 4), default=0)
    aliquotapis = Column(Numeric(10, 4), default=0)
    aliquotacofins = Column(Numeric(10, 4), default=0)
    
    # Configurações
    vendasn = Column(SmallInteger, default=1)
    comprasn = Column(SmallInteger, default=1)
    balancasn = Column(SmallInteger, default=0)
    
    # Controle
    inativosn = Column(SmallInteger, default=0)
    datacadastro = Column(DateTime, default=datetime.now)
    dataalteracao = Column(DateTime, nullable=True, onupdate=datetime.now)
    
    # Observações
    observacoes = Column(Text, nullable=True)
    
    # Relacionamentos
    grupo = relationship("GrupoEstoque", back_populates="produtos")
    tipo_produto = relationship("TipoProduto", back_populates="produtos")
    estoques = relationship("ProdutoEstoque", back_populates="produto")
    lotes = relationship("ProdutoLote", back_populates="produto")
    anexos = relationship("ProdutoAnexo", back_populates="produto")
    
    # Índices
    __table_args__ = (
        Index("idx_produtos_codigobarras", "codigobarras"),
        Index("idx_produtos_descricao", "descricaoproduto"),
        Index("idx_produtos_grupo", "codgrupo"),
    )
    
    def __repr__(self):
        return f"<Produto(codproduto={self.codproduto}, descricao='{self.descricaoproduto[:30]}')>"
    
    @hybrid_property
    def is_active(self) -> bool:
        """Verifica se produto está ativo."""
        return self.inativosn == 0
    
    @hybrid_property
    def controla_estoque(self) -> bool:
        """Verifica se controla estoque."""
        return self.controlaestoque == 1


# ============================================================================
# Tabela: produtosestoque
# ============================================================================

class ProdutoEstoque(Base):
    """Modelo para tabela produtosestoque."""
    
    __tablename__ = "produtosestoque"
    
    # Chave primária composta
    codempresa = Column(
        Integer, 
        ForeignKey("empresas.codempresa"), 
        primary_key=True
    )
    codproduto = Column(
        Integer, 
        ForeignKey("produtos.codproduto"), 
        primary_key=True
    )
    
    # Situação e localização
    situacao = Column(String(20), nullable=True, default="A")  # A=Ativo, I=Inativo
    localizacao = Column(String(50), nullable=True)
    codlocal = Column(Integer, ForeignKey("localestoque.codlocal"), nullable=True)
    
    # Estoque
    estoquedeposito = Column(Numeric(15, 4), default=0)
    estoqueloja = Column(Numeric(15, 4), default=0)
    estoquereservado = Column(Numeric(15, 4), default=0)
    estoqueencomenda = Column(Numeric(15, 4), default=0)
    
    # Estoque calculado (saldo disponível)
    @hybrid_property
    def estoque_disponivel(self) -> Decimal:
        """Calcula estoque disponível."""
        deposito = self.estoquedeposito or Decimal("0")
        loja = self.estoqueloja or Decimal("0")
        reservado = self.estoquereservado or Decimal("0")
        return deposito + loja - reservado
    
    # Fornecedor preferencial
    codfornecedor = Column(Integer, nullable=True)
    
    # Configurações
    compoevenda = Column(SmallInteger, default=0)
    encomendasn = Column(SmallInteger, default=0)
    
    # Custos específicos da empresa
    customedio = Column(Numeric(18, 6), default=0)
    ultimocusto = Column(Numeric(18, 6), default=0)
    
    # Preços específicos da empresa (se diferentes do produto)
    precovenda = Column(Numeric(18, 6), nullable=True)
    precoatacado = Column(Numeric(18, 6), nullable=True)
    
    # Datas de movimento
    dataultimavenda = Column(DateTime, nullable=True)
    dataultimacompra = Column(DateTime, nullable=True)
    dataultimomovimento = Column(DateTime, nullable=True)
    
    # Controle
    datacadastro = Column(DateTime, default=datetime.now)
    dataalteracao = Column(DateTime, nullable=True, onupdate=datetime.now)
    
    # Relacionamentos
    empresa = relationship("Empresa", back_populates="produtos_estoque")
    produto = relationship("Produto", back_populates="estoques")
    
    # Índices
    __table_args__ = (
        Index("idx_prodestoque_empresa", "codempresa"),
        Index("idx_prodestoque_produto", "codproduto"),
        Index("idx_prodestoque_situacao", "situacao"),
    )
    
    def __repr__(self):
        return f"<ProdutoEstoque(empresa={self.codempresa}, produto={self.codproduto})>"


# ============================================================================
# Tabela: ProdutosLote
# ============================================================================

class ProdutoLote(Base):
    """Modelo para tabela ProdutosLote."""
    
    __tablename__ = "produtoslote"
    
    # Chave primária
    codlote = Column(Integer, primary_key=True, autoincrement=True)
    
    # Produto
    codproduto = Column(
        Integer, 
        ForeignKey("produtos.codproduto"), 
        nullable=False,
        index=True
    )
    
    # Empresa
    codempresa = Column(
        Integer, 
        ForeignKey("empresas.codempresa"), 
        nullable=True
    )
    
    # Dados do lote
    numerolote = Column(String(50), nullable=False)
    descricaolote = Column(String(100), nullable=True)
    
    # Datas
    datafabricacao = Column(Date, nullable=True)
    datavalidade = Column(Date, nullable=True)
    dataentrada = Column(DateTime, default=datetime.now)
    
    # Quantidades
    quantidadeentrada = Column(Numeric(15, 4), default=0)
    quantidadeatual = Column(Numeric(15, 4), default=0)
    quantidadereservada = Column(Numeric(15, 4), default=0)
    
    # Localização
    localizacao = Column(String(50), nullable=True)
    
    # Rastreabilidade
    numeroserie = Column(String(100), nullable=True)
    codigoanvisa = Column(String(50), nullable=True)
    
    # Fornecedor
    codfornecedor = Column(Integer, nullable=True)
    notafiscal = Column(String(20), nullable=True)
    
    # Controle
    inativosn = Column(SmallInteger, default=0)
    datacadastro = Column(DateTime, default=datetime.now)
    
    # Relacionamentos
    produto = relationship("Produto", back_populates="lotes")
    
    # Índices
    __table_args__ = (
        Index("idx_prodlote_produto", "codproduto"),
        Index("idx_prodlote_numero", "numerolote"),
        Index("idx_prodlote_validade", "datavalidade"),
    )
    
    def __repr__(self):
        return f"<ProdutoLote(codlote={self.codlote}, lote='{self.numerolote}')>"
    
    @hybrid_property
    def is_expired(self) -> bool:
        """Verifica se o lote está vencido."""
        if self.datavalidade:
            return self.datavalidade < date.today()
        return False
    
    @hybrid_property
    def quantidade_disponivel(self) -> Decimal:
        """Calcula quantidade disponível no lote."""
        atual = self.quantidadeatual or Decimal("0")
        reservada = self.quantidadereservada or Decimal("0")
        return atual - reservada


# ============================================================================
# Tabela: produtosanexos
# ============================================================================

class ProdutoAnexo(Base):
    """Modelo para tabela produtosanexos."""
    
    __tablename__ = "produtosanexos"
    
    # Chave primária
    codanexo = Column(Integer, primary_key=True, autoincrement=True)
    
    # Produto
    codproduto = Column(
        Integer, 
        ForeignKey("produtos.codproduto"), 
        nullable=False,
        index=True
    )
    
    # Dados do anexo
    nomearquivo = Column(String(200), nullable=False)
    descricao = Column(String(200), nullable=True)
    tipoanexo = Column(String(50), nullable=True)  # 'IMAGEM', 'PDF', 'DOCUMENTO', etc.
    extensao = Column(String(10), nullable=True)
    
    # Armazenamento
    # Opção 1: Caminho do arquivo
    caminhoarquivo = Column(String(500), nullable=True)
    
    # Opção 2: Conteúdo binário (para arquivos pequenos)
    conteudo = Column(LargeBinary, nullable=True)
    
    # Metadados
    tamanho = Column(Integer, nullable=True)  # Em bytes
    mimetype = Column(String(100), nullable=True)
    
    # Configurações
    principal = Column(SmallInteger, default=0)  # Se é a imagem principal
    ordem = Column(Integer, default=0)
    
    # Controle
    inativosn = Column(SmallInteger, default=0)
    datacadastro = Column(DateTime, default=datetime.now)
    usuariocadastro = Column(Integer, nullable=True)
    
    # Relacionamentos
    produto = relationship("Produto", back_populates="anexos")
    
    def __repr__(self):
        return f"<ProdutoAnexo(codanexo={self.codanexo}, arquivo='{self.nomearquivo}')>"
    
    @hybrid_property
    def is_image(self) -> bool:
        """Verifica se é uma imagem."""
        if self.tipoanexo:
            return self.tipoanexo.upper() == "IMAGEM"
        if self.extensao:
            return self.extensao.lower() in (".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp")
        return False


# ============================================================================
# Funções auxiliares
# ============================================================================

def create_all_tables(engine):
    """
    Cria todas as tabelas no banco de dados.
    
    Args:
        engine: SQLAlchemy Engine
    """
    Base.metadata.create_all(engine)


def drop_all_tables(engine):
    """
    Remove todas as tabelas do banco de dados.
    
    CUIDADO: Esta operação é destrutiva!
    
    Args:
        engine: SQLAlchemy Engine
    """
    Base.metadata.drop_all(engine)


def get_table_names() -> list:
    """
    Retorna lista com nomes de todas as tabelas mapeadas.
    
    Returns:
        Lista de nomes de tabelas
    """
    return list(Base.metadata.tables.keys())
