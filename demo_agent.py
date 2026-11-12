import asyncio
import json
from pathlib import Path
from typing import Annotated

from agent_framework import Agent,tool
from agent_framework.foundry import FoundryLocalClient
from dotenv import load_dotenv
from pydantic import Field

load_dotenv()

DATA_FILE = Path(__file__).parent/"hire_types.json"


@tool(approval_mode="never_require")
def lookup_hire_type(
    name: Annotated[
        str,
        Field(description="Hire type name, ex:- 'Intern'. Pass 'all' to list every hire type."),
    ],
) -> str:
    """Look up details of a hire type (description, probation, notice period,
    benefits eligibility). Use this whenever the user asks about a hire type."""
    print(f"[tool called] lookup_hire_type(name={name!r})")

    hire_types = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    query = name.strip().lower()

    if query == "all":
        return json.dumps(hire_types)

    for item in hire_types:
        if item["name"].lower() == query:
            return json.dumps(item)

    available = ", ".join(item["name"] for item in hire_types)
    return f"HIRE_TYPE_NOT_FOUND. Available hire types: {available}"


async def main() -> None:
    client = FoundryLocalClient()

    agent = Agent(
        client = client,
        name = "HireTypeAgent",
        instructions=(
            "You are an HR assistant that answers questions about hire types.\n"
            "STEP 1: Always call lookup_hire_type() to get the facts. "
            "Never answer from memory.\n"
            "STEP 2: If it returns HIRE_TYPE_NOT_FOUND, tell the user which "
            "hire types are available. Do not guess.\n"
            "STEP 3: Reply briefly in plain language."
        ),
        tools=[lookup_hire_type]
    )

    session = agent.create_session()

    while True:
        question = input("\nYou (type 'exit' to quit): ")
        if question.strip().lower() == "exit":
            break
        result = await agent.run(question, session=session)
        print(f"Agent: {result}")


if __name__ == "__main__":
    asyncio.run(main())