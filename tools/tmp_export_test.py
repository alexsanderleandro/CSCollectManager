import os
import sys
import zipfile
from pathlib import Path

# Garantir que o diretório do projeto esteja no sys.path para importar pacotes locais
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.db_export_service import DbExportService
from services.export_service import EmpresaInfo, UsuarioInfo

empresa = EmpresaInfo(codempresa=1, nomeempresa="Empresa Teste", local="Matriz")
usuario = UsuarioInfo(codusuario=1, nomeusuario="Admin")
produtos = [
    {"codean":"7891234567890","codproduto":1,"descricaoproduto":"Produto","unidade":"UN","casasdecimais":3,"controlalote":False,"numlote":"","datafabricacao":None,"datavalidade":None,"codgrupo":0,"nomegrupo":"","localizacao":""}
]

out_dir = r"C:\Temp"
os.makedirs(out_dir, exist_ok=True)
svc = DbExportService(output_dir=out_dir)
zip_path = svc.export_carga(empresa, usuario, produtos)
print('ZIP gerado:', zip_path)
print('Existe?', os.path.exists(zip_path))

try:
    with zipfile.ZipFile(zip_path, 'r') as z:
        print('Conteúdo do ZIP:')
        for name in z.namelist():
            print(' -', name)
except Exception as e:
    print('Erro abrindo zip:', e)

# Lista arquivos no diretório de saída
print('\nArquivos em', out_dir)
for f in os.listdir(out_dir):
    print(' *', f)
