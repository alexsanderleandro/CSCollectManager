"""
Teste de validação de licença - CSCollectManager
Execute este script para testar a validação de licença.
"""

import os
import sys

# Adiciona o diretório raiz ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def testar_imports():
    """Testa se todos os imports necessários funcionam."""
    print("=" * 60)
    print("TESTE 1: Importação de Módulos")
    print("=" * 60)
    
    try:
        from services.license_validator import (
            validar_licenca_completa,
            obter_device_id,
            carregar_licenca,
            validar_token,
            validar_licenca_offline
        )
        print("✓ services.license_validator importado com sucesso")
    except Exception as e:
        print(f"✗ Erro ao importar license_validator: {e}")
        return False
    
    try:
        from licenca import (
            gerar_licenca,
            salvar_licenca_json,
            verificar_licenca
        )
        print("✓ licenca importado com sucesso")
    except Exception as e:
        print(f"✗ Erro ao importar licenca: {e}")
        return False
    
    return True


def testar_device_id():
    """Testa obtenção do Device ID."""
    print("\n" + "=" * 60)
    print("TESTE 2: Obtenção de Device ID")
    print("=" * 60)
    
    try:
        from services.license_validator import obter_device_id
        device_id = obter_device_id()
        print(f"✓ Device ID obtido: {device_id}")
        return device_id
    except Exception as e:
        print(f"✗ Erro ao obter Device ID: {e}")
        return None


def testar_formato_licenca():
    """Testa carregamento de licença no formato JSON."""
    print("\n" + "=" * 60)
    print("TESTE 3: Validação de Formato de Licença")
    print("=" * 60)
    
    import json
    import tempfile
    
    # Cria licença de teste
    licenca_teste = {
        "cnpjs": ["12345678000199"],
        "ids": ["teste-device-123"],
        "token": "token_teste",
        "validade": "2099-12-31",
        "database_url": None
    }
    
    # Salva em arquivo temporário
    with tempfile.NamedTemporaryFile(mode='w', suffix='.key', delete=False, encoding='utf-8') as f:
        json.dump(licenca_teste, f, ensure_ascii=False, indent=2)
        temp_file = f.name
    
    try:
        from services.license_validator import carregar_licenca
        licenca_carregada = carregar_licenca(temp_file)
        
        print(f"✓ Licença carregada do arquivo temporário")
        print(f"  CNPJs: {licenca_carregada['cnpjs']}")
        print(f"  IDs: {licenca_carregada['ids']}")
        print(f"  Validade: {licenca_carregada['validade']}")
        
        os.unlink(temp_file)
        return True
        
    except Exception as e:
        print(f"✗ Erro ao carregar licença: {e}")
        if os.path.exists(temp_file):
            os.unlink(temp_file)
        return False


def verificar_arquivo_licenca():
    """Verifica se existe arquivo de licença."""
    print("\n" + "=" * 60)
    print("TESTE 4: Verificação de Arquivo de Licença")
    print("=" * 60)
    
    caminho_licenca = os.path.join(os.path.dirname(__file__), "licenca.key")
    
    if os.path.exists(caminho_licenca):
        print(f"✓ Arquivo de licença encontrado: {caminho_licenca}")
        
        try:
            import json
            with open(caminho_licenca, 'r', encoding='utf-8') as f:
                conteudo = f.read().strip()
                
            # Tenta parsear como JSON
            try:
                licenca = json.loads(conteudo)
                print("✓ Formato: JSON (novo formato)")
                print(f"  CNPJs: {licenca.get('cnpjs', [])}")
                print(f"  IDs: {licenca.get('ids', [])}")
                print(f"  Validade: {licenca.get('validade', 'N/A')}")
                print(f"  Database URL: {'Configurada' if licenca.get('database_url') else 'Não configurada'}")
                return True
                
            except json.JSONDecodeError:
                print("⚠ Formato: Token simples (formato antigo)")
                print(f"  Tamanho: {len(conteudo)} caracteres")
                return True
                
        except Exception as e:
            print(f"✗ Erro ao ler arquivo: {e}")
            return False
    else:
        print(f"⚠ Arquivo de licença não encontrado: {caminho_licenca}")
        print("  Para criar uma licença, execute: python licenca.py")
        return False


def verificar_dependencias():
    """Verifica se as dependências estão instaladas."""
    print("\n" + "=" * 60)
    print("TESTE 5: Verificação de Dependências")
    print("=" * 60)
    
    dependencias = {
        'PySide6': 'Interface gráfica',
        'python-dotenv': 'Variáveis de ambiente (.env)',
        'psycopg2': 'PostgreSQL (validação online)'
    }
    
    for modulo, descricao in dependencias.items():
        try:
            if modulo == 'python-dotenv':
                __import__('dotenv')
            else:
                __import__(modulo.lower().replace('-', '_'))
            print(f"✓ {modulo:20s} - {descricao}")
        except ImportError:
            print(f"✗ {modulo:20s} - {descricao} (NÃO INSTALADO)")


def verificar_master_key():
    """Verifica se MASTER_KEY está configurada."""
    print("\n" + "=" * 60)
    print("TESTE 6: Verificação de MASTER_KEY")
    print("=" * 60)
    
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        print("⚠ python-dotenv não instalado, tentando sem .env...")
    
    master_key = os.environ.get('MASTER_KEY')
    
    if master_key:
        print(f"✓ MASTER_KEY configurada (tamanho: {len(master_key)} caracteres)")
        if len(master_key) < 32:
            print("⚠ AVISO: Chave muito curta (recomendado: mínimo 32 caracteres)")
        return True
    else:
        print("✗ MASTER_KEY não configurada")
        print("  Crie um arquivo .env com: MASTER_KEY=sua_chave_aqui")
        
        # Verifica se existe arquivo .env
        env_path = os.path.join(os.path.dirname(__file__), '.env')
        if os.path.exists(env_path):
            print(f"  Arquivo .env encontrado em: {env_path}")
        else:
            print(f"  Arquivo .env não encontrado")
        
        return False


def main():
    """Executa todos os testes."""
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 10 + "TESTE DE VALIDAÇÃO DE LICENÇA" + " " * 19 + "║")
    print("║" + " " * 17 + "CSCollectManager" + " " * 25 + "║")
    print("╚" + "=" * 58 + "╝")
    
    resultados = []
    
    # Executa testes
    resultados.append(("Importação de Módulos", testar_imports()))
    resultados.append(("Device ID", testar_device_id() is not None))
    resultados.append(("Formato de Licença", testar_formato_licenca()))
    resultados.append(("Arquivo de Licença", verificar_arquivo_licenca()))
    verificar_dependencias()  # Não conta no resultado
    resultados.append(("MASTER_KEY", verificar_master_key()))
    
    # Resumo
    print("\n" + "=" * 60)
    print("RESUMO DOS TESTES")
    print("=" * 60)
    
    total = len(resultados)
    sucesso = sum(1 for _, r in resultados if r)
    
    for nome, resultado in resultados:
        status = "✓ PASSOU" if resultado else "✗ FALHOU"
        print(f"{nome:30s} {status}")
    
    print("=" * 60)
    print(f"Total: {sucesso}/{total} testes passaram")
    
    if sucesso == total:
        print("\n✅ Todos os testes passaram! Sistema pronto para uso.")
        return 0
    else:
        print(f"\n⚠ {total - sucesso} teste(s) falharam. Verifique as mensagens acima.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
