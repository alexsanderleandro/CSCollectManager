"""
xlsx_writer.py
==============
Gravador mínimo de planilha Excel (.xlsx), sem dependência nova.

Um .xlsx é um ZIP de arquivos XML (SpreadsheetML). Para uma planilha só,
com títulos, cabeçalho em negrito, números, moeda e datas, bastam os seis
arquivos gravados aqui — o mesmo espírito do PDF da Análise de Estoque, que
usa o que o Qt já oferece em vez de trazer uma biblioteca.
"""
from __future__ import annotations

import re
import zipfile
from datetime import date, datetime
from typing import Any, List, Optional, Sequence
from xml.sax.saxutils import escape

# Formato de cada coluna.
TEXTO, NUMERO, MOEDA, DATA = "texto", "numero", "moeda", "data"

# Índice do estilo (cellXfs em styles.xml) de cada formato.
_ESTILO = {TEXTO: 0, NUMERO: 2, MOEDA: 3, DATA: 4}
_ESTILO_CABECALHO = 1
_ESTILO_TITULO = 5
_ESTILO_SUBTITULO = 6

# Caracteres de controle que o XML não aceita (quebra de linha e tab passam).
_CONTROLE_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")

_STYLES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<numFmts count="3">
<numFmt numFmtId="164" formatCode="#,##0.###"/>
<numFmt numFmtId="165" formatCode="&quot;R$&quot; #,##0.00;[Red]-&quot;R$&quot; #,##0.00"/>
<numFmt numFmtId="166" formatCode="dd/mm/yyyy"/>
</numFmts>
<fonts count="4">
<font><sz val="10"/><name val="Calibri"/></font>
<font><b/><sz val="10"/><color rgb="FFFFFFFF"/><name val="Calibri"/></font>
<font><b/><sz val="13"/><color rgb="FF1D6BB0"/><name val="Calibri"/></font>
<font><sz val="10"/><color rgb="FF5B6577"/><name val="Calibri"/></font>
</fonts>
<fills count="3">
<fill><patternFill patternType="none"/></fill>
<fill><patternFill patternType="gray125"/></fill>
<fill><patternFill patternType="solid"><fgColor rgb="FF1D6BB0"/><bgColor indexed="64"/></patternFill></fill>
</fills>
<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>
<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
<cellXfs count="7">
<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
<xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1"/>
<xf numFmtId="164" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>
<xf numFmtId="165" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>
<xf numFmtId="166" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>
<xf numFmtId="0" fontId="2" fillId="0" borderId="0" xfId="0" applyFont="1"/>
<xf numFmtId="0" fontId="3" fillId="0" borderId="0" xfId="0" applyFont="1"/>
</cellXfs>
<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>"""

_CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
</Types>"""

_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>"""

_WORKBOOK_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>"""


def _coluna(n: int) -> str:
    """0 -> "A", 25 -> "Z", 26 -> "AA"."""
    letras = ""
    n += 1
    while n:
        n, resto = divmod(n - 1, 26)
        letras = chr(65 + resto) + letras
    return letras


def _texto(valor: Any) -> str:
    return escape(_CONTROLE_RE.sub("", str(valor)))


def _celula(ref: str, valor: Any, estilo: int, formato: str) -> str:
    if valor is None or valor == "":
        return f'<c r="{ref}" s="{estilo}"/>' if estilo else ""
    if formato == DATA and isinstance(valor, (date, datetime)):
        dia = valor.date() if isinstance(valor, datetime) else valor
        serial = (dia - date(1899, 12, 30)).days
        return f'<c r="{ref}" s="{estilo}"><v>{serial}</v></c>'
    if formato in (NUMERO, MOEDA) and isinstance(valor, (int, float)) and not isinstance(valor, bool):
        return f'<c r="{ref}" s="{estilo}"><v>{valor!r}</v></c>'
    return f'<c r="{ref}" s="{estilo}" t="inlineStr"><is><t xml:space="preserve">{_texto(valor)}</t></is></c>'


def gravar_xlsx(
    caminho: str,
    nome_planilha: str,
    titulos: Sequence[str],
    cabecalho: Sequence[str],
    linhas: Sequence[Sequence[Any]],
    formatos: Sequence[str],
    larguras: Optional[Sequence[float]] = None,
) -> None:
    """Grava uma planilha com linhas de título, cabeçalho (com filtro e
    congelado no topo) e dados.

    Args:
        titulos: Linhas acima do cabeçalho; a primeira sai em destaque.
        cabecalho: Nome de cada coluna.
        linhas: Uma lista de valores por linha, na ordem do cabeçalho.
        formatos: ``TEXTO``/``NUMERO``/``MOEDA``/``DATA`` por coluna.
        larguras: Largura de cada coluna, em caracteres (opcional).
    """
    n_colunas = len(cabecalho)
    linhas_xml: List[str] = []
    r = 0
    for k, titulo in enumerate(titulos):
        r += 1
        estilo = _ESTILO_TITULO if k == 0 else _ESTILO_SUBTITULO
        linhas_xml.append(f'<row r="{r}">{_celula(f"A{r}", titulo, estilo, TEXTO)}</row>')
    if titulos:
        r += 1  # linha em branco entre os títulos e a tabela
    r += 1
    linha_cabecalho = r
    linhas_xml.append(
        f'<row r="{r}">' + "".join(
            _celula(f"{_coluna(c)}{r}", nome, _ESTILO_CABECALHO, TEXTO) for c, nome in enumerate(cabecalho)
        ) + "</row>"
    )
    for valores in linhas:
        r += 1
        celulas = "".join(
            _celula(f"{_coluna(c)}{r}", valores[c] if c < len(valores) else None,
                    _ESTILO.get(formatos[c], 0), formatos[c])
            for c in range(n_colunas)
        )
        linhas_xml.append(f'<row r="{r}">{celulas}</row>')

    cols = ""
    if larguras:
        cols = "<cols>" + "".join(
            f'<col min="{c + 1}" max="{c + 1}" width="{w:.1f}" customWidth="1"/>' for c, w in enumerate(larguras)
        ) + "</cols>"
    ultima = f"{_coluna(n_colunas - 1)}{max(r, linha_cabecalho)}"
    folha = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<sheetViews><sheetView workbookViewId="0">'
        f'<pane ySplit="{linha_cabecalho}" topLeftCell="A{linha_cabecalho + 1}" activePane="bottomLeft" state="frozen"/>'
        '</sheetView></sheetViews>'
        f"{cols}<sheetData>{''.join(linhas_xml)}</sheetData>"
        f'<autoFilter ref="A{linha_cabecalho}:{ultima}"/>'
        "</worksheet>"
    )
    nome_planilha = _texto(re.sub(r"[\[\]:*?/\\]", " ", nome_planilha)[:31] or "Planilha")
    workbook = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f'<sheets><sheet name="{nome_planilha}" sheetId="1" r:id="rId1"/></sheets>'
        '<definedNames><definedName name="_xlnm._FilterDatabase" localSheetId="0" hidden="1">'
        f"'{nome_planilha}'!$A${linha_cabecalho}:${_coluna(n_colunas - 1)}${max(r, linha_cabecalho)}"
        "</definedName></definedNames>"
        "</workbook>"
    )

    with zipfile.ZipFile(caminho, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", _CONTENT_TYPES)
        zf.writestr("_rels/.rels", _RELS)
        zf.writestr("xl/workbook.xml", workbook)
        zf.writestr("xl/_rels/workbook.xml.rels", _WORKBOOK_RELS)
        zf.writestr("xl/styles.xml", _STYLES)
        zf.writestr("xl/worksheets/sheet1.xml", folha)
