$ErrorActionPreference = 'Stop'
$dist = Join-Path $PSScriptRoot 'dist'
$source = Join-Path $dist 'rapfi-source'
$output = Join-Path $dist 'rapfi-arm64'
$toolchain = Join-Path $dist 'rapfi-toolchain'
$zig = Join-Path $toolchain 'ziglang/zig.exe'
$cmake = Join-Path $toolchain 'cmake/data/bin/cmake.exe'
$ninja = Join-Path $toolchain 'ninja-1.11.1.4.data/scripts/ninja.exe'
$revision = '1387d11312190ec66665d361ff07a7c70221b78a'
$weights = '7eeb19b55219a48138756293f92211a1539bab4d'

function Invoke-Checked {
    param([string]$Program, [string[]]$Arguments)
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Program exited with $LASTEXITCODE" }
}

if (!(Test-Path -LiteralPath $zig) -or !(Test-Path -LiteralPath $cmake) -or !(Test-Path -LiteralPath $ninja)) {
    $wheels = Join-Path $dist 'rapfi-wheels'
    Invoke-Checked python @('-m','pip','download','--only-binary=:all:','--dest',$wheels,'ziglang==0.14.1','cmake==3.31.10','ninja==1.11.1.4')
    foreach ($wheel in (Get-ChildItem -LiteralPath $wheels -Filter '*.whl')) {
        Invoke-Checked python @('-m','zipfile','-e',$wheel.FullName,$toolchain)
    }
}
if (!(Test-Path -LiteralPath $source)) {
    Invoke-Checked git @('clone','https://github.com/dotb1ue/rapfi.git',$source)
}
Invoke-Checked git @('-C',$source,'checkout','--detach',$revision)
New-Item -ItemType Directory -Force $output | Out-Null
$upstream = "https://raw.githubusercontent.com/dotb1ue/rapfi-networks/$weights"
foreach ($file in @(@('classical/model260809.bin','model260809.bin'),
                    @('config-example/gomocalc-classical260809.toml','config.toml'),
                    @('LICENSE','CC0.txt'))) {
    Invoke-Checked curl.exe @('-fLsS',"$upstream/$($file[0])",'-o',(Join-Path $output $file[1]))
}
$config = Join-Path $output 'config.toml'
(Get-Content -Raw -LiteralPath $config).Replace('coord_conversion_mode = "X_flipY"', 'coord_conversion_mode = "none"') |
    Set-Content -NoNewline -Encoding utf8 $config

$build = Join-Path $dist 'rapfi-build'
$archiveRules = Join-Path $dist 'zig-archive.cmake'
$zigPath = $zig.Replace('\', '/')
@"
set(CMAKE_C_ARCHIVE_CREATE "\"$zigPath\" ar qc <TARGET> <OBJECTS>")
set(CMAKE_C_ARCHIVE_FINISH "\"$zigPath\" ranlib <TARGET>")
"@ | Set-Content -LiteralPath $archiveRules
$env:ZIG_LOCAL_CACHE_DIR = Join-Path $dist 'zig-local-cache'
$env:ZIG_GLOBAL_CACHE_DIR = Join-Path $dist 'zig-global-cache'
$flags = @(
    "-DCMAKE_MAKE_PROGRAM=$ninja", '-DCMAKE_SYSTEM_NAME=Linux', '-DCMAKE_SYSTEM_PROCESSOR=aarch64',
    "-DCMAKE_USER_MAKE_RULES_OVERRIDE=$archiveRules",
    "-DCMAKE_C_COMPILER=$zig;cc", "-DCMAKE_CXX_COMPILER=$zig;c++",
    '-DCMAKE_C_FLAGS=-target aarch64-linux-musl', '-DCMAKE_CXX_FLAGS=-target aarch64-linux-musl -DUSE_NEON',
    '-DCMAKE_BUILD_TYPE=Release', '-DUSE_NEON=OFF', '-DUSE_NEON_DOTPROD=OFF',
    '-DNO_MULTI_THREADING=ON', '-DNO_COMMAND_MODULES=ON'
)
Invoke-Checked $cmake (@('--fresh','-S',(Join-Path $source 'Rapfi'),'-B',$build,'-G','Ninja') + $flags)
Invoke-Checked $cmake @('--build',$build,'--parallel','4')
Invoke-Checked $zig @('objcopy','--strip-debug',(Join-Path $build 'pbrain-rapfi'),(Join-Path $output 'rapfi'))
Copy-Item -LiteralPath (Join-Path $source 'Copying.txt') -Destination (Join-Path $output 'Rapfi-GPL.txt')
Invoke-Checked git @('-C',$source,'archive','--format=tar.gz','--prefix=rapfi/','-o',(Join-Path $output 'rapfi-source.tar.gz'),$revision)
