# AI Debate Orchestrator

Automated debate system where Claude Code and Codex CLI take turns as proposer and critic to reach consensus on a goal.

## Usage

```bash
# Start a debate
python debate_watcher.py --goal "Your goal here"

# Swap roles (Codex proposes, Claude critiques)
python debate_watcher.py --goal "..." --swap

# Resume after pause
python debate_watcher.py --resume

# Set max rounds
python debate_watcher.py --goal "..." --max-rounds 15
```

## Options

| Flag | Description |
|------|-------------|
| `-g, --goal` | Goal text for the debate |
| `-f, --goal-file` | Read goal from file |
| `-p, --proposer` | Agent for proposer (`claude` or `codex`) |
| `-c, --critic` | Agent for critic (`claude` or `codex`) |
| `-s, --swap` | Swap default roles |
| `-m, --max-rounds` | Max rounds before stopping (default: 10) |
| `-r, --resume` | Resume existing debate |

## Output Files

```
debate/
├── goal.md        # The objective
├── state.md       # Current turn
├── proposer.md    # Latest proposal
├── critic.md      # Latest critique
├── history.md     # Full debate log
└── consensus.md   # Final agreement (when reached)
```

## Requirements

- `claude` CLI installed and authenticated
- `codex` CLI installed and authenticated
