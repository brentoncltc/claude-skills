#!/usr/bin/env bash
# Scheduler entry point: runs /coffee-check headless and appends to the log.
set -u
export PATH="$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
log="$HOME/.claude/productivity/coffee-check.log"
mkdir -p "$(dirname "$log")"
cd "$(dirname "$log")"
{
  echo "=== $(date -Is)"
  # The Bash rules must match the commands in SKILL.md character for character.
  claude -p "/coffee-check" --allowedTools \
    "Skill(coffee-check)" \
    "Bash(python3 ~/.claude/skills/coffee-check/coffee_check.py:*)" \
    "Bash(~/.claude/skills/coffee-check/notify.sh:*)" \
    "mcp__claude_ai_Microsoft_365__outlook_email_search"
} >>"$log" 2>&1
