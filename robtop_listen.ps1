# RobTop's ears, with no internet and no API key: Windows' own speech recognition, limited to a
# short list of phrases, sends the matching command to the robot (dispatcher or teleoperation) and speaks a short reply.
#
#   powershell -ExecutionPolicy Bypass -File robtop_listen.ps1            # say "RobTop, wave" or just "wave"
#   powershell -ExecutionPolicy Bypass -File robtop_listen.ps1 -Sure 0.8  # stricter, for a noisy room
#   powershell -ExecutionPolicy Bypass -File robtop_listen.ps1 -NeedName  # only react to phrases that start with "RobTop"
#
# A fixed phrase list is the noise filter: anything that is not one of these phrases is ignored,
# and a phrase heard with less confidence than -Sure is ignored too. Ctrl+C to quit.
param([double]$Sure = 0.70, [switch]$NeedName, [int]$Port = 8765)

Add-Type -AssemblyName System.Speech

# phrase -> (line for the robot, what RobTop says). No phrase ever sends 'filter off': that switch is
# only for the keypad, the dashboard or a typed line. 'steady off' freezes the arm in steady.py.
# 'run wave {}', not bare 'run wave', which steady.py reads as the keypad's steady toggle.
$commands = [ordered]@{
    "wave"             = @('run wave {}', 'Hello!')
    "say hi"           = @('run wave {}', 'Hello!')
    "nod"              = @('run gesture {"name": "nod"}', 'Yes.')
    "shake your head"  = @('run gesture {"name": "shake"}', 'No.')
    "fist bump"        = @('run gesture {"name": "fist_bump"}', 'Boom.')
    "high five"        = @('run gesture {"name": "high_five"}', 'Up top!')
    "dance"            = @('run gesture {"name": "dance"}', 'Watch this.')
    "take this"        = @('run hand {"do": "take"}', 'Give it here.')
    "hold this"        = @('run hand {"do": "take"}', 'I have it.')
    "give it back"     = @('run hand {"do": "give"}', 'Here you go.')
    "hand it to me"    = @('run hand {"do": "give"}', 'Here you go.')
    "give it to me"    = @('run hand {"do": "give"}', 'Here you go.')
    "drop it"          = @('run hand {"do": "drop"}', 'Dropping.')
    "let go"           = @('run hand {"do": "drop"}', 'Letting go.')
    "go home"          = @('home', 'Going home.')
    "stop"             = @('stop', 'Stopped.')
    "steady on"        = @('steady on', 'Steadying your hand.')
    "filter on"        = @('steady on', 'Steadying your hand.')
    "steady off"       = @('steady off', 'Holding still.')
    "filter off"       = @('steady off', 'Holding still.')
    "hold"             = @('hold on', 'Holding still.')
    "release"          = @('hold off', 'Released.')
    "start the test"   = @('test', 'Starting the ten second test. Hold still.')
}

function Send-Line([string]$line) {
    try {
        $client = New-Object System.Net.Sockets.TcpClient('127.0.0.1', $Port)
        $stream = $client.GetStream()
        $writer = New-Object System.IO.StreamWriter($stream); $writer.NewLine = "`n"; $writer.AutoFlush = $true
        $reader = New-Object System.IO.StreamReader($stream)
        $writer.WriteLine($line)
        $reply = $reader.ReadLine()
        $client.Close()
        return $reply
    } catch { return '{"ok": false, "reason": "no dispatcher"}' }
}

$voice = New-Object System.Speech.Synthesis.SpeechSynthesizer
$ears = New-Object System.Speech.Recognition.SpeechRecognitionEngine([System.Globalization.CultureInfo]'en-US')
$phrases = New-Object System.Speech.Recognition.Choices
$phrases.Add([string[]]$commands.Keys)
$builder = New-Object System.Speech.Recognition.GrammarBuilder
$builder.Culture = [System.Globalization.CultureInfo]'en-US'
$name = New-Object System.Speech.Recognition.GrammarBuilder((New-Object System.Speech.Recognition.Choices(,[string[]]@('RobTop', 'Rob Top'))))
if ($NeedName) { $builder.Append($name) } else { $builder.Append($name, 0, 1) }  # the name is optional unless -NeedName
$builder.Append($phrases)
$ears.LoadGrammar((New-Object System.Speech.Recognition.Grammar($builder)))
$ears.SetInputToDefaultAudioDevice()

Write-Host "RobTop is listening. Phrases: $($commands.Keys -join ', '). Ctrl+C to quit."
while ($true) {
    $heard = $ears.Recognize([TimeSpan]::FromSeconds(4))
    if ($null -eq $heard) { continue }
    $text = ($heard.Text -replace '^Rob ?Top\s+', '')
    # not "$sure": PowerShell names ignore case, so that would overwrite the -Sure threshold itself
    $shown = [math]::Round($heard.Confidence, 2)
    if ($heard.Confidence -lt $Sure -or -not $commands.Contains($text)) {
        Write-Host "  (ignored: '$($heard.Text)' at $shown)"
        continue
    }
    $line, $say = $commands[$text]
    $reply = Send-Line $line
    Write-Host "heard '$($heard.Text)' ($shown) -> $line -> $reply"
    if ($reply -match '"busy"') { $say = 'One moment.' }
    elseif ($reply -match 'no dispatcher') { $say = 'My arm is not switched on.' }
    $voice.Speak($say)   # blocks, so RobTop does not hear its own voice as a command
}
