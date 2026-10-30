---
name: coffee-check
description: Hourly productivity check. Counts GitHub PRs created/reviewed/merged and Microsoft 365 sent emails in the last hour, compares to a rolling mean, and asks about coffee if more than 30% below it. Meant to run headless from a scheduler via run.sh.
disable-model-invocation: true
---

Scripts live in `~/.claude/skills/coffee-check/`. Run them with the exact command forms
below (they match the allowed-tools rules in run.sh). Do not use any other tools.

1. Get the window:
   `python3 ~/.claude/skills/coffee-check/coffee_check.py window`
   It prints `start`, `end` (UTC) and their local-time equivalents.

2. Count sent emails in the window with `mcp__claude_ai_Microsoft_365__outlook_email_search`:
   `folderName: "Sent Items"`, `afterDateTime: <start>`, `beforeDateTime: <end>`, `limit: 25`,
   `offset: 0`. No `query`, no `order`. Page with `nextOffset`/`nextCursor` until done.
   Count only messages whose sent/received time is inside the window.
   If the search errors or the tool is unavailable, print "coffee-check: M365 failed: <reason>"
   and stop. Do not record a sample.

3. Record and score:
   `python3 ~/.claude/skills/coffee-check/coffee_check.py record --start <start> --end <end> --emails <count>`
   If it prints `"ok": false`, print the error and stop.

4. If the result has `"ask": true`, run with its `message` text verbatim:
   `~/.claude/skills/coffee-check/notify.sh "Coffee check" "<message>"`

5. End with one line: `coffee-check: score=<score> mean=<mean> verdict=<verdict>`, plus
   ` garmin=<hr_avg>bpm/stress <stress_avg>/bb <body_battery>` when `garmin` has readings, or
   ` garmin_error=<error>` when it has an error. A Garmin error never stops the run.

Read-only except for the state file. Never send email, post, or change anything in GitHub or M365.
