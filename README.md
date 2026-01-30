# AI Debate Arena

Automated debate system where Claude Code and Codex CLI take turns as proposer and critic to reach consensus on a goal. Features both CLI and web UI interfaces.

## Quick Start

### Web UI (Recommended)

```bash
pip install -r requirements.txt
streamlit run app.py
```

Open `http://localhost:8501` in your browser.

### Command Line

```bash
# Start a debate
python debate_watcher.py --goal "Your goal here"

# Or use a goal file
python debate_watcher.py --goal-file prompt.md
```

## Features

- **Dual Agent Debate**: Claude and Codex take turns proposing and critiquing
- **Structured Format**: Proposals and critiques follow consistent templates
- **Consensus Detection**: Automatically detects when agents reach agreement
- **Web UI**: Real-time visualization with chat-like interface
- **Pause/Resume**: Stop anytime and continue later
- **Workflow Instructions**: Embed custom debate rules in your goal (e.g., "list 10 ideas first")

## Web UI

The Streamlit app provides:

- Chat-like conversation view with proposer (🔵) and critic (🟣) messages
- Real-time status updates while agents are thinking
- Verdict highlighting (NEEDS_REVISION, MINOR_ISSUES, CONSENSUS)
- Expandable full content for long messages
- Auto-refresh with configurable rate
- Download buttons for consensus and full history
- Goal file loading or direct text input

## CLI Options

| Flag | Description |
|------|-------------|
| `-g, --goal` | Goal text for the debate |
| `-f, --goal-file` | Read goal from file |
| `-p, --proposer` | Agent for proposer (`claude` or `codex`) |
| `-c, --critic` | Agent for critic (`claude` or `codex`) |
| `-s, --swap` | Swap default roles (codex proposes, claude critiques) |
| `-m, --max-rounds` | Max rounds before stopping (default: 10) |
| `-r, --resume` | Resume existing debate |

## Output Files

```
debate/
├── goal.md        # The objective
├── state.md       # Current turn (PROPOSER_TURN, CRITIC_TURN, CONSENSUS)
├── proposer.md    # Latest proposal
├── critic.md      # Latest critique
├── history.md     # Full debate log
└── consensus.md   # Final agreement (when reached)
```

## Writing Effective Goals

You can include workflow instructions in your goal file:

```markdown
Design a microservices architecture for an e-commerce platform.

Requirements:
- Must handle 10K concurrent users
- Include authentication and payment services

A proposer MUST list at least 5 architecture options first.
Then the critic picks 2-3 to debate in detail.

When consensus is reached, summarize all options considered
and the final architecture with justifications.
```

The agents will follow these embedded instructions.

## Requirements

- Python 3.8+
- `claude` CLI installed and authenticated
- `codex` CLI installed and authenticated
- `streamlit` (for web UI)

## Installation

```bash
# Clone the repo
git clone <repo-url>
cd claude-codex-debator

# Install dependencies
pip install -r requirements.txt

# Verify CLIs are available
claude --version
codex --version
```

## Examples

```bash
# Debate with goal file
python debate_watcher.py -f prompt.md

# Claude as critic instead of proposer
python debate_watcher.py --goal "Design a caching system" --swap

# Longer debate with more rounds
python debate_watcher.py -f prompt.md --max-rounds 15

# Resume a paused debate
python debate_watcher.py --resume
```
