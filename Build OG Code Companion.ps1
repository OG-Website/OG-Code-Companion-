$ErrorActionPreference = 'Stop'
$ogProject = $PSScriptRoot
$ogBuild = Join-Path $ogProject '.build'
$ogOutput = Join-Path $ogBuild 'dist\OG Code Companion'
$ogOriginalPath = $env:Path
Push-Location -LiteralPath $ogProject
try {
    py -3 -m unittest -v og_companion_tests.py
    if ($LASTEXITCODE -ne 0) { throw 'Source tests failed.' }
    $ogPython = py -3 -c "import sys; print(sys.executable)"
    $ogQtDirectories = & $ogPython -c "from pathlib import Path; import PySide6, shiboken6; print(Path(PySide6.__file__).parent); print(Path(shiboken6.__file__).parent)"
    # Native Qt dependencies must come from this runtime or Windows, not another tool on PATH.
    $env:Path = (@($ogQtDirectories) + @([IO.Path]::GetDirectoryName($ogPython), (Join-Path $env:windir 'System32'), $env:windir)) -join ';'
    & $ogPython -m PyInstaller --noconfirm --onedir --windowed --noupx --exclude-module PyQt6 --name 'OG Code Companion' --contents-directory 'OG Runtime' --distpath (Join-Path $ogBuild 'dist') --workpath (Join-Path $ogBuild 'work') --specpath (Join-Path $ogBuild 'spec') --icon (Join-Path $ogProject 'og_companion_assets\OG Code Companion logo.ico') --version-file (Join-Path $ogProject 'version_info.txt') (Join-Path $ogProject 'og_companion.py')
    if ($LASTEXITCODE -ne 0) { throw 'Executable build failed.' }
    $ogOptionalQtFiles = @('OG Runtime\PySide6\plugins\platforminputcontexts\qtvirtualkeyboardplugin.dll','OG Runtime\PySide6\Qt6VirtualKeyboard.dll')
    foreach ($ogOptionalFile in $ogOptionalQtFiles) {
        $ogOptionalPath = [IO.Path]::GetFullPath((Join-Path $ogOutput $ogOptionalFile))
        if (-not $ogOptionalPath.StartsWith(([IO.Path]::GetFullPath($ogOutput)+'\'),[StringComparison]::OrdinalIgnoreCase)) { throw 'Unexpected optional Qt component path.' }
        if (Test-Path -LiteralPath $ogOptionalPath) { Remove-Item -LiteralPath $ogOptionalPath -Force }
    }
    $ogFiles = @('og_companion.py','og_companion_search.py','og_companion_sources.py','og_companion_tests.py','og_companion_workbench.py','og_companion_providers.py','og_companion_library.json','OG Code Companion - Read Me.txt','OG Code Companion - Technical Specification.pdf','Start OG Code Companion.cmd')
    foreach ($ogFile in $ogFiles) { Copy-Item -LiteralPath (Join-Path $ogProject $ogFile) -Destination $ogOutput -Force }
    Copy-Item -LiteralPath (Join-Path $ogProject 'og_companion_assets') -Destination $ogOutput -Recurse -Force
    $ogPythonLicence = & $ogPython -c "import sys; from pathlib import Path; print(Path(sys.base_prefix) / 'LICENSE.txt')"
    if (Test-Path -LiteralPath $ogPythonLicence) { Copy-Item -LiteralPath $ogPythonLicence -Destination (Join-Path $ogOutput 'OG Runtime\Python-Licence.txt') -Force }
    $ogCheck = Join-Path $ogBuild 'installation-check.json'
    $ogProcess = Start-Process -FilePath (Join-Path $ogOutput 'OG Code Companion.exe') -ArgumentList @('--check-installation', ('"'+$ogCheck+'"')) -WindowStyle Hidden -PassThru
    if (-not $ogProcess.WaitForExit(60000)) { Stop-Process -Id $ogProcess.Id; throw 'Packaged installation check did not finish within 60 seconds.' }
    $ogProcess.Refresh()
    if ($ogProcess.ExitCode -ne 0) { throw 'Packaged installation check failed.' }
    Compress-Archive -LiteralPath $ogOutput -DestinationPath (Join-Path $ogProject 'OG Code Companion.zip') -Force
    Write-Output ('Portable package: '+(Join-Path $ogProject 'OG Code Companion.zip'))
} finally { $env:Path = $ogOriginalPath; Pop-Location }
