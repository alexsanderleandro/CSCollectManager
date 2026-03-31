# Build script para Windows PowerShell
# Usa o virtualenv ativo para instalar pyinstaller e gerar o executável

Set-StrictMode -Version Latest

$ErrorActionPreference = 'Stop'

Write-Host "Iniciando build do CSCollectManager..."

# Garante que estamos na raiz do projeto
$root = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $root

# Instala PyInstaller no venv ativo (se não estiver instalado)
Write-Host "Instalando/atualizando PyInstaller..."
& .\.venv\Scripts\pip.exe install --upgrade pyinstaller

# Adiciona os imports escondidos necessários (variáveis separadas para evitar concatenação)
$hiddenImportHandlers = "--hidden-import=logging.handlers"
$hiddenImportVersion = "--hidden-import=version"

# Garante que o diretório do projeto seja adicionado ao caminho de busca do PyInstaller
$paths = "--paths=."

# Definições
$entry = "run.py"
$outName = "CSCollectManager"
$icon = "assets/icon.ico"
$verFile = "version.txt"
$assetsSrc = "assets"
$assetsDest = "assets"
$appSrc = "app"
$appDest = "app"
$utilsSrc = "utils"
$utilsDest = "utils"

# Corrige o formato do parâmetro --add-data para SOURCE:DEST
$addDataAssets = "--add-data=${assetsSrc}:${assetsDest}"
$addDataApp = "--add-data=${appSrc}:${appDest}"
$addDataUtils = "--add-data=${utilsSrc}:${utilsDest}"

# Executa PyInstaller (usa ícone apenas se existir)
Write-Host "Executando PyInstaller..."
if (Test-Path $icon) {
    Write-Host "Ícone encontrado: $icon"
    & .\.venv\Scripts\pyinstaller.exe --noconfirm --clean --name $outName --onefile --windowed --icon $icon $paths $hiddenImportHandlers $hiddenImportVersion $addDataAssets $addDataApp $addDataUtils --version-file $verFile $entry
} else {
    Write-Host "Ícone não encontrado em $icon - executando sem ícone"
    & .\.venv\Scripts\pyinstaller.exe --noconfirm --clean --name $outName --onefile --windowed $paths $hiddenImportHandlers $hiddenImportVersion $addDataAssets $addDataApp $addDataUtils --version-file $verFile $entry
}

Write-Host "Build finalizado. Artefatos em dist\\$outName or dist\\$outName.exe"
