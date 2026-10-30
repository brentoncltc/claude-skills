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
- Akiflow tasks you **completed**, except in a project named "Personal" (optional)

With a Garmin watch connected (optional, below), the nudge changes with how you feel:

| Garmin says | Nudge |
|---|---|
| Stress above 50, or heart rate 20+ bpm over resting | "You're wired, not tired. Water and a walk?" |
| Body Battery below 30 | "Body Battery's at 22. Need a coffee? Or maybe a Celsius?" |
| Neither, or no Garmin | "Need a coffee? Or maybe a Celsius?" |

No Celsius after noon: from 12:00 on it only offers coffee.

It keeps the last 200 hourly scores in a local JSON file and compares each hour to their mean.
It only records samples and asks between 7:00 AM and 2:00 PM local time, Monday–Friday.
It starts comparing after the first recorded hour, so early averages are noisy.

## Requirements

| Need | Why | Check |
|---|---|---|
| [Claude Code](https://docs.claude.com/en/docs/claude-code) CLI, signed in with a claude.ai account | Runs the check headless (`claude -p`) | `claude --version` |
| Microsoft 365 connector enabled on your claude.ai account | Counts sent emails | Ask Claude Code to call the Microsoft 365 `get_me` tool |
| Akiflow connector on your claude.ai account (optional) | Counts tasks completed; counts 0 without it | Ask Claude Code to call the Akiflow `get_user_context` tool |
| [GitHub CLI](https://cli.github.com/), authenticated | Reads your GitHub activity | `gh auth status` |
| Python 3.9+ | Scoring and state | `python3 --version` |
| A scheduler that runs on your machine | Hourly runs | see below |
| For Windows toasts: WSL, with Windows interop on (the default) | `notify.sh` calls `powershell.exe` | `ls /mnt/c/Windows/System32/WindowsPowerShell` |

Not supported: **Claude Desktop scheduled tasks** and **cloud routines**. Both run in a
sandbox that can't reach your `gh` login, your local files, or WSL.

GitHub counts come from your public events feed plus private events your `gh` token can see.
GitHub can delay events by a few minutes, occasionally longer.

Akiflow's tool filters completed tasks by the date they were scheduled, not the date you
finished them. The check looks back 7 days, so a task scheduled more than a week ago or never
scheduled (inbox only) isn't counted when you complete it. To count personal tasks too, change
the "Personal" exclusion in `SKILL.md` step 3.

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

## Garmin (optional)

Uses the unofficial [`garminconnect`](https://github.com/cyberjunky/python-garminconnect)
library against your own Garmin Connect account. It's not a Garmin-supported API and can
break when Garmin changes things. Data is only as fresh as your watch's last sync through the
phone app, so the last few minutes of an hour are often missing.

```bash
cd ~/.claude/skills/coffee-check
python3 -m venv .venv && .venv/bin/pip install garminconnect
.venv/bin/python garmin.py login     # interactive: email, password, MFA code
```

`login` saves refreshable tokens to `~/.garminconnect` (owner-only permissions; set
`GARMINTOKENS` to move them). Your password is not stored. Once the tokens exist,
`coffee_check.py` uses Garmin automatically. Delete the folder to turn it off.
Test with:

```bash
.venv/bin/python garmin.py window --start 2026-01-05T14:00:00Z --end 2026-01-05T15:00:00Z
```

Thresholds (`WIRED_STRESS`, `WIRED_HR_OVER_RHR`, `TIRED_BODY_BATTERY`, `NO_CELSIUS_FROM`) are
constants at the top of `coffee_check.py`. If Garmin fails, the check runs without it and logs
`garmin_error=...`.

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
| `garmin.py` | Optional Garmin login and heart rate / stress / Body Battery readings |
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

- Stores counts only, never email subjects, recipients or PR titles. With Garmin, it also
  stores the hour's average heart rate, stress and Body Battery.
- Read-only: it never sends, posts or changes anything in GitHub or Microsoft 365.
- `run.sh` allows Claude only the two scripts, the skill, the Outlook search tool and the
  Akiflow schedule reader.
- Each run is one headless Claude Code session on your account: 8 a day on weekdays.
