param(
    [string]$ScenesFile = 'assets\pitch-scenes.json',
    [string]$OutputDirectory = 'artifacts\pitch'
)
$ErrorActionPreference = 'Stop'
$proofTrailRoot = Split-Path -Parent $PSScriptRoot
$proofTrailScenes = Get-Content -LiteralPath (Join-Path $proofTrailRoot $ScenesFile) -Raw -Encoding UTF8 | ConvertFrom-Json
$proofTrailOutput = Join-Path $proofTrailRoot $OutputDirectory
New-Item -ItemType Directory -Path $proofTrailOutput -Force | Out-Null
Add-Type -AssemblyName System.Speech
$proofTrailNarrator = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {
    $proofTrailNarrator.SelectVoice('Microsoft Huihui Desktop')
    $proofTrailNarrator.Rate = 1
    $proofTrailNarrator.Volume = 100
    for ($proofTrailIndex = 0; $proofTrailIndex -lt $proofTrailScenes.Count; $proofTrailIndex++) {
        $proofTrailWave = Join-Path $proofTrailOutput ('scene-{0:D2}.wav' -f ($proofTrailIndex + 1))
        $proofTrailNarrator.SetOutputToWaveFile($proofTrailWave)
        $proofTrailNarrator.Speak($proofTrailScenes[$proofTrailIndex].narration)
        $proofTrailNarrator.SetOutputToNull()
    }
    Write-Output 'Chinese synthetic narration written locally; no audio playback, upload or voice imitation.'
} finally {
    $proofTrailNarrator.Dispose()
}
