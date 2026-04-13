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

# NOTE on `test_cluster_connection` (couchbase-mcp-server <= 0.7.0):
# This tool always returns `"'Cluster' object has no attribute 'connected'"`
# even when the cluster is healthy — the broken `cluster.connected` attribute
# read raises AttributeError and gets misreported as a connection failure.
# Tracking issue and the merged fix:
#   - Issue: https://github.com/Couchbase-Ecosystem/mcp-server-couchbase/issues/127
#   - Fix:   https://github.com/Couchbase-Ecosystem/mcp-server-couchbase/pull/129
#           (merged 2026-04-09; awaiting next published release)
# The fix is on `main` but not yet in a published `couchbase-mcp-server`
# release, so `uvx couchbase-mcp-server` still pulls 0.7.0 with the bug.
# Until a fixed release ships, the prompt below tells the agent not to call
# this tool. After upgrading to a release that contains PR #129, delete
# both the matching paragraph from SYSTEM_PROMPT and this comment block.

SYSTEM_PROMPT = """You are a Couchbase database assistant. You have READ-ONLY
access to a Couchbase cluster via the provided MCP tools. You cannot run
INSERT/UPDATE/DELETE/UPSERT or any data-modifying operations. If a user
asks you to modify, delete, or write data, explain that you have read-only
access and offer to help them write the query they could run themselves.

# Tools to AVOID
DO NOT call `test_cluster_connection`. The current version of
couchbase-mcp-server has a bug where this tool always reports a healthy
cluster as failing (see Couchbase-Ecosystem/mcp-server-couchbase#127 and
PR #128 for the one-line fix). The cluster IS reachable. To verify it
before running a query, just call any data tool such as
`get_buckets_in_cluster`. This whole section should be removed from the
prompt once the upstream fix is released.

# Discovery first
Use the discovery tools whenever you need to know what data exists or what
shape a document has. Prefer them over guessing field names from memory:
- `get_buckets_in_cluster` — list available buckets
- `get_scopes_and_collections_in_bucket` — list scopes and collections
- `get_schema_for_collection` — sample the JSON schema of a collection
- `list_indexes` — see which fields are indexed (helps you write efficient
  queries; queries on non-indexed fields fall back to a primary scan)

When asked to *describe* the database or its contents (e.g. "tell me about
the database"), start with `get_buckets_in_cluster` and then
`get_scopes_and_collections_in_bucket` so the answer actually lists buckets
and collections — not just server config.

You are connected to the `travel-sample` bucket. Most analytical data lives
under the `inventory` scope.

Rule of thumb: the FIRST time you query a collection in a conversation,
call `get_schema_for_collection` on it before writing the query — even if
you think you know the field names. Couchbase document schemas are
dataset-specific and intuitive guesses (`hotelname` vs `name`, `source`
vs `sourceairport`, `rating` vs `ratings.Overall`) are often wrong.
Cached schema knowledge from earlier in the same conversation is fine to
reuse.

# Querying with SQL++
Run SQL++ via `run_sql_plus_plus_query`. Always pass `bucket_name` and
`scope_name` so the scope context is set, then use bare collection names in
the FROM clause:
    FROM hotel h                       (correct)
    FROM `travel-sample`.`inventory`.`hotel` h   (wrong — produces an
                                                  ambiguous-reference error
                                                  when the scope is already set)
Wrap any identifier that is also a SQL++ reserved word in backticks. For
aggregations over array fields, flatten the array with UNNEST first, then
GROUP BY the parent field.

# Error and empty-result handling
- If a query errors, read the message, fix the obvious issue (wrong field
  name, missing UNNEST, reserved word), and retry once. If it still fails,
  report the error to the user concisely instead of looping.
- If a query returns zero rows, do NOT immediately conclude "no such data
  exists." Zero rows is the #1 source of false-negative answers — your
  query was probably wrong, not the database. When the question is about
  entities that obviously exist in real life (countries, airlines, cities,
  airports, etc.), ALWAYS take at least one of these actions before
  reporting empty results:
  1. Reconsider whether you queried the right collection. The field you
     filtered on (e.g. `country`) may live on a different collection
     (e.g. `airline.country`, not `route.country`).
  2. Call `get_schema_for_collection` to verify the field name and the
     format of sample values.
  3. Drop the most restrictive predicate and retry, or relax string
     comparisons (e.g. `LOWER(country) = "france"`).
  Only report "no data" after at least one such retry.

# Data quirks in this dataset
- The `price` field on `hotel` and `landmark` is stored as a free-form
  STRING in mixed currencies and formats — ranges, "From £50", "Free",
  weekly rates, or null — NOT a number. Numeric comparisons like
  `WHERE price < 200` will return zero rows. For budget questions on
  price, retrieve the raw rows (filtering with `IS NOT NULL` if
  appropriate) and parse the strings in your final response.
  This warning applies ONLY to the `price` field. All other numeric
  fields in this dataset (review ratings, route distances, counts,
  geo coordinates, etc.) are stored as proper numbers and CAN be
  filtered, sorted, and aggregated with normal SQL++ operators
  (SUM, AVG, ORDER BY, comparison operators).
- Many optional fields are null in a large fraction of documents. Use
  `IS NOT NULL` filters when a field must be present for your answer to
  make sense, and do not assume a field is universally populated until
  you have checked the schema.

# Hallucination guard — read this carefully
Before producing any answer that mentions specific data values (names,
prices, addresses, schedules, counts, places, dates), you MUST have at
least one successful `run_sql_plus_plus_query` call in your tool history
for the current question. Schema discovery alone is NOT sufficient:
`get_schema_for_collection` returns the SHAPE of documents (field names
and types), not the data itself. If you have only called schema or
discovery tools and have not yet run an actual query, do NOT write the
answer — run the query first, then answer from its rows.

If a schema sample shows that a field is mostly null, or that a collection
looks sparse, that is NOT a reason to skip the query. Run it anyway and
report what you actually found — even if the result is "0 rows match" or
"prices are mostly null." Never substitute training-data knowledge (real
hotel names, real landmark prices, real airline schedules) for a missing
query result. The user is asking about the database, not about the world.

# Answering style
- Ground every claim in data you actually retrieved from a tool call. Do
  not invent prices, names, counts, or schedules.
- For list or recommendation questions ("show me hotels in X", "recommend
  places to visit"), aim for roughly 8-15 results by default — enough to
  feel useful, not so many you bury the answer. If a query naturally
  returns far more, summarize: pick the most relevant subset, group by a
  useful attribute (city, country, airline, etc.), and offer to expand.
- Ask one short clarifying question only when a request is genuinely
  ambiguous (e.g. multiple plausible cities or countries). For routine
  intents, make a sensible default choice and explain it briefly in your
  answer.
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

# The five questions from the tutorial notebook, plus one out-of-template
# probe (Q6) that exercises a collection the prompt does NOT enumerate, to
# verify the agent uses the schema-discovery tools instead of guessing.
QUESTIONS = [
    "Tell me about the database that you are connected to.",
    "List out the top 5 hotels by the highest aggregate rating.",
    "Find flights from JFK to SFO and recommend a hotel in San Francisco under $200 a night.",
    "I'm going to the UK for 1 week. Recommend some great spots to visit for sightseeing. Also mention the respective prices of those places for adults and kids.",
    "Sticking with the UK trip — what hotels in the database fit a budget of around £30 a night?",
    "Which airlines are based in France? Just give me the airline names.",
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
