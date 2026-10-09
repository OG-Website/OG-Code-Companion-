$ErrorActionPreference = 'Stop'
$ogProject = $PSScriptRoot
$ogBuild = Join-Path $ogProject '.build'
$ogOutput = Join-Path $ogBuild 'dist\OG Companion'
Push-Location -LiteralPath $ogProject
try {
    py -3 -m unittest -v og_companion_tests.py
    if ($LASTEXITCODE -ne 0) { throw 'Source tests failed.' }
    py -3 -m PyInstaller --noconfirm --onedir --windowed --noupx --name 'OG Companion' --contents-directory 'OG Runtime' --distpath (Join-Path $ogBuild 'dist') --workpath (Join-Path $ogBuild 'work') --specpath (Join-Path $ogBuild 'spec') --icon (Join-Path $ogProject 'og_companion_assets\og-companion.ico') --version-file (Join-Path $ogProject 'version_info.txt') (Join-Path $ogProject 'og_companion.py')
    if ($LASTEXITCODE -ne 0) { throw 'Executable build failed.' }
    $ogFiles = @('og_companion.py','og_companion_search.py','og_companion_sources.py','og_companion_tests.py','og_companion_library.json','OG Companion - Read Me.txt','OG Companion - Technical Specification.pdf','Start OG Companion.cmd')
    foreach ($ogFile in $ogFiles) { Copy-Item -LiteralPath (Join-Path $ogProject $ogFile) -Destination $ogOutput -Force }
    Copy-Item -LiteralPath (Join-Path $ogProject 'og_companion_assets') -Destination $ogOutput -Recurse -Force
    $ogCheck = Join-Path $ogBuild 'installation-check.json'
    $ogProcess = Start-Process -FilePath (Join-Path $ogOutput 'OG Companion.exe') -ArgumentList @('--check-installation', ('"'+$ogCheck+'"')) -WindowStyle Hidden -Wait -PassThru
    if ($ogProcess.ExitCode -ne 0) { throw 'Packaged installation check failed.' }
    Compress-Archive -LiteralPath $ogOutput -DestinationPath (Join-Path $ogProject 'OG Companion.zip') -Force
    Write-Output ('Portable package: '+(Join-Path $ogProject 'OG Companion.zip'))
} finally { Pop-Location }
