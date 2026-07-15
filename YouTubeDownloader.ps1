param(
    [switch]$SelfTest
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

$script:AppRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$script:ToolsDir = Join-Path $script:AppRoot 'tools'
$script:YtDlpPath = Join-Path $script:ToolsDir 'yt-dlp.exe'
$script:FfmpegRoot = Join-Path $script:ToolsDir 'ffmpeg'
$script:Process = $null
$script:StdoutTask = $null
$script:StderrTask = $null

function Test-YouTubeUrl {
    param([string]$Value)

    if ([string]::IsNullOrWhiteSpace($Value)) {
        return $false
    }

    try {
        $uri = [Uri]$Value.Trim()
    }
    catch {
        return $false
    }

    if ($uri.Scheme -ne 'https' -and $uri.Scheme -ne 'http') {
        return $false
    }

    $hostName = $uri.DnsSafeHost.ToLowerInvariant()
    return $hostName -eq 'youtu.be' -or
        $hostName -eq 'youtube.com' -or
        $hostName.EndsWith('.youtube.com') -or
        $hostName -eq 'youtube-nocookie.com' -or
        $hostName.EndsWith('.youtube-nocookie.com')
}

if ($SelfTest) {
    $testCases = @(
        @{ Url = 'https://www.youtube.com/watch?v=dQw4w9WgXcQ'; Expected = $true },
        @{ Url = 'https://youtu.be/dQw4w9WgXcQ'; Expected = $true },
        @{ Url = 'https://music.youtube.com/watch?v=dQw4w9WgXcQ'; Expected = $true },
        @{ Url = 'https://example.com/video'; Expected = $false },
        @{ Url = 'not-a-url'; Expected = $false }
    )

    foreach ($testCase in $testCases) {
        $actual = Test-YouTubeUrl $testCase.Url
        if ($actual -ne $testCase.Expected) {
            throw "Self-test failed for URL: $($testCase.Url)"
        }
    }

    Write-Output 'Self-test OK'
    exit 0
}

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[System.Windows.Forms.Application]::EnableVisualStyles()
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

function Set-Status {
    param(
        [string]$Text,
        [System.Drawing.Color]$Color = [System.Drawing.Color]::FromArgb(55, 65, 81)
    )

    $statusLabel.Text = $Text
    $statusLabel.ForeColor = $Color
    [System.Windows.Forms.Application]::DoEvents()
}

function Add-Log {
    param([string]$Text)

    if (-not [string]::IsNullOrWhiteSpace($Text)) {
        $logBox.AppendText($Text.TrimEnd() + [Environment]::NewLine)
        $logBox.SelectionStart = $logBox.TextLength
        $logBox.ScrollToCaret()
    }
}

function Set-Busy {
    param([bool]$Busy)

    $downloadButton.Enabled = -not $Busy
    $browseButton.Enabled = -not $Busy
    $urlBox.Enabled = -not $Busy
    $folderBox.Enabled = -not $Busy
    $cancelButton.Enabled = $Busy
    $progressBar.Style = if ($Busy) { 'Marquee' } else { 'Blocks' }
    $progressBar.MarqueeAnimationSpeed = if ($Busy) { 25 } else { 0 }
}

function Save-RemoteFile {
    param(
        [string]$Url,
        [string]$Destination
    )

    $temporaryPath = $Destination + '.part'
    $webClient = $null
    Remove-Item $temporaryPath -Force -ErrorAction SilentlyContinue
    try {
        $webClient = New-Object Net.WebClient
        $webClient.Headers.Add('User-Agent', 'Mozilla/5.0 YouTubeDownloader')
        $webClient.DownloadFile($Url, $temporaryPath)
        Move-Item $temporaryPath $Destination -Force
    }
    finally {
        if ($null -ne $webClient) {
            $webClient.Dispose()
        }
        Remove-Item $temporaryPath -Force -ErrorAction SilentlyContinue
    }
}

function Find-Ffmpeg {
    if (-not (Test-Path $script:FfmpegRoot)) {
        return $null
    }

    return Get-ChildItem $script:FfmpegRoot -Recurse -File -Filter 'ffmpeg.exe' -ErrorAction SilentlyContinue |
        Select-Object -First 1 -ExpandProperty FullName
}

function Ensure-Dependencies {
    New-Item $script:ToolsDir -ItemType Directory -Force | Out-Null

    if (-not (Test-Path $script:YtDlpPath)) {
        Set-Status 'Pierwsze uruchomienie: pobieram yt-dlp...'
        Save-RemoteFile `
            'https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe' `
            $script:YtDlpPath
    }

    $ffmpegPath = Find-Ffmpeg
    if ($null -eq $ffmpegPath) {
        Set-Status 'Pierwsze uruchomienie: pobieram ffmpeg (moze potrwac chwile)...'
        $archivePath = Join-Path $script:ToolsDir 'ffmpeg.zip'
        Remove-Item $script:FfmpegRoot -Recurse -Force -ErrorAction SilentlyContinue
        New-Item $script:FfmpegRoot -ItemType Directory -Force | Out-Null
        try {
            Save-RemoteFile `
                'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip' `
                $archivePath
            Expand-Archive -Path $archivePath -DestinationPath $script:FfmpegRoot -Force
        }
        finally {
            Remove-Item $archivePath -Force -ErrorAction SilentlyContinue
        }
        $ffmpegPath = Find-Ffmpeg
    }

    if (-not (Test-Path $script:YtDlpPath)) {
        throw 'Nie udalo sie przygotowac yt-dlp.'
    }
    if ([string]::IsNullOrWhiteSpace($ffmpegPath) -or -not (Test-Path $ffmpegPath)) {
        throw 'Nie udalo sie przygotowac ffmpeg.'
    }

    return $ffmpegPath
}

function Stop-Download {
    if ($null -ne $script:Process -and -not $script:Process.HasExited) {
        try {
            $script:Process.Kill()
            Set-Status 'Pobieranie anulowane.' ([System.Drawing.Color]::DarkOrange)
            Add-Log 'Anulowano przez uzytkownika.'
        }
        catch {
            Add-Log "Nie udalo sie zatrzymac procesu: $($_.Exception.Message)"
        }
    }
}

$form = New-Object System.Windows.Forms.Form
$form.Text = 'YouTube Downloader Full HD'
$form.Size = New-Object System.Drawing.Size(720, 500)
$form.MinimumSize = New-Object System.Drawing.Size(640, 440)
$form.StartPosition = 'CenterScreen'
$form.Font = New-Object System.Drawing.Font('Segoe UI', 10)
$form.BackColor = [System.Drawing.Color]::FromArgb(248, 250, 252)

$titleLabel = New-Object System.Windows.Forms.Label
$titleLabel.Text = 'YouTube Downloader'
$titleLabel.Font = New-Object System.Drawing.Font('Segoe UI Semibold', 18)
$titleLabel.AutoSize = $true
$titleLabel.Location = New-Object System.Drawing.Point(24, 18)
$form.Controls.Add($titleLabel)

$qualityLabel = New-Object System.Windows.Forms.Label
$qualityLabel.Text = 'Najlepsza jakosc do 1080p + dzwiek, wynik MP4'
$qualityLabel.AutoSize = $true
$qualityLabel.ForeColor = [System.Drawing.Color]::FromArgb(75, 85, 99)
$qualityLabel.Location = New-Object System.Drawing.Point(27, 57)
$form.Controls.Add($qualityLabel)

$urlLabel = New-Object System.Windows.Forms.Label
$urlLabel.Text = 'Link do filmu YouTube'
$urlLabel.AutoSize = $true
$urlLabel.Location = New-Object System.Drawing.Point(24, 94)
$form.Controls.Add($urlLabel)

$urlBox = New-Object System.Windows.Forms.TextBox
$urlBox.Anchor = 'Top, Left, Right'
$urlBox.Location = New-Object System.Drawing.Point(28, 119)
$urlBox.Size = New-Object System.Drawing.Size(646, 30)
$form.Controls.Add($urlBox)

$folderLabel = New-Object System.Windows.Forms.Label
$folderLabel.Text = 'Folder docelowy'
$folderLabel.AutoSize = $true
$folderLabel.Location = New-Object System.Drawing.Point(24, 162)
$form.Controls.Add($folderLabel)

$defaultFolder = Join-Path ([Environment]::GetFolderPath('Desktop')) 'YouTube'
$folderBox = New-Object System.Windows.Forms.TextBox
$folderBox.Anchor = 'Top, Left, Right'
$folderBox.Location = New-Object System.Drawing.Point(28, 187)
$folderBox.Size = New-Object System.Drawing.Size(535, 30)
$folderBox.Text = $defaultFolder
$form.Controls.Add($folderBox)

$browseButton = New-Object System.Windows.Forms.Button
$browseButton.Anchor = 'Top, Right'
$browseButton.Text = 'Wybierz...'
$browseButton.Location = New-Object System.Drawing.Point(574, 185)
$browseButton.Size = New-Object System.Drawing.Size(100, 32)
$form.Controls.Add($browseButton)

$downloadButton = New-Object System.Windows.Forms.Button
$downloadButton.Text = 'Pobierz film'
$downloadButton.Location = New-Object System.Drawing.Point(28, 235)
$downloadButton.Size = New-Object System.Drawing.Size(160, 40)
$downloadButton.BackColor = [System.Drawing.Color]::FromArgb(220, 38, 38)
$downloadButton.ForeColor = [System.Drawing.Color]::White
$downloadButton.FlatStyle = 'Flat'
$downloadButton.FlatAppearance.BorderSize = 0
$form.Controls.Add($downloadButton)

$cancelButton = New-Object System.Windows.Forms.Button
$cancelButton.Text = 'Anuluj'
$cancelButton.Location = New-Object System.Drawing.Point(198, 235)
$cancelButton.Size = New-Object System.Drawing.Size(100, 40)
$cancelButton.Enabled = $false
$form.Controls.Add($cancelButton)

$progressBar = New-Object System.Windows.Forms.ProgressBar
$progressBar.Anchor = 'Top, Left, Right'
$progressBar.Location = New-Object System.Drawing.Point(28, 290)
$progressBar.Size = New-Object System.Drawing.Size(646, 12)
$form.Controls.Add($progressBar)

$statusLabel = New-Object System.Windows.Forms.Label
$statusLabel.Anchor = 'Top, Left, Right'
$statusLabel.Text = 'Gotowy.'
$statusLabel.Location = New-Object System.Drawing.Point(25, 312)
$statusLabel.Size = New-Object System.Drawing.Size(649, 24)
$form.Controls.Add($statusLabel)

$logBox = New-Object System.Windows.Forms.TextBox
$logBox.Anchor = 'Top, Bottom, Left, Right'
$logBox.Location = New-Object System.Drawing.Point(28, 340)
$logBox.Size = New-Object System.Drawing.Size(646, 95)
$logBox.Multiline = $true
$logBox.ReadOnly = $true
$logBox.ScrollBars = 'Vertical'
$logBox.BackColor = [System.Drawing.Color]::White
$form.Controls.Add($logBox)

$folderDialog = New-Object System.Windows.Forms.FolderBrowserDialog
$folderDialog.Description = 'Wybierz folder na pobrane filmy'
$folderDialog.ShowNewFolderButton = $true

$browseButton.Add_Click({
    if (Test-Path $folderBox.Text -PathType Container) {
        $folderDialog.SelectedPath = $folderBox.Text
    }
    if ($folderDialog.ShowDialog() -eq 'OK') {
        $folderBox.Text = $folderDialog.SelectedPath
    }
})

$cancelButton.Add_Click({ Stop-Download })

$timer = New-Object System.Windows.Forms.Timer
$timer.Interval = 300
$timer.Add_Tick({
    if ($null -eq $script:Process -or -not $script:Process.HasExited) {
        return
    }

    $timer.Stop()
    $exitCode = $script:Process.ExitCode
    $standardOutput = $script:StdoutTask.Result
    $standardError = $script:StderrTask.Result
    Add-Log $standardOutput
    Add-Log $standardError

    if ($exitCode -eq 0) {
        Set-Status 'Gotowe. Film zapisany na dysku.' ([System.Drawing.Color]::DarkGreen)
        [System.Media.SystemSounds]::Asterisk.Play()
    }
    elseif ($statusLabel.Text -ne 'Pobieranie anulowane.') {
        Set-Status "Blad pobierania (kod $exitCode). Szczegoly sa ponizej." ([System.Drawing.Color]::DarkRed)
        [System.Media.SystemSounds]::Hand.Play()
    }

    $script:Process.Dispose()
    $script:Process = $null
    $script:StdoutTask = $null
    $script:StderrTask = $null
    Set-Busy $false
})

$downloadButton.Add_Click({
    $url = $urlBox.Text.Trim()
    $outputFolder = $folderBox.Text.Trim()

    if (-not (Test-YouTubeUrl $url)) {
        [System.Windows.Forms.MessageBox]::Show(
            'Wklej poprawny link do filmu z YouTube.',
            'Niepoprawny link',
            'OK',
            'Warning'
        ) | Out-Null
        return
    }
    if ([string]::IsNullOrWhiteSpace($outputFolder)) {
        [System.Windows.Forms.MessageBox]::Show('Wybierz folder docelowy.', 'Brak folderu', 'OK', 'Warning') | Out-Null
        return
    }

    try {
        Set-Busy $true
        $logBox.Clear()
        $ffmpegPath = Ensure-Dependencies
        New-Item $outputFolder -ItemType Directory -Force | Out-Null

        $arguments = @(
            '--no-playlist'
            '--newline'
            '--no-overwrites'
            '--windows-filenames'
            '--merge-output-format mp4'
            '-f "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/bv*[height<=1080]+ba/b[height<=1080]"'
            "--ffmpeg-location `"$ffmpegPath`""
            "-P `"$outputFolder`""
            '-o "%(title)s [%(id)s].%(ext)s"'
            "`"$url`""
        ) -join ' '

        $startInfo = New-Object System.Diagnostics.ProcessStartInfo
        $startInfo.FileName = $script:YtDlpPath
        $startInfo.Arguments = $arguments
        $startInfo.UseShellExecute = $false
        $startInfo.CreateNoWindow = $true
        $startInfo.RedirectStandardOutput = $true
        $startInfo.RedirectStandardError = $true
        $startInfo.StandardOutputEncoding = [Text.Encoding]::UTF8
        $startInfo.StandardErrorEncoding = [Text.Encoding]::UTF8

        $script:Process = New-Object System.Diagnostics.Process
        $script:Process.StartInfo = $startInfo
        if (-not $script:Process.Start()) {
            throw 'Nie udalo sie uruchomic yt-dlp.'
        }

        $script:StdoutTask = $script:Process.StandardOutput.ReadToEndAsync()
        $script:StderrTask = $script:Process.StandardError.ReadToEndAsync()
        Set-Status 'Pobieram film do maksymalnie 1080p...'
        Add-Log "Folder: $outputFolder"
        $timer.Start()
    }
    catch {
        Set-Status 'Nie udalo sie rozpoczac pobierania.' ([System.Drawing.Color]::DarkRed)
        Add-Log $_.Exception.Message
        Set-Busy $false
        if ($null -ne $script:Process) {
            try {
                if (-not $script:Process.HasExited) {
                    $script:Process.Kill()
                }
            }
            catch {}
            $script:Process.Dispose()
            $script:Process = $null
        }
    }
})

$form.Add_FormClosing({
    if ($null -ne $script:Process -and -not $script:Process.HasExited) {
        $choice = [System.Windows.Forms.MessageBox]::Show(
            'Pobieranie nadal trwa. Przerwac i zamknac program?',
            'Trwa pobieranie',
            'YesNo',
            'Question'
        )
        if ($choice -ne 'Yes') {
            $_.Cancel = $true
            return
        }
        Stop-Download
    }
})

[void]$form.ShowDialog()
