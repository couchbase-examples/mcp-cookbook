"""
Test script for Google ADK + Couchbase MCP Server agent.
Run this first to verify everything works before creating the Jupyter notebook.

Usage:
    pip install google-adk python-dotenv
    python test_agent.py
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

SYSTEM_PROMPT = """You are a Couchbase database assistant connected to a Couchbase cluster
with the `travel-sample` bucket. This bucket contains travel-related data organized
under the `inventory` scope.

Use the provided tools to check cluster health, explore the data model
(buckets, scopes, collections, and document schemas), run SQL++ queries,
and perform key-value document operations.

IMPORTANT: ALWAYS use the tools to query the database to answer questions.
NEVER answer from your own knowledge. If the database does not contain
relevant data, say so explicitly rather than making up an answer.

The data is inside the `inventory` scope. Available collections:
- `airline`: Airline information (name, callsign, iata, icao, country)
- `airport`: Airport data (airportname, faa, city, country, geo, tz)
- `hotel`: Hotel/accommodation data (name, city, country, address, price, reviews)
- `landmark`: Sightseeing spots, tourist attractions, restaurants
- `route`: Flight route information (airline, sourceairport, destinationairport, distance, schedule)

IMPORTANT SQL++ Query Rules:
- Use only the collection name in the FROM clause (e.g., FROM `hotel`)
- Collection names and top-level field names should be in backticks
- For nested fields, use dot notation WITHOUT backticks around each part
  CORRECT: `hotel`.reviews[0].ratings.Overall
  WRONG: `hotel`.`reviews`.`ratings`.`Overall`
- To aggregate data from arrays, use UNNEST to flatten the array first

  Example - top hotels by aggregate rating:
  SELECT h.`name`, SUM(r.ratings.Overall) as total_rating
  FROM `hotel` h UNNEST h.`reviews` r
  GROUP BY h.`name`
  ORDER BY total_rating DESC
  LIMIT 5

- For flight routes, query the `route` collection and join with `airline`:
  SELECT r.`airline`, r.`sourceairport`, r.`destinationairport`, r.`distance`
  FROM `route` r
  WHERE r.`sourceairport` = "JFK" AND r.`destinationairport` = "SFO"
"""

root_agent = LlmAgent(
    model="gemini-2.5-flash",
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

# Questions to test the agent with
QUESTIONS = [
    "Tell me about the database that you are connected to.",
    "List out the top 5 hotels by the highest aggregate rating.",
    "Find flights from JFK to SFO and recommend a hotel in San Francisco under $200 a night.",
]


async def main():
    session_service = InMemorySessionService()
    session = await session_service.create_session(
        app_name="couchbase_agent", user_id="test_user"
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
            user_id="test_user",
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
