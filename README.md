# claude-skills

Public [Claude Code skills](https://docs.claude.com/en/docs/claude-code/skills) by Brenton Chamberland.

| Skill | What it does |
|---|---|
| [coffee-check](skills/coffee-check/) | Hourly check of GitHub PR activity and sent email against your average. Asks if you need coffee when you're lagging. |

## Using a skill

Each skill lives in `skills/<name>/` and has its own README listing what it needs.
Install one by linking it into your Claude Code skills folder:

```bash
git clone https://github.com/brentoncltc/claude-skills.git ~/repos/claude-skills
mkdir -p ~/.claude/skills
ln -s ~/repos/claude-skills/skills/<name> ~/.claude/skills/<name>
```

`git pull` in the clone updates every linked skill.

## Adding a skill

1. Create `skills/<name>/` with a `SKILL.md` (`name` and `description` frontmatter) and a `README.md`
   covering requirements, install, and what data it touches.
2. Add a row to the table above.
3. No secrets, tokens, personal paths or account names in the files. Read them from the
   environment or look them up at runtime.

## License

[MIT](LICENSE)
