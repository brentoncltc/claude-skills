#!/usr/bin/env bash
# Show a desktop notification. Usage: notify.sh "Title" "Message"
# WSL: Windows toast via powershell.exe, reminder style so it stays on screen until
# dismissed. macOS: osascript. Linux: notify-send.
set -euo pipefail
ps=/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe

if [ -x "$ps" ]; then
  title=${1//\'/\'\'}
  msg=${2//\'/\'\'}
  # scenario='reminder' keeps the toast up; Windows only honors it when the toast has a button.
  script="
\$ProgressPreference = 'SilentlyContinue'
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > \$null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] > \$null
\$title = [System.Security.SecurityElement]::Escape('$title')
\$msg = [System.Security.SecurityElement]::Escape('$msg')
\$x = New-Object Windows.Data.Xml.Dom.XmlDocument
\$x.LoadXml(\"<toast scenario='reminder'><visual><binding template='ToastGeneric'><text>\$title</text><text>\$msg</text></binding></visual><actions><action activationType='system' arguments='dismiss' content=''/></actions></toast>\")
\$app = '{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe'
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier(\$app).Show([Windows.UI.Notifications.ToastNotification]::new(\$x))
"
  "$ps" -NoProfile -NonInteractive -EncodedCommand "$(printf '%s' "$script" | iconv -t UTF-16LE | base64 -w0)"
elif command -v osascript >/dev/null; then
  osascript -e 'on run argv' -e 'display notification (item 2 of argv) with title (item 1 of argv)' -e 'end run' "$1" "$2"
elif command -v notify-send >/dev/null; then
  notify-send "$1" "$2"
else
  echo "notify.sh: no notifier found" >&2
  exit 1
fi
