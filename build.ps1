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

# --- Sincroniza versão: lê `version.py` e atualiza `version.txt` usado pelo PyInstaller
Write-Host "Sincronizando versão de version.py para $verFile"
$verPy = Get-Content -Raw -Path "version.py"
$versionMatch = [regex]::Match($verPy, 'VERSION\s*=\s*"(?<v>[^"]+)"')
$buildMatch = [regex]::Match($verPy, 'BUILD\s*=\s*"(?<b>[^"]+)"')
$versionStr = if ($versionMatch.Success) { $versionMatch.Groups['v'].Value } else { '0.0.0' }
$buildStr = if ($buildMatch.Success) { $buildMatch.Groups['b'].Value } else { $versionStr }

# Converte BUILD (ex: 26.03.31) em tuple numeric para filevers/prodvers
$parts = $buildStr -split '\.' | ForEach-Object { [int]($_ -replace '\D','') }
while ($parts.Count -lt 4) { $parts += 0 }
$fileVers = "({0},{1},{2},{3})" -f $parts[0], $parts[1], $parts[2], $parts[3]

# tenta capturar revisão em VERSION (ex: 'rev. 1') para usar como quarto número
$revMatch = [regex]::Match($versionStr, 'rev\.?\s*(?<r>\d+)', 'IgnoreCase')
if ($revMatch.Success) { $parts[3] = [int]$revMatch.Groups['r'].Value }

# Cria o conteúdo de version.txt com os valores extraídos
$versionTxt = @"
VSVersionInfo(
    ffi=FixedFileInfo(
        filevers=$fileVers,
        prodvers=$fileVers,
        mask=0x3f,
        flags=0x0,
        OS=0x40004,
        fileType=0x1,
        subtype=0x0,
        date=(0, 0)
    ),
    kids=[
        StringFileInfo(
            [
                StringTable(
                    '041604B0',  # Português Brasil
                    [
                        StringStruct('CompanyName', 'CEOsoftware'),
                        StringStruct('FileDescription', 'CSCollect Manager'),
                        StringStruct('FileVersion', '$versionStr'),
                        StringStruct('InternalName', 'CSCollectManager.exe'),
                        StringStruct('OriginalFilename', 'CSCollectManager.exe'),
                        StringStruct('ProductName', 'CSCollect Manager'),
                        StringStruct('CompanyName', 'CEOsoftware'),
                        StringStruct('LegalTrademarks', ''),
                        StringStruct('ProductVersion', '$versionStr'),
                        StringStruct('LegalCopyright', '© 2026 CEOsoftware')
                    ]
                )
            ]
        ),
        VarFileInfo([VarStruct('Translation', [1046, 1200])])
    ]
)
"@

Set-Content -Path $verFile -Value $versionTxt -Encoding UTF8
Write-Host "Arquivo $verFile atualizado com versão: $versionStr"

if (Test-Path $icon) {
    Write-Host "Ícone encontrado: $icon"
    & .\.venv\Scripts\pyinstaller.exe --noconfirm --clean --name $outName --onefile --windowed --icon $icon $paths $hiddenImportHandlers $hiddenImportVersion $addDataAssets $addDataApp $addDataUtils --version-file $verFile $entry
} else {
    Write-Host "Ícone não encontrado em $icon - executando sem ícone"
    & .\.venv\Scripts\pyinstaller.exe --noconfirm --clean --name $outName --onefile --windowed $paths $hiddenImportHandlers $hiddenImportVersion $addDataAssets $addDataApp $addDataUtils --version-file $verFile $entry
}

Write-Host "Build finalizado. Artefatos em dist\\$outName or dist\\$outName.exe"
