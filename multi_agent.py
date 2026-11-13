"""Intern 3/7 - multi-turn MAF demo.

Extends the 2/7 agent:
  * remembers earlier turns (one session for the whole conversation)
  * asks for missing hire-request details instead of guessing
  * ends with a structured draft returned by a tool

Run:  python multiturn_agent.py
Type  /reset  to start a fresh session, or  exit  to quit.
"""

import asyncio
import json
from datetime import date
from pathlib import Path
from typing import Annotated

from agent_framework import Agent, tool
from agent_framework.foundry import FoundryLocalClient
from dotenv import load_dotenv
from pydantic import Field

load_dotenv()  # reads FOUNDRY_LOCAL_MODEL from .env

DATA_FILE = Path(__file__).parent / "hire_types.json"
PLACEHOLDERS = {"", "unknown", "n/a", "na", "none", "tbd", "not provided", "?"}



@tool(approval_mode="never_require")
def lookup_hire_type(
    name: Annotated[
        str,
        Field(description="Hire type name, e.g. 'Full-time'. Pass 'all' to list every hire type."),
    ],
) -> str:
    """Look up details of a hire type (description, probation, notice period,
    benefits eligibility). Use this whenever the user asks about a hire type."""
    print(f"  [tool called] lookup_hire_type(name={name!r})")

    hire_types = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    query = name.strip().lower()

    if query == "all":
        return json.dumps(hire_types)

    for item in hire_types:
        if item["name"].lower() == query:
            return json.dumps(item)

    available = ", ".join(item["name"] for item in hire_types)
    return f"HIRE_TYPE_NOT_FOUND. Available hire types: {available}"



@tool(approval_mode="never_require")
def create_hire_request_draft(
    name: Annotated[
        str | None,
        Field(
            description="Full name of the person to hire, exactly as the user gave it. "
            "Omit this argument if the user has not given a name."
        ),
    ] = None,
    role: Annotated[
        str | None,
        Field(
            description="Job role or title, exactly as the user gave it. "
            "Omit this argument if the user has not given a role."
        ),
    ] = None,
    location: Annotated[
        str | None,
        Field(
            description="Work location (city), exactly as the user gave it. "
            "Omit this argument if the user has not given a location."
        ),
    ] = None,
) -> str:
    """Create a structured hire request draft from details the user has actually given.
    Pass only the values the user stated. Omit any argument the user has not given --
    never substitute a guess, a default, or an example value from another tool."""
    print(f"  [tool called] create_hire_request_draft(name={name!r}, role={role!r}, location={location!r})")

    fields = {"name": name, "role": role, "location": location}
    missing = [
        key
        for key, value in fields.items()
        if value is None or value.strip().lower() in PLACEHOLDERS
    ]
    if missing:
        # Guardrail: a value the user never gave must be absent, not invented.
        return (
            f"MISSING_FIELDS: {', '.join(missing)}. "
            "Ask the user for these, one at a time. Do not guess."
        )

    draft = {
        "status": "DRAFT",
        "name": name.strip(),
        "role": role.strip(),
        "location": location.strip(),
        "created_on": date.today().isoformat(),
    }
    return json.dumps(draft)


INSTRUCTIONS = (
    "You are an HR assistant. You help with three things: answering questions about "
    "hire types, drafting hire requests, and recalling the hire requests already "
    "drafted earlier in this conversation.\n"
    "For hire-type questions: call lookup_hire_type(). Never answer a hire-type "
    "question from memory -- the hire type list lives in the tool, not in your head. "
    "If it returns HIRE_TYPE_NOT_FOUND, tell the user which hire types exist.\n"
    "For a hire request you need exactly three details: name, role and location.\n"
    "RULE 1: Remember everything the user already told you in this conversation. "
    "Never ask again for something they already gave.\n"
    "RULE 2: If any detail is missing, ask for ONE missing detail at a time. "
    "Never guess or make up a value. When filling in the name, role or location of a "
    "NEW draft, use only what the user typed in this conversation -- do not borrow a "
    "value from a tool description or from the hire type list. 'Intern', 'Full-time' "
    "and 'Contract' are hire types, not a role the user asked for.\n"
    "RULE 3: Only when you have all three, call create_hire_request_draft(). "
    "If you do call it without all three, leave the unknown arguments out entirely "
    "rather than filling them with a guess.\n"
    "RULE 4: If a tool returns MISSING_FIELDS, ask the user for those fields. "
    "If a tool returns an error, tell the user the draft could not be created and offer to try again.\n"
    "RULE 5: After the draft tool succeeds, show the draft to the user. Then wait for "
    "the next request -- the conversation is not over.\n"
    "RULE 6: Every draft create_hire_request_draft() returned earlier in THIS "
    "conversation is part of the conversation and you can still read it. If the user "
    "asks what has been drafted so far, or to list, count, repeat or compare the hire "
    "requests, answer from the conversation itself. Do NOT look for a tool for this "
    "and do NOT say no tool is available -- there is no listing tool and none is "
    "needed. Scroll back through the conversation, collect every successful draft, and "
    "list them with their name, role, location and created_on. If no draft has been "
    "created yet in this conversation, say exactly that.\n"
    "RULE 7: Drafts belong to the current conversation only. After /reset you are a "
    "new session with no drafts -- say so rather than inventing past drafts."
)


def build_agent() -> Agent:
    client = FoundryLocalClient()  # model alias comes from FOUNDRY_LOCAL_MODEL in .env
    return Agent(
        client=client,
        name="HireRequestAgent",
        instructions=INSTRUCTIONS,
        tools=[lookup_hire_type, create_hire_request_draft],
    )


def stored_message_count(session) -> int:
    """How many messages MAF has saved in this session so far.
    The default in-memory provider keeps them in session.state['in_memory']['messages']."""
    return len(session.state.get("in_memory", {}).get("messages", []))


async def main() -> None:
    agent = build_agent()
    session = agent.create_session()  # one session = one conversation
    print(f"New session: {session.session_id}")

    turn = 0
    while True:
        user_input = input("\nYou (/reset for new session, exit to quit): ").strip()
        if user_input.lower() == "exit":
            break
        if user_input.lower() == "/reset":
            session = agent.create_session()  # new session = no memory of the old chat
            turn = 0
            print(f"New session: {session.session_id}")
            continue
        if not user_input:
            continue

        turn += 1
        result = await agent.run(user_input, session=session)
        print(f"Agent: {result}")
        print(f"  (turn {turn}, {stored_message_count(session)} messages stored in session)")


if __name__ == "__main__":
    asyncio.run(main())