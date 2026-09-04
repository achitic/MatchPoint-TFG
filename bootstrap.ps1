[CmdletBinding()]
param(
    [string]$Python = "py",
    [string]$VenvPath = ".venv"
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvAbsolute = if ([System.IO.Path]::IsPathRooted($VenvPath)) {
    [System.IO.Path]::GetFullPath($VenvPath)
} else {
    [System.IO.Path]::GetFullPath((Join-Path $projectRoot $VenvPath))
}
$lockFile = Join-Path $projectRoot "requirements-dev.lock"

if (-not (Test-Path -LiteralPath $lockFile)) {
    throw "No se encuentra el lock de desarrollo: $lockFile"
}
if (Test-Path -LiteralPath $venvAbsolute) {
    throw "El destino ya existe: $venvAbsolute. Elimínalo o elige otro -VenvPath."
}

if ($Python -eq "py") {
    & py -3.13 -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 13) else 1)"
    if ($LASTEXITCODE -ne 0) {
        throw "Se necesita Python 3.13 para usar los locks reproducibles."
    }
    & py -3.13 -m venv $venvAbsolute
    if ($LASTEXITCODE -ne 0) {
        throw "No se pudo crear el entorno virtual con py -3.13."
    }
} else {
    & $Python -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 13) else 1)"
    if ($LASTEXITCODE -ne 0) {
        throw "El ejecutable indicado debe ser Python 3.13."
    }
    & $Python -m venv $venvAbsolute
    if ($LASTEXITCODE -ne 0) {
        throw "No se pudo crear el entorno virtual con $Python."
    }
}

$venvPython = Join-Path $venvAbsolute "Scripts\python.exe"
& $venvPython -m pip install --require-hashes -r $lockFile
if ($LASTEXITCODE -ne 0) {
    throw "Falló la instalación verificada de requirements-dev.lock."
}
& $venvPython -m pip check
if ($LASTEXITCODE -ne 0) {
    throw "pip check detectó dependencias incompatibles."
}
& $venvPython -c "import sklearn; assert sklearn.__version__ == '1.8.0', sklearn.__version__; print('MatchPoint listo - scikit-learn', sklearn.__version__)"
if ($LASTEXITCODE -ne 0) {
    throw "La versión instalada de scikit-learn no coincide con 1.8.0."
}

Write-Host "Entorno reproducible creado en $venvAbsolute"
