param(
    [Parameter(Mandatory = $true)]
    [string]$AudioPath
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
Add-Type -AssemblyName System.Speech

$culture = [Globalization.CultureInfo]::GetCultureInfo("zh-CN")
$recognizer = [System.Speech.Recognition.SpeechRecognitionEngine]::new($culture)
try {
    $recognizer.LoadGrammar(
        [System.Speech.Recognition.DictationGrammar]::new()
    )
    $recognizer.SetInputToWaveFile($AudioPath)
    $result = $recognizer.Recognize([TimeSpan]::FromSeconds(8))
    if ($null -ne $result) {
        [Console]::Out.Write($result.Text)
    }
}
finally {
    $recognizer.Dispose()
}
