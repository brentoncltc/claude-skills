# coffee-check

Every hour on weekdays, Claude checks how much you got done in the last hour. If you're more
than 30% below your average, it pops up a desktop notification:

> Last hour: 2 vs your average of 6.4. Need a coffee? Or maybe a Celsius?

## What it measures

Score for the last 60 minutes = sum of:

- GitHub PRs you **opened**
- GitHub PRs you **reviewed** (one per PR)
- GitHub PRs you **merged**
- Microsoft 365 emails you **sent**

It keeps the last 200 hourly scores in a local JSON file and compares each hour to their mean.
It only records samples and asks between 7:00 AM and 2:00 PM local time, Monday–Friday.
It starts comparing after the first recorded hour, so early averages are noisy.

## Requirements

| Need | Why | Check |
|---|---|---|
| [Claude Code](https://docs.claude.com/en/docs/claude-code) CLI, signed in with a claude.ai account | Runs the check headless (`claude -p`) | `claude --version` |
| Microsoft 365 connector enabled on your claude.ai account | Counts sent emails | Ask Claude Code to call the Microsoft 365 `get_me` tool |
| [GitHub CLI](https://cli.github.com/), authenticated | Reads your GitHub activity | `gh auth status` |
| Python 3.9+ | Scoring and state | `python3 --version` |
| A scheduler that runs on your machine | Hourly runs | see below |
| For Windows toasts: WSL, with Windows interop on (the default) | `notify.sh` calls `powershell.exe` | `ls /mnt/c/Windows/System32/WindowsPowerShell` |

Not supported: **Claude Desktop scheduled tasks** and **cloud routines**. Both run in a
sandbox that can't reach your `gh` login, your local files, or WSL.

GitHub counts come from your public events feed plus private events your `gh` token can see.
GitHub can delay events by a few minutes, occasionally longer.

## Install

```bash
git clone https://github.com/brentoncltc/claude-skills.git ~/repos/claude-skills
mkdir -p ~/.claude/skills
ln -s ~/repos/claude-skills/skills/coffee-check ~/.claude/skills/coffee-check
chmod +x ~/.claude/skills/coffee-check/*.sh ~/.claude/skills/coffee-check/*.py
```

The skill must sit at `~/.claude/skills/coffee-check`: `SKILL.md` and `run.sh` use that path.

Test it once by hand. It records a sample if you're inside the 7a–2p weekday window.

```bash
~/.claude/skills/coffee-check/run.sh && tail -3 ~/.claude/productivity/coffee-check.log
~/.claude/skills/coffee-check/notify.sh "Coffee check" "Test notification"
```

## Schedule it

### Windows + WSL (Task Scheduler)

From PowerShell or cmd on Windows. Replace `<distro>` (`wsl -l -v` lists them) and `<user>`:

```
schtasks /create /tn "coffee-check" /sc weekly /d MON,TUE,WED,THU,FRI /st 07:00 /ri 60 /du 07:30 /f ^
  /tr "C:\Windows\System32\conhost.exe --headless C:\Windows\System32\wsl.exe -d <distro> -- /home/<user>/.claude/skills/coffee-check/run.sh"
```

`conhost --headless` stops a console window from flashing every hour. The task runs only while
you're signed in, which is what lets the toast show. Remove it with
`schtasks /delete /tn coffee-check /f`.

### macOS / Linux (cron)

```
0 7-14 * * 1-5 $HOME/.claude/skills/coffee-check/run.sh
```

On macOS, `notify.sh` uses `osascript`; on Linux, `notify-send`.

## Files

| File | Role |
|---|---|
| `SKILL.md` | Steps Claude follows on `/coffee-check` |
| `coffee_check.py` | Time window, GitHub counts, mean and threshold, state file |
| `notify.sh` | Desktop notification (WSL, macOS, Linux) |
| `run.sh` | Scheduler entry point: `claude -p /coffee-check` with a narrow tool allowlist |

State: `~/.claude/productivity/coffee-check.json`. Log: `~/.claude/productivity/coffee-check.log`.

## Settings

Environment variables (set them in `run.sh` or your scheduler):

- `COFFEE_CHECK_GH_LOGIN`: your GitHub login. Default: looked up with `gh api user`.
- `COFFEE_CHECK_STATE`: state file path.

Thresholds are constants at the top of `coffee_check.py`: `THRESHOLD` (0.7), `ASK_HOURS`
(7–14), `MIN_SAMPLES` (1), `MAX_SAMPLES` (200). Timezone is your system's local time.

## Privacy and cost

- Stores counts only, never email subjects, recipients or PR titles.
- Read-only: it never sends, posts or changes anything in GitHub or Microsoft 365.
- `run.sh` allows Claude only the two scripts, the skill and the Outlook search tool.
- Each run is one headless Claude Code session on your account: 8 a day on weekdays.
