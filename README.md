# Couchbase LangChain MCP Adapter Demo

## 1. Project Overview

This project demonstrates the integration of a Large Language Model (LLM) with a Couchbase database using the Model Context Protocol (MCP). It showcases how an AI agent, built using LangChain and LangGraph, can understand natural language queries, interact with a Couchbase instance to retrieve or manipulate data, and provide meaningful responses. This demo specifically focuses on querying a sample database `travel-sample` containing information about hotels, airports, airlines, routes, and landmarks, primarily within an `inventory` scope, using the `react_agent.ipynb` notebook.

Users can ask questions like:
*   "List out the top 5 hotels by the highest aggregate rating?"
*   "Recommend me a flight and hotel from New York to San Francisco."

## 2. Introduction to Model Context Protocol (MCP)

The Model Context Protocol (MCP) is an open standard designed to standardize how AI assistants and applications connect to and interact with external data sources, tools, and systems. Think of MCP as a universal adapter that allows AI models to seamlessly access the context they need to produce more relevant, accurate, and actionable responses.

**Key Goals and Features of MCP:**

*   **Standardized Communication:** MCP provides a common language and structure for AI models to communicate with diverse backend systems, replacing the need for numerous custom integrations.
*   **Enhanced Context Management:** It helps manage the limited context windows of LLMs efficiently, enabling them to maintain longer, more coherent interactions and leverage historical data.
*   **Secure Data Access:** MCP emphasizes secure connections, allowing developers to expose data through MCP servers while maintaining control over their infrastructure.
*   **Tool Use and Actionability:** It enables LLMs to not just retrieve information but also to use external tools and trigger actions in other systems.
*   **Interoperability:** Fosters an ecosystem where different AI tools, models, and data sources can work together more cohesively.
*   **Client-Server Architecture:** MCP typically involves:
    *   **MCP Hosts/Clients:** Applications (like AI assistants, IDEs, or other AI-powered tools) that want to access data or capabilities. In this demo, the `react_agent.ipynb` notebook, through LangChain, acts as an MCP client.
    *   **MCP Servers:** Lightweight programs that expose specific data sources or tools (e.g., a database, an API) through the standardized MCP. The `mcp-server-couchbase` project fulfills this role for Couchbase.

MCP aims to break down data silos, making it easier for AI to integrate with real-world applications and enterprise systems, leading to more powerful and context-aware AI solutions. It is an open-source initiative, often supported by SDKs in various programming languages to facilitate the development of MCP clients and servers.

## 3. Implementation Overview: LangChain ReAct Agent with `react_agent.ipynb`

This project leverages MCP to allow an AI agent, built with LangChain and LangGraph, to query and understand data within a Couchbase database. The primary demonstration is contained within the `react_agent.ipynb` Jupyter notebook.

This example utilizes the popular LangChain and LangGraph frameworks to build a ReAct (Reasoning and Acting) agent. This approach demonstrates how to integrate MCP-exposed tools into a LangChain ecosystem.

### 3.1. Core Components:

*   **`react_agent.ipynb`:**
    *   The Jupyter notebook demonstrating the LangChain-based ReAct agent.
    *   It handles environment setup, MCP server connection, agent definition, and interaction.
*   **LangChain (`langchain_core`, `langchain_openai`):**
    *   The core LangChain library provides the foundational components for building LLM applications, including prompt templates and LLM wrappers.
    *   `ChatOpenAI` is used to interact with OpenAI's GPT models.
*   **LangGraph (`langgraph.prebuilt`, `langgraph.checkpoint`):**
    *   An extension of LangChain for building robust and stateful multi-actor applications.
    *   `create_react_agent` is a prebuilt constructor for creating ReAct agents.
    *   `InMemorySaver` is used for checkpointing agent state.
*   **`langchain_mcp_adapters`:**
    *   A library that provides helper functions, specifically `load_mcp_tools`, to adapt tools exposed over MCP for use within the LangChain framework.
*   **`mcp` (Python library):**
    *   Used for direct client-side communication with the MCP server.
    *   Components like `ClientSession`, `StdioServerParameters`, and `stdio_client` are used to manage the connection to the `mcp-server-couchbase` process.
*   **`mcp-server-couchbase` (External MCP Server):**
    *   This is a separate Python application (located [here](https://github.com/Couchbase-Ecosystem/mcp-server-couchbase)) that implements the MCP server logic for Couchbase.
    *   It exposes Couchbase operations (like running SQL++ queries, fetching documents, listing scopes/collections) as tools that the AI agent can call via MCP.
    *   It requires its own environment configuration (e.g., via environment variables passed directly during its startup) to connect to the actual Couchbase instance. The `react_agent.ipynb` example demonstrates passing these as environment variables directly to the `StdioServerParameters`.

### 3.2. Workflow:

1.  **Environment and MCP Server Setup:**
    *   The notebook loads necessary environment variables (e.g., OpenAI API key, Couchbase credentials for the MCP server) using `python-dotenv`.
    *   `StdioServerParameters` configures the command to launch the `mcp-server-couchbase` Python script (e.g., using `uv run ...`).
    *   An MCP connection is established using `stdio_client` and `ClientSession` from the `mcp` library. The session is initialized.

2.  **System Prompt Definition:**
    *   A detailed system prompt (stored in the `system_prompt` string variable in the notebook) is defined. This prompt guides the LLM on how to behave, understand the Couchbase data hierarchy (Cluster, Bucket, Scope, Collection), specifically target the `inventory` scope, and correctly formulate SQL++ queries (e.g., using backticks for identifiers, collection name only in `FROM` clause).

3.  **MCP Tool Loading for LangChain:**
    *   The `load_mcp_tools(session)` function from `langchain_mcp_adapters` is called. This function introspects the connected MCP server, discovers the available Couchbase tools (e.g., `mcp_couchbase_run_sql_plus_plus_query`), and wraps them in a format compatible with LangChain agents.

4.  **Agent Creation:**
    *   A ReAct agent is created using `create_react_agent` from LangGraph.
    *   This function takes the LLM (e.g., `ChatOpenAI(model="gpt-4.1")`), the loaded MCP tools, the system prompt, and a checkpointer (`InMemorySaver`) as arguments.

5.  **Querying the Agent:**
    *   The `qna` asynchronous function defines a series of natural language questions.
    *   For each question, `agent.ainvoke({"messages": message}, config)` sends the message to the ReAct agent. A `thread_id` is used in the configuration for maintaining conversation state.

6.  **Agent Processing and MCP Tool Use:**
    *   The ReAct agent receives the user's question.
    *   It reasons about the task and decides which tool to use (if any) from the MCP tools it has been provided.
    *   If a Couchbase tool is selected, the agent executes it, which involves sending a request via the MCP `ClientSession` to the `mcp-server-couchbase`.
    *   The `mcp-server-couchbase` performs the database operation, and the results are returned to the agent.

7.  **Response Generation:**
    *   The agent uses the information retrieved from Couchbase and its internal reasoning loop to formulate a natural language response.
    *   The final content of the agent's response is then printed in the notebook.

### 3.3. Database Interaction Details:

*   **Target Database:** The agent is configured to primarily work with the `inventory` scope of the connected Couchbase bucket.
*   **Collections:** The demo typically interacts with collections such as `airport`, `airline`, `route`, `landmark`, and `hotel` within the `inventory` scope.
*   **Query Language:** The agent is instructed via its system prompt to generate SQL++ (N1QL) queries for Couchbase, following specific syntax rules (e.g., using backticks for identifiers).

## 4. Setting Up and Running the Demo

**Prerequisites:**

*   Python
*   Jupyter Notebook or JupyterLab.
*   Access to a running Couchbase Server instance populated with the relevant sample data (especially in the `inventory` scope with collections like `airport`, `airline`, `route`, `landmark`, `hotel`).
*   The `mcp-server-couchbase` project must be cloned and available locally. Its path is required to start it from the `react_agent.ipynb` notebook (e.g., `/Users/gautham.krithiwas/projects/mcp-server-couchbase/` as used in the example notebook). Ensure this path in `react_agent.ipynb` is updated for your environment.
*   The following Python libraries must be installed:
    *   `langchain`
    *   `langgraph`
    *   `langchain-openai`
    *   `langchain-mcp-adapters`
    *   `python-dotenv`
    *   `openai` (typically a dependency of `langchain-openai`)
    *   The `mcp` Python library (often a dependency of `langchain-mcp-adapters` or installable as `mcp-client`).
    *   `uv` (or ensure the command in `StdioServerParameters` is adapted if `uv` is not used to run the `mcp-server-couchbase` script).
*   An OpenAI API Key: Ensure your `OPENAI_API_KEY` environment variable is set. The `react_agent.ipynb` notebook uses `load_dotenv()` to load it from a `.env` file in the project root. Create a `.env` file in the root of this project with your key:
    ```env
    OPENAI_API_KEY=your_openai_api_key_here
    # Also, ensure the MCP server connection variables are available
    # if not hardcoded or passed directly in the notebook.
    # The react_agent.ipynb passes CB_CONNECTION_STRING, CB_USERNAME, 
    # CB_PASSWORD, CB_BUCKET_NAME as env vars to the server process.
    # These can also be in your .env file for the notebook to pick up.
    CB_CONNECTION_STRING=your_couchbase_connection_string
    CB_USERNAME=your_couchbase_username
    CB_PASSWORD=your_couchbase_password
    CB_BUCKET_NAME=your_target_bucket # e.g., travel-sample
    ```

**Running the Demo:**

1.  Ensure all prerequisites are met, especially the Couchbase instance, the local clone of `mcp-server-couchbase`, required Python packages, and your OpenAI API key in the `.env` file.
2.  Verify the path to your local `mcp-server-couchbase` directory within `react_agent.ipynb` (specifically in the `StdioServerParameters` configuration) is correct for your environment.
3.  Open `react_agent.ipynb` in Jupyter Notebook or JupyterLab.
4.  Run the cells in the notebook sequentially.
5.  Observe the output, which will include the questions asked and the AI agent's responses based on its interaction with the Couchbase database via MCP.