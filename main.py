"""Interactive CLI for the AutoStream / Inflx agent.

Usage:
    python main.py
"""
from __future__ import annotations

import uuid

from agent import chat


BANNER = r"""
 _____         __  _
|_   _|       / _|| |     Inflx x AutoStream
  | |  _ __  | |_ | |__    Social-to-Lead Agent
  | | | '_ \ |  _|| / /    (LangGraph + OpenRouter)
 _| |_| | | || |  | |\ \
 \___/|_| |_||_|  |_| \_\  Type 'exit' to quit.
"""


def main() -> None:
    print(BANNER)
    thread_id = str(uuid.uuid4())
    print(f"[session: {thread_id[:8]}]\n")

    while True:
        try:
            user = input("you > ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not user:
            continue
        if user.lower() in {"exit", "quit", ":q"}:
            break
        try:
            reply = chat(user, thread_id=thread_id)
        except Exception as exc:
            print(f"[error] {exc}\n")
            continue
        print(f"inflx > {reply}\n")


if __name__ == "__main__":
    main()
