#!/usr/bin/env python3
"""
debate_watcher.py - Automated debate between Claude Code and Codex CLIs

Usage:
    python debate_watcher.py --goal "Design a rate limiting system"
    python debate_watcher.py --resume
"""

import subprocess
import time
import argparse
import shutil
import os
import re
import signal
import tempfile
from pathlib import Path
from datetime import datetime
from enum import Enum

# Track current subprocess for cleanup on Ctrl+C
_current_process = None

# ============================================================================
# CONFIGURATION
# ============================================================================

DEBATE_DIR = Path("./debate")
MAX_ROUNDS = 10
POLL_INTERVAL = 2

# Which CLI plays which role
PROPOSER = "claude"  # "claude" | "codex"
CRITIC = "codex"     # "claude" | "codex"

# ============================================================================
# PROMPTS
# ============================================================================

PROPOSER_SYSTEM = """You are the PROPOSER in a structured debate. Your job is to propose solutions and refine them based on critique.

## Proposal Format

# Proposal (Round {round})

## Summary
[One paragraph overview]

## Detailed Approach
[Specific steps, architecture, implementation details]

## Addressing Previous Critique
[How you addressed each point raised - skip if Round 1]

## Trade-offs Acknowledged
[Known limitations and why they're acceptable]

## Guidelines

- Be specific and actionable
- Address ALL previous critiques explicitly
- Justify trade-offs
- Keep it focused - solve the goal, don't over-engineer
- Output ONLY the proposal, no preamble

## IMPORTANT: Follow Workflow Instructions

If the GOAL contains specific workflow instructions (e.g., "list 10 ideas first", "brainstorm before narrowing"), you MUST follow them. Read the goal carefully for any process requirements."""

CRITIC_SYSTEM = """You are the CRITIC in a structured debate. Your job is to rigorously evaluate proposals and push for better solutions — but also recognize when a proposal is good enough.

## Critique Format

# Critique (Round {round})

## Verdict
[NEEDS_REVISION | MINOR_ISSUES | CONSENSUS REACHED]

## What Works Well
[Genuine positives]

## Blocking Issues
[Problems that MUST be fixed - empty if none]

## Suggestions
[Improvements, prioritized]

## Consensus Criteria

Declare "CONSENSUS REACHED" as your verdict when:
- The proposal achieves the stated goal
- No blocking issues remain
- Trade-offs are reasonable
- Further iteration has diminishing returns

## IMPORTANT: When Declaring CONSENSUS REACHED

When you declare "CONSENSUS REACHED", you MUST include a comprehensive summary section at the end:

### Debate Summary

#### Ideas Considered
[List ALL ideas that were proposed and debated, with one-line descriptions]

#### Debate Progression
[Brief timeline: what was proposed, what was critiqued, how ideas were narrowed down, key turning points]

#### Final Selected Idea
[Name of the selected idea]

#### Key Agreements Made
[Bullet list of all major agreements reached during the debate, including: scope, timeline, pricing, GTM strategy, validation criteria, trade-offs accepted, etc.]

#### Final Idea Details
[Comprehensive description of the final agreed idea with all specifications consolidated in one place]

## Guidelines

- Be constructive, not obstructive
- Be specific with critiques
- Suggest alternatives, don't just criticize
- Don't demand perfection when good enough suffices
- Output ONLY the critique, no preamble

## IMPORTANT: Follow Workflow Instructions

If the GOAL contains specific workflow instructions (e.g., "pick a few ideas to focus on", "debate each idea"), you MUST follow them. Read the goal carefully for any process requirements."""


class State(Enum):
    PROPOSER_TURN = "PROPOSER_TURN"
    CRITIC_TURN = "CRITIC_TURN"
    CONSENSUS = "CONSENSUS"


def read_file(name: str) -> str:
    return (DEBATE_DIR / name).read_text()


def write_file(name: str, content: str):
    (DEBATE_DIR / name).write_text(content)


def append_file(name: str, content: str):
    with open(DEBATE_DIR / name, "a") as f:
        f.write(content)


def get_state() -> State:
    return State(read_file("state.md").strip())


def set_state(state: State):
    write_file("state.md", state.value)


def get_round() -> int:
    history = read_file("history.md")
    return history.count("## [PROPOSER]") + 1


def call_claude(prompt: str) -> str:
    """Call Claude Code CLI."""
    global _current_process
    print("    Running: claude -p '...' --dangerously-skip-permissions")
    proc = subprocess.Popen(
        ["claude", "-p", prompt, "--dangerously-skip-permissions"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    _current_process = proc
    try:
        stdout, stderr = proc.communicate(timeout=600)
    except subprocess.TimeoutExpired:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        raise
    finally:
        _current_process = None

    if proc.returncode != 0:
        raise RuntimeError(f"Claude CLI failed: {stderr}")
    return stdout.strip()


def call_codex(prompt: str) -> str:
    """Call Codex CLI in non-interactive exec mode."""
    global _current_process
    print("    Running: codex exec --dangerously-bypass-approvals-and-sandbox '...'")

    # Use temp file for output (codex exec -o option)
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        output_file = f.name

    try:
        proc = subprocess.Popen(
            [
                "codex", "exec",
                "--dangerously-bypass-approvals-and-sandbox",
                "-o", output_file,
                prompt,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        _current_process = proc

        try:
            stdout, stderr = proc.communicate(timeout=600)
        except subprocess.TimeoutExpired:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            raise
        finally:
            _current_process = None

        # Read output from file
        if Path(output_file).exists():
            output = Path(output_file).read_text()
        else:
            # Fallback to stdout if -o didn't work
            output = stdout

    finally:
        Path(output_file).unlink(missing_ok=True)

    return output.strip()


def call_agent(agent: str, prompt: str) -> str:
    """Call the specified agent CLI."""
    if agent == "claude":
        return call_claude(prompt)
    elif agent == "codex":
        return call_codex(prompt)
    else:
        raise ValueError(f"Unknown agent: {agent}")


def build_proposer_prompt(round_num: int) -> str:
    """Build the full prompt for the proposer."""
    goal = read_file("goal.md")
    history = read_file("history.md")
    critique = read_file("critic.md")
    system = PROPOSER_SYSTEM.format(round=round_num)

    return f"""{system}

---

## GOAL

{goal}

## DEBATE HISTORY

{history}

## LATEST CRITIQUE

{critique}

---

Write your proposal for Round {round_num}."""


def build_critic_prompt(round_num: int) -> str:
    """Build the full prompt for the critic."""
    goal = read_file("goal.md")
    history = read_file("history.md")
    proposal = read_file("proposer.md")
    system = CRITIC_SYSTEM.format(round=round_num)

    return f"""{system}

---

## GOAL

{goal}

## DEBATE HISTORY

{history}

## LATEST PROPOSAL

{proposal}

---

Evaluate this proposal for Round {round_num}."""


def setup_debate_dir(goal: str | None = None):
    """Initialize debate directory."""
    DEBATE_DIR.mkdir(exist_ok=True)

    files = {
        "goal.md": goal or "# Goal\n\n[Define your goal here]",
        "state.md": State.PROPOSER_TURN.value,
        "proposer.md": "# Proposal\n\n(Awaiting first proposal)",
        "critic.md": "# Critique\n\n(No critique yet - this is Round 1)",
        "history.md": "# Debate History\n\n---\n",
    }

    for filename, content in files.items():
        (DEBATE_DIR / filename).write_text(content)
        print(f"  Created {DEBATE_DIR / filename}")


def run_proposer_turn():
    """Execute the proposer's turn."""
    round_num = get_round()
    print(f"\n{'='*60}")
    print(f"  PROPOSER ({PROPOSER.upper()}) - Round {round_num}")
    print(f"{'='*60}")

    prompt = build_proposer_prompt(round_num)
    response = call_agent(PROPOSER, prompt)

    write_file("proposer.md", response)

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    append_file("history.md", f"\n## [PROPOSER] Round {round_num} ({timestamp})\n\n{response}\n\n---\n")

    # Show truncated response
    print(f"\n{response[:800]}{'...' if len(response) > 800 else ''}")

    set_state(State.CRITIC_TURN)
    print(f"\n  → Next: CRITIC")


def run_critic_turn():
    """Execute the critic's turn."""
    round_num = get_round() - 1
    print(f"\n{'='*60}")
    print(f"  CRITIC ({CRITIC.upper()}) - Round {round_num}")
    print(f"{'='*60}")

    prompt = build_critic_prompt(round_num)
    response = call_agent(CRITIC, prompt)

    write_file("critic.md", response)

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    append_file("history.md", f"\n## [CRITIC] Round {round_num} ({timestamp})\n\n{response}\n\n---\n")

    print(f"\n{response[:800]}{'...' if len(response) > 800 else ''}")

    if "CONSENSUS REACHED" in response.upper():
        set_state(State.CONSENSUS)
        write_file("consensus.md", f"# Consensus Reached - Round {round_num}\n\n{response}")
        print(f"\n  → CONSENSUS REACHED!")
    else:
        set_state(State.PROPOSER_TURN)
        print(f"\n  → Next: PROPOSER")


def run_debate_loop():
    """Main debate loop."""
    print("\n" + "="*60)
    print("  DEBATE WATCHER STARTED")
    print("="*60)
    print(f"  Proposer: {PROPOSER}")
    print(f"  Critic:   {CRITIC}")
    print(f"  Max rounds: {MAX_ROUNDS}")
    print("="*60)

    rounds = 0

    while rounds < MAX_ROUNDS:
        state = get_state()

        if state == State.CONSENSUS:
            print("\n" + "="*60)
            print("  DEBATE COMPLETE - CONSENSUS REACHED")
            print("="*60)
            print(f"  Result: {DEBATE_DIR}/consensus.md")
            print(f"  History: {DEBATE_DIR}/history.md")
            return

        elif state == State.PROPOSER_TURN:
            run_proposer_turn()
            rounds += 1

        elif state == State.CRITIC_TURN:
            run_critic_turn()

        time.sleep(POLL_INTERVAL)

    print("\n" + "="*60)
    print(f"  MAX ROUNDS ({MAX_ROUNDS}) REACHED")
    print("="*60)
    print("  Resume with: python debate_watcher.py --resume --max-rounds 20")


def main():
    global PROPOSER, CRITIC, MAX_ROUNDS

    parser = argparse.ArgumentParser(description="Claude vs Codex debate orchestrator")
    parser.add_argument("--goal", "-g", type=str, help="Goal for the debate")
    parser.add_argument("--goal-file", "-f", type=str, help="File containing the goal")
    parser.add_argument("--resume", "-r", action="store_true", help="Resume existing debate")
    parser.add_argument("--proposer", "-p", choices=["claude", "codex"], default=PROPOSER)
    parser.add_argument("--critic", "-c", choices=["claude", "codex"], default=CRITIC)
    parser.add_argument("--max-rounds", "-m", type=int, default=MAX_ROUNDS)
    parser.add_argument("--swap", "-s", action="store_true", help="Swap roles (codex proposes, claude critiques)")

    args = parser.parse_args()
    MAX_ROUNDS = args.max_rounds

    if args.swap:
        PROPOSER, CRITIC = "codex", "claude"
    else:
        PROPOSER = args.proposer
        CRITIC = args.critic

    # Get goal
    goal = None
    if args.goal:
        goal = f"# Goal\n\n{args.goal}"
    elif args.goal_file:
        goal = Path(args.goal_file).read_text()

    # Setup
    if args.resume:
        if not DEBATE_DIR.exists():
            print("Error: No debate to resume. Start with --goal")
            return 1
        print(f"Resuming from {DEBATE_DIR}")
    else:
        if DEBATE_DIR.exists():
            shutil.rmtree(DEBATE_DIR)
        if not goal:
            print("Error: Provide --goal or --goal-file")
            return 1
        setup_debate_dir(goal)

    def handle_interrupt(signum, frame):
        """Handle Ctrl+C by killing any running subprocess."""
        global _current_process
        if _current_process:
            try:
                os.killpg(os.getpgid(_current_process.pid), signal.SIGTERM)
            except (ProcessLookupError, OSError):
                pass
        raise KeyboardInterrupt

    signal.signal(signal.SIGINT, handle_interrupt)

    try:
        run_debate_loop()
    except KeyboardInterrupt:
        print("\n\n  Paused. Resume with: python debate_watcher.py --resume")

    return 0


if __name__ == "__main__":
    exit(main())
