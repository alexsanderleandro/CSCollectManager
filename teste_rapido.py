"""Teste rápido de validação de licença"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

# Importa diretamente do módulo, não do package
import importlib.util
spec = importlib.util.spec_from_file_location(
    "license_validator",
    os.path.join(os.path.dirname(__file__), "services", "license_validator.py")
)
license_validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(license_validator)

validar_licenca_completa = license_validator.validar_licenca_completa
obter_device_id = license_validator.obter_device_id

try:
    device_atual = obter_device_id()
    print(f'Device ID atual: {device_atual}')
    
    # Testa validação apenas com CNPJ (device ID opcional)
    result = validar_licenca_completa(
        caminho_key='licenca.key',
        cnpj_atual='65381113000120',
        device_id_atual=device_atual,
        validar_online=False,  # Não tenta validação online
        obrigar_online=False,
        validar_device_id=False  # NÃO valida device ID
    )
    
    print('✅ LICENÇA VÁLIDA')
    print(f'Cliente: {result["nome_cliente"]}')
    print(f'Servidor: {result["sql_servidor"]}')
    print(f'Banco: {result["sql_banco"]}')
    print(f'Validade: {result["validade"]}')
    
except Exception as e:
    print(f'❌ ERRO: {e}')
    import traceback
    traceback.print_exc()
