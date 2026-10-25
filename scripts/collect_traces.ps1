<#
.SYNOPSIS
    Collects original Google Antigravity agent traces for HackerRank Orchestrate.
.DESCRIPTION
    Extracts the conversation session files for hackerrank-orchestrate-october26
    into agent-trace/antigravity/<conversation-id>/ and compresses it to agent-trace.zip.
#>

[CmdletBinding()]
param(
    [string]$ConversationId = "18b88279-76a8-49af-a094-b1a77687c15e",
    [string]$ProjectRoot = "$PSScriptRoot\..",
    [string]$DestinationZip = "$ProjectRoot\agent-trace.zip"
)

$ErrorActionPreference = "Stop"

Write-Host "=== Antigravity Agent Trace Packaging Utility ===" -ForegroundColor Cyan
$SourceBrainDir = "$env:USERPROFILE\.gemini\antigravity\brain\$ConversationId"
Write-Host "Source Brain Path: $SourceBrainDir"
Write-Host "Destination ZIP:   $DestinationZip"

if (-not (Test-Path $SourceBrainDir)) {
    Write-Error "Source conversation directory not found at $SourceBrainDir"
    exit 1
}

$StagingRoot = "$env:TEMP\agent-trace-staging"
$StagingAgentTrace = "$StagingRoot\agent-trace"
$StagingTarget = "$StagingAgentTrace\antigravity\$ConversationId"

if (Test-Path $StagingRoot) {
    Remove-Item -Path $StagingRoot -Recurse -Force
}

New-Item -ItemType Directory -Path $StagingTarget -Force | Out-Null
Write-Host "Copying original conversation files to staging..." -ForegroundColor Yellow

# Copy files while excluding __pycache__ and temp binaries
Get-ChildItem -Path $SourceBrainDir -Recurse | Where-Object {
    $_.FullName -notmatch '__pycache__' -and $_.Extension -notmatch '\.pyc$'
} | ForEach-Object {
    $rel = $_.FullName.Substring($SourceBrainDir.Length)
    $dest = "$StagingTarget$rel"
    if ($_.PSIsContainer) {
        if (-not (Test-Path $dest)) {
            New-Item -ItemType Directory -Path $dest -Force | Out-Null
        }
    } else {
        $parent = Split-Path $dest
        if (-not (Test-Path $parent)) {
            New-Item -ItemType Directory -Path $parent -Force | Out-Null
        }
        Copy-Item -Path $_.FullName -Destination $dest -Force
    }
}

# Copy root log.txt
$RootLog = "$ProjectRoot\log.txt"
if (Test-Path $RootLog) {
    Copy-Item -Path $RootLog -Destination "$StagingTarget\log.txt" -Force
}

# Preserve existing zip if present
if (Test-Path $DestinationZip) {
    $bak = "$DestinationZip.bak"
    Write-Host "Preserving existing zip to $bak..." -ForegroundColor Gray
    Copy-Item -Path $DestinationZip -Destination $bak -Force
}

Write-Host "Compressing archive to $DestinationZip..." -ForegroundColor Yellow
Compress-Archive -Path $StagingAgentTrace -DestinationPath $DestinationZip -Force

# Clean staging
Remove-Item -Path $StagingRoot -Recurse -Force

# Validation
if (Test-Path $DestinationZip) {
    $zipSize = (Get-Item $DestinationZip).Length
    Write-Host "[SUCCESS] agent-trace.zip created successfully!" -ForegroundColor Green
    Write-Host "  Path: $DestinationZip"
    Write-Host "  Size: $([math]::Round($zipSize / 1MB, 2)) MB ($zipSize bytes)"
} else {
    Write-Error "Failed to create agent-trace.zip"
}

