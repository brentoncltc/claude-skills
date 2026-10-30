#!/usr/bin/env bash
# Show a desktop notification. Usage: notify.sh "Title" "Message"
# WSL: Windows toast via powershell.exe. macOS: osascript. Linux: notify-send.
set -euo pipefail
ps=/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe

if [ -x "$ps" ]; then
  title=${1//\'/\'\'}
  msg=${2//\'/\'\'}
  script="
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > \$null
\$x = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
\$t = \$x.GetElementsByTagName('text')
\$t.Item(0).AppendChild(\$x.CreateTextNode('$title')) > \$null
\$t.Item(1).AppendChild(\$x.CreateTextNode('$msg')) > \$null
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
