#!/usr/bin/env python3
"""
Streamlit UI for the Claude vs Codex Debate System
"""

import streamlit as st
import subprocess
import time
import os
import signal
import shutil
from pathlib import Path
import re

# Configuration
DEBATE_DIR = Path("./debate")

# Page config
st.set_page_config(
    page_title="AI Debate Arena",
    page_icon="🎭",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for chat-like UI
st.markdown("""
<style>
    .block-container {
        padding-top: 2rem;
    }
    .stExpander {
        border: none;
    }
    div[data-testid="stExpander"] details {
        border: 1px solid #333;
        border-radius: 8px;
    }
    .debate-header {
        text-align: center;
        padding: 1rem;
        background: linear-gradient(90deg, #1e3a5f, #4a1a4a);
        border-radius: 10px;
        margin-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)


def read_file(name: str) -> str:
    """Read a file from the debate directory."""
    path = DEBATE_DIR / name
    if path.exists():
        return path.read_text()
    return ""


def get_state() -> str:
    """Get current debate state."""
    state = read_file("state.md").strip()
    return state if state else "NOT_STARTED"


def parse_history(history_text: str) -> list:
    """Parse debate history into structured entries."""
    entries = []
    pattern = r'## \[(PROPOSER|CRITIC)\] Round (\d+) \(([^)]+)\)\n\n(.*?)(?=\n---|\Z)'
    matches = re.findall(pattern, history_text, re.DOTALL)

    for role, round_num, timestamp, content in matches:
        entries.append({
            "role": role,
            "round": int(round_num),
            "timestamp": timestamp,
            "content": content.strip()
        })

    return entries


def render_proposer_message(entry: dict, cli_name: str):
    """Render a proposer message."""
    with st.chat_message("assistant", avatar="🔵"):
        st.caption(f"**PROPOSER** ({cli_name.upper()}) • Round {entry['round']} • {entry['timestamp']}")

        # Show summary/preview
        content = entry["content"]
        lines = content.split('\n')
        preview = '\n'.join(lines[:15])

        if len(lines) > 15:
            st.markdown(preview + "\n\n*...*")
            with st.expander("📄 View Full Proposal"):
                st.markdown(content)
        else:
            st.markdown(content)


def render_critic_message(entry: dict, cli_name: str):
    """Render a critic message."""
    content = entry["content"]
    is_consensus = "CONSENSUS REACHED" in content.upper()

    if is_consensus:
        with st.chat_message("assistant", avatar="🟢"):
            st.caption(f"**CONSENSUS REACHED** • Round {entry['round']} • {entry['timestamp']}")
            st.success("The agents have reached consensus!")

            with st.expander("🏆 View Full Consensus & Summary", expanded=True):
                st.markdown(content)
    else:
        with st.chat_message("user", avatar="🟣"):
            st.caption(f"**CRITIC** ({cli_name.upper()}) • Round {entry['round']} • {entry['timestamp']}")

            # Extract verdict
            verdict_match = re.search(r'## Verdict\s*\n+([^\n#]+)', content)
            if verdict_match:
                verdict = verdict_match.group(1).strip()
                if "NEEDS_REVISION" in verdict.upper():
                    st.warning(f"Verdict: {verdict}")
                elif "MINOR" in verdict.upper():
                    st.info(f"Verdict: {verdict}")
                else:
                    st.success(f"Verdict: {verdict}")

            lines = content.split('\n')
            preview = '\n'.join(lines[:12])

            if len(lines) > 12:
                st.markdown(preview + "\n\n*...*")
                with st.expander("📋 View Full Critique"):
                    st.markdown(content)
            else:
                st.markdown(content)


def run_debate_subprocess(goal: str, proposer: str, critic: str, max_rounds: int, resume: bool = False):
    """Run the debate in a subprocess."""
    if resume:
        cmd = [
            "python", "debate_watcher.py",
            "--resume",
            "--proposer", proposer,
            "--critic", critic,
            "--max-rounds", str(max_rounds)
        ]
    else:
        cmd = [
            "python", "debate_watcher.py",
            "--goal", goal,
            "--proposer", proposer,
            "--critic", critic,
            "--max-rounds", str(max_rounds)
        ]

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True
    )

    return process


def main():
    # Header
    st.markdown("""
    <div class="debate-header">
        <h1>🎭 AI Debate Arena</h1>
        <p>Watch AI agents debate and reach consensus</p>
    </div>
    """, unsafe_allow_html=True)

    # Initialize session state
    if "debate_process" not in st.session_state:
        st.session_state.debate_process = None
    if "is_running" not in st.session_state:
        st.session_state.is_running = False

    # Sidebar configuration
    with st.sidebar:
        st.header("⚙️ Configuration")

        # Agent selection
        st.subheader("🤖 Agent Roles")

        col1, col2 = st.columns(2)
        with col1:
            proposer_cli = st.selectbox(
                "Proposer",
                ["claude", "codex"],
                index=0
            )
        with col2:
            critic_cli = st.selectbox(
                "Critic",
                ["codex", "claude"],
                index=0 if proposer_cli == "claude" else 1
            )

        max_rounds = st.slider("Max Rounds", 3, 20, 10)

        st.divider()

        # Goal input
        st.subheader("🎯 Goal")

        goal_source = st.radio(
            "Source",
            ["File", "Text"],
            horizontal=True
        )

        if goal_source == "File":
            goal_file = st.text_input("File Path", value="prompt.md")
            if Path(goal_file).exists():
                goal_text = Path(goal_file).read_text()
                st.success(f"✓ Loaded ({len(goal_text)} chars)")
                with st.expander("Preview"):
                    st.text(goal_text[:500] + "..." if len(goal_text) > 500 else goal_text)
            else:
                goal_text = ""
                st.error(f"Not found: {goal_file}")
        else:
            goal_text = st.text_area(
                "Enter goal",
                height=150,
                placeholder="What should the agents debate?"
            )

        st.divider()

        # Control buttons
        st.subheader("🎮 Controls")

        col1, col2 = st.columns(2)

        with col1:
            start_btn = st.button(
                "▶️ Start New",
                type="primary",
                use_container_width=True,
                disabled=st.session_state.is_running or not goal_text
            )

        with col2:
            resume_btn = st.button(
                "⏯️ Resume",
                use_container_width=True,
                disabled=st.session_state.is_running or not DEBATE_DIR.exists()
            )

        stop_btn = st.button(
            "⏹️ Stop",
            use_container_width=True,
            disabled=not st.session_state.is_running
        )

        st.divider()

        # Auto-refresh
        auto_refresh = st.toggle("🔄 Auto-refresh", value=True)
        refresh_rate = st.select_slider(
            "Refresh rate",
            options=[1, 2, 3, 5, 10],
            value=2,
            format_func=lambda x: f"{x}s"
        )

    # Handle button actions
    if start_btn and goal_text:
        if DEBATE_DIR.exists():
            shutil.rmtree(DEBATE_DIR)

        st.session_state.is_running = True
        st.session_state.debate_process = run_debate_subprocess(
            goal_text, proposer_cli, critic_cli, max_rounds, resume=False
        )
        st.rerun()

    if resume_btn:
        st.session_state.is_running = True
        st.session_state.debate_process = run_debate_subprocess(
            "", proposer_cli, critic_cli, max_rounds, resume=True
        )
        st.rerun()

    if stop_btn and st.session_state.debate_process:
        try:
            os.killpg(os.getpgid(st.session_state.debate_process.pid), signal.SIGTERM)
        except (ProcessLookupError, OSError, AttributeError):
            pass
        st.session_state.is_running = False
        st.session_state.debate_process = None
        st.rerun()

    # Check if process finished
    if st.session_state.debate_process:
        poll = st.session_state.debate_process.poll()
        if poll is not None:
            st.session_state.is_running = False
            st.session_state.debate_process = None

    # Main content
    state = get_state()
    history = read_file("history.md")
    current_round = history.count("## [PROPOSER]")

    # Status bar
    status_col1, status_col2, status_col3 = st.columns([2, 1, 1])

    with status_col1:
        if state == "CONSENSUS":
            st.success("🎉 **CONSENSUS REACHED** - Debate Complete!")
        elif st.session_state.is_running:
            if state == "PROPOSER_TURN":
                st.info(f"🔵 **Proposer** ({proposer_cli.upper()}) is thinking...")
            elif state == "CRITIC_TURN":
                st.info(f"🟣 **Critic** ({critic_cli.upper()}) is evaluating...")
            else:
                st.info("🔄 **Starting debate...**")
        elif DEBATE_DIR.exists():
            st.warning("⏸️ **Paused** - Click Resume to continue")
        else:
            st.info("👈 **Configure and start** a debate from the sidebar")

    with status_col2:
        st.metric("Round", current_round if current_round > 0 else "-")

    with status_col3:
        st.metric("Max", max_rounds)

    st.divider()

    # Goal display
    goal_content = read_file("goal.md")
    if goal_content:
        with st.expander("🎯 **Debate Goal**", expanded=False):
            st.markdown(goal_content)

    # Debate conversation
    if history and "## [" in history:
        entries = parse_history(history)

        if entries:
            st.subheader(f"💬 Conversation ({len(entries)} messages)")

            for entry in entries:
                if entry["role"] == "PROPOSER":
                    render_proposer_message(entry, proposer_cli)
                else:
                    render_critic_message(entry, critic_cli)

            # Show typing indicator if running
            if st.session_state.is_running:
                if state == "PROPOSER_TURN":
                    with st.chat_message("assistant", avatar="🔵"):
                        st.caption("*Proposer is typing...*")
                        st.spinner("Thinking...")
                elif state == "CRITIC_TURN":
                    with st.chat_message("user", avatar="🟣"):
                        st.caption("*Critic is typing...*")
                        st.spinner("Evaluating...")

    elif DEBATE_DIR.exists():
        st.info("⏳ Waiting for first message...")
        if st.session_state.is_running:
            with st.spinner("Proposer is preparing the first proposal..."):
                time.sleep(1)

    # Consensus summary (prominent display)
    if state == "CONSENSUS":
        st.divider()
        consensus_content = read_file("consensus.md")
        if consensus_content:
            st.subheader("🏆 Final Consensus")
            st.markdown(consensus_content)

            # Download button
            st.download_button(
                "📥 Download Consensus",
                consensus_content,
                file_name="consensus.md",
                mime="text/markdown"
            )

        # Also offer full history download
        if history:
            st.download_button(
                "📥 Download Full History",
                history,
                file_name="debate_history.md",
                mime="text/markdown"
            )

    # Auto-refresh logic
    if auto_refresh and st.session_state.is_running:
        time.sleep(refresh_rate)
        st.rerun()
    elif auto_refresh and state not in ["CONSENSUS", "NOT_STARTED"] and DEBATE_DIR.exists():
        # Keep refreshing to catch updates even when not "running" (process might have restarted)
        time.sleep(refresh_rate)
        st.rerun()


if __name__ == "__main__":
    main()
