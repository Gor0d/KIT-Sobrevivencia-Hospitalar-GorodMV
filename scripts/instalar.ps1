<#
.SYNOPSIS
    Instala as skills do KIT de Sobrevivência Hospitalar MV para o Claude Code e/ou Codex.

.EXAMPLE
    .\scripts\instalar.ps1
    .\scripts\instalar.ps1 -Agente claude
    .\scripts\instalar.ps1 -Link            # link simbólico: 'git pull' já atualiza
#>
[CmdletBinding()]
param(
    [ValidateSet("claude", "codex", "ambos")]
    [string]$Agente = "ambos",
    [switch]$Link,
    [switch]$Force
)

$ErrorActionPreference = "Stop"

$raiz = Split-Path -Parent $PSScriptRoot
$origem = Join-Path $raiz "skills"
if (-not (Test-Path $origem)) {
    throw "Pasta 'skills' não encontrada em $raiz. Rode o script de dentro do repositório."
}

$destinos = @()
if ($Agente -in @("claude", "ambos")) { $destinos += Join-Path $HOME ".claude\skills" }
if ($Agente -in @("codex", "ambos")) { $destinos += Join-Path $HOME ".codex\skills" }

$skills = Get-ChildItem -Path $origem -Directory
Write-Host "KIT de Sobrevivência Hospitalar MV" -ForegroundColor Cyan
Write-Host "$($skills.Count) skills - modo: $(if ($Link) { 'link simbólico' } else { 'cópia' })`n"

foreach ($destino in $destinos) {
    if (-not (Test-Path $destino)) { New-Item -ItemType Directory -Force -Path $destino | Out-Null }
    Write-Host "-> $destino" -ForegroundColor Yellow

    foreach ($skill in $skills) {
        $alvo = Join-Path $destino $skill.Name

        if (Test-Path $alvo) {
            if (-not $Force) {
                # Preserva ajustes locais: sem -Force, nada é sobrescrito em silêncio.
                $resposta = Read-Host "   '$($skill.Name)' já existe. Sobrescrever? (s/N)"
                if ($resposta -notmatch '^[sS]') {
                    Write-Host "   [pulado ] $($skill.Name)" -ForegroundColor DarkGray
                    continue
                }
            }
            Remove-Item -Recurse -Force $alvo
        }

        if ($Link) {
            New-Item -ItemType SymbolicLink -Path $alvo -Target $skill.FullName | Out-Null
            Write-Host "   [linkado] $($skill.Name)" -ForegroundColor Green
        }
        else {
            Copy-Item -Recurse -Path $skill.FullName -Destination $alvo
            Get-ChildItem -Path $alvo -Recurse -Directory -Filter "__pycache__" |
                Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
            Write-Host "   [copiado] $($skill.Name)" -ForegroundColor Green
        }
    }
    Write-Host ""
}

Write-Host "Pronto. Abra o Claude Code ou o Codex e descreva o problema em português." -ForegroundColor Cyan
Write-Host "As skills ativam sozinhas pela descrição; para forçar: /mv-sobrevivencia"
if ($Link) {
    Write-Host "`nComo instalou com link, um 'git pull' neste repositório já atualiza as skills."
}
