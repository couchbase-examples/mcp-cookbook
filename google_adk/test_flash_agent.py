"""
Test script for Google ADK + Couchbase MCP Server agent on `gemini-2.5-flash`.
Mirrors the 5 questions from the tutorial notebook so we can A/B compare against
test_flash_lite_agent.py.

Usage:
    pip install google-adk python-dotenv
    python test_flash_agent.py
"""

import asyncio
import logging
import os
import warnings

from dotenv import load_dotenv
from google.adk.agents.llm_agent import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools.mcp_tool import McpToolset, StdioConnectionParams
from google.genai import types
from mcp import StdioServerParameters

# Suppress noisy logs — keep only errors
logging.getLogger("couchbase").setLevel(logging.ERROR)
logging.getLogger("mcp").setLevel(logging.ERROR)
warnings.filterwarnings("ignore")

load_dotenv()

CB_CONNECTION_STRING = os.getenv("CB_CONNECTION_STRING")
CB_USERNAME = os.getenv("CB_USERNAME")
CB_PASSWORD = os.getenv("CB_PASSWORD")

if not CB_CONNECTION_STRING or not CB_USERNAME or not CB_PASSWORD:
    raise ValueError(
        "Missing environment variables. Please create a .env file with "
        "GOOGLE_GENAI_API_KEY, CB_CONNECTION_STRING, CB_USERNAME, CB_PASSWORD"
    )

MODEL = "gemini-2.5-flash"

SYSTEM_PROMPT = """You are a Couchbase database assistant connected to
the `travel-sample` bucket (scope: `inventory`). The connection is already
established — do NOT call `test_cluster_connection` (it has known issues);
just answer using the schema and query tools.

Always use the MCP tools to query the database — never answer from memory.
Do not ask the user clarifying questions about the schema; the cheatsheet
below tells you everything you need.

Available collections in `inventory`: airline, airport, hotel, landmark, route.

Schema cheatsheet:
- `hotel`: name, city, country, address, price, reviews[*].ratings.{Overall, Cleanliness, Service}
- `route`: airline, sourceairport, destinationairport, distance, schedule[*].flight
- `landmark`: name, city, country, activity, content, price

SQL++ rules:
- Use only the collection name in the FROM clause (e.g. `FROM hotel h`).
  Do NOT prefix with the bucket or scope.
- For aggregations over array fields, flatten with UNNEST first.

Common query patterns to use directly:

"Top hotels by rating" — sum the Overall review rating per hotel:
    SELECT h.name, SUM(r.ratings.Overall) AS total
    FROM hotel h UNNEST h.reviews r
    GROUP BY h.name
    ORDER BY total DESC
    LIMIT 5

"Flights from X to Y":
    SELECT r.airline, r.sourceairport, r.destinationairport, r.distance
    FROM route r
    WHERE r.sourceairport = "X" AND r.destinationairport = "Y"

`hotel.price` and `landmark.price` are free-form strings (e.g. "$54-$104",
"From £50") or null — never filter them numerically. For budget questions:
    SELECT h.name, h.city, h.price
    FROM hotel h
    WHERE h.city = "X" AND h.price IS NOT NULL
Then read each price string yourself and pick the ones that fit.
"""

root_agent = LlmAgent(
    model=MODEL,
    name="couchbase_agent",
    description=(
        "An agent that interacts with Couchbase databases using the "
        "Couchbase MCP server."
    ),
    instruction=SYSTEM_PROMPT,
    tools=[
        McpToolset(
            connection_params=StdioConnectionParams(
                server_params=StdioServerParameters(
                    command="uvx",
                    args=["couchbase-mcp-server"],
                    env={
                        "CB_CONNECTION_STRING": CB_CONNECTION_STRING,
                        "CB_USERNAME": CB_USERNAME,
                        "CB_PASSWORD": CB_PASSWORD,
                        "CB_MCP_READ_ONLY_MODE": "true",
                    },
                ),
                timeout=60,
            ),
        )
    ],
)

# The five questions from the tutorial notebook, in order.
QUESTIONS = [
    "Tell me about the database that you are connected to.",
    "List out the top 5 hotels by the highest aggregate rating.",
    "Find flights from JFK to SFO and recommend a hotel in San Francisco under $200 a night.",
    "I'm going to the UK for 1 week. Recommend some great spots to visit for sightseeing. Also mention the respective prices of those places for adults and kids.",
    "My budget is around 30 pounds a night. What will be the best hotel to stay in?",
]


async def main():
    print(f"\n>>> Running tests against model: {MODEL}\n")

    session_service = InMemorySessionService()
    session = await session_service.create_session(
        app_name="couchbase_agent", user_id="test_flash_user"
    )
    runner = Runner(
        agent=root_agent,
        app_name="couchbase_agent",
        session_service=session_service,
    )

    for question in QUESTIONS:
        print(f"\n\n{'='*60}")
        print(f"QUESTION: {question}")
        print(f"{'='*60}\n")

        tool_calls = []
        final_response = ""

        async for event in runner.run_async(
            session_id=session.id,
            user_id="test_flash_user",
            new_message=types.Content(
                role="user",
                parts=[types.Part(text=question)],
            ),
        ):
            # Log tool calls (function calls and responses)
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.function_call:
                        tool_calls.append({
                            "tool": part.function_call.name,
                            "args": dict(part.function_call.args) if part.function_call.args else {},
                        })
                        print(f"  [TOOL CALL] {part.function_call.name}({dict(part.function_call.args) if part.function_call.args else {}})")
                    if part.function_response:
                        response_text = str(part.function_response.response)
                        # Truncate long responses for readability
                        if len(response_text) > 500:
                            response_text = response_text[:500] + "... [truncated]"
                        print(f"  [TOOL RESPONSE] {part.function_response.name} -> {response_text}")

            # Collect the final agent response
            if event.is_final_response() and event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        final_response += part.text

        print(f"\n  [TOOLS USED: {len(tool_calls)}]")
        print(f"\nANSWER:\n{final_response}")
        print("-" * 50)


if __name__ == "__main__":
    asyncio.run(main())
