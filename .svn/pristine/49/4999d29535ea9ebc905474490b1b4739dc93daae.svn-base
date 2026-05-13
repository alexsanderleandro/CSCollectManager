# Build script para Windows PowerShell
# Usa o virtualenv ativo para instalar pyinstaller e gerar o executÃ¡vel

Set-StrictMode -Version Latest

$ErrorActionPreference = 'Stop'

Write-Host "Iniciando build do CSCollectManager..."

# Garante que estamos na raiz do projeto
$root = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $root

# Instala PyInstaller no venv ativo (se nÃ£o estiver instalado)
Write-Host "Instalando/atualizando PyInstaller..."
& .\.venv\Scripts\pip.exe install --upgrade pyinstaller

# Adiciona os imports escondidos necessÃ¡rios (variÃ¡veis separadas para evitar concatenaÃ§Ã£o)
$hiddenImportHandlers = "--hidden-import=logging.handlers"
$hiddenImportVersion = "--hidden-import=version"

# Garante que o diretÃ³rio do projeto seja adicionado ao caminho de busca do PyInstaller
$paths = "--paths=."

# DefiniÃ§Ãµes
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

# Corrige o formato do parÃ¢metro --add-data para SOURCE:DEST
$addDataAssets = "--add-data=${assetsSrc}:${assetsDest}"
$addDataApp = "--add-data=${appSrc}:${appDest}"
$addDataUtils = "--add-data=${utilsSrc}:${utilsDest}"
# Incluir .env e keys no bundle para que EXE extraÃ­do em _MEIPASS possa ler MASTER_KEY e hmac_key.bin
$addDataEnv = "--add-data=.env:."
# somente adicionar keys se a pasta existir (evita erro quando nÃ£o hÃ¡ keys no projeto)
$addDataKeys = ""
if (Test-Path "keys") {
    $addDataKeys = "--add-data=keys:keys"
    Write-Host "Incluindo pasta 'keys' no bundle"
} else {
    Write-Host "Pasta 'keys' nao encontrada - nao sera adicionada ao bundle"
}

# Executa PyInstaller (usa Ã­cone apenas se existir)
Write-Host "Executando PyInstaller..."

# --- Sincroniza versÃ£o: lÃª `version.py` e atualiza `version.txt` usado pelo PyInstaller
Write-Host "Sincronizando versÃ£o de version.py para $verFile"
$verPy = Get-Content -Raw -Path "version.py"
$versionMatch = [regex]::Match($verPy, 'VERSION\s*=\s*"(?<v>[^"]+)"')
$buildMatch = [regex]::Match($verPy, 'BUILD\s*=\s*"(?<b>[^"]+)"')
$versionStr = if ($versionMatch.Success) { $versionMatch.Groups['v'].Value } else { '0.0.0' }
$buildStr = if ($buildMatch.Success) { $buildMatch.Groups['b'].Value } else { $versionStr }

# Converte BUILD (ex: 26.03.31) em tuple numeric para filevers/prodvers
$parts = $buildStr -split '\.' | ForEach-Object { [int]($_ -replace '\D','') }
while ($parts.Count -lt 4) { $parts += 0 }
$fileVers = "({0},{1},{2},{3})" -f $parts[0], $parts[1], $parts[2], $parts[3]

# tenta capturar revisÃ£o em VERSION (ex: 'rev. 1') para usar como quarto nÃºmero
$revMatch = [regex]::Match($versionStr, 'rev\.?\s*(?<r>\d+)', 'IgnoreCase')
if ($revMatch.Success) { $parts[3] = [int]$revMatch.Groups['r'].Value }

# Cria o conteÃºdo de version.txt com os valores extraÃ­dos
$copyright = [char]0x00A9
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
                    '041604B0',  # PortuguÃªs Brasil
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
                        StringStruct('LegalCopyright', 'Copyright $copyright 2026 CEOsoftware')
                    ]
                )
            ]
        ),
        VarFileInfo([VarStruct('Translation', [1046, 1200])])
    ]
)
"@

Set-Content -Path $verFile -Value $versionTxt -Encoding UTF8
Write-Host "Arquivo $verFile atualizado com versÃ£o: $versionStr"

if (Test-Path $icon) {
    Write-Host "Ãcone encontrado: $icon"
    & .\.venv\Scripts\pyinstaller.exe --noconfirm --clean --name $outName --onefile --windowed --icon $icon $paths $hiddenImportHandlers $hiddenImportVersion $addDataAssets $addDataApp $addDataUtils $addDataEnv $addDataKeys --version-file $verFile $entry
} else {
    Write-Host "Ãcone nÃ£o encontrado em $icon - executando sem Ã­cone"
    & .\.venv\Scripts\pyinstaller.exe --noconfirm --clean --name $outName --onefile --windowed $paths $hiddenImportHandlers $hiddenImportVersion $addDataAssets $addDataApp $addDataUtils $addDataEnv $addDataKeys --version-file $verFile $entry
}

Write-Host "Build finalizado. Artefatos em dist\\$outName or dist\\$outName.exe"
