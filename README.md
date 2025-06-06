# Couchbase MCP Integrations

This project demonstrates the integration of a Large Language Model (LLM) with a Couchbase database using the Model Context Protocol (MCP). It showcases how AI agents can understand natural language queries, interact with a Couchbase instance to retrieve or manipulate data, and provide meaningful responses.

Users can ask questions like:
*   "List out the top 5 hotels by the highest aggregate rating?"
*   "Recommend me a flight and hotel from New York to San Francisco."
*   And other questions relevant to the specific dataset and agent implementation in each tutorial.

## Introduction to Model Context Protocol (MCP)

The Model Context Protocol (MCP) is an open standard designed to standardize how AI assistants and applications connect to and interact with external data sources, tools, and systems. Think of MCP as a universal adapter that allows AI models to seamlessly access the context they need to produce more relevant, accurate, and actionable responses.

**Key Goals and Features of MCP:**

*   **Standardized Communication:** MCP provides a common language and structure for AI models to communicate with diverse backend systems, replacing the need for numerous custom integrations.
*   **Enhanced Context Management:** It helps manage the limited context windows of LLMs efficiently, enabling them to maintain longer, more coherent interactions and leverage historical data.
*   **Secure Data Access:** MCP emphasizes secure connections, allowing developers to expose data through MCP servers while maintaining control over their infrastructure.
*   **Tool Use and Actionability:** It enables LLMs to not just retrieve information but also to use external tools and trigger actions in other systems.
*   **Interoperability:** Fosters an ecosystem where different AI tools, models, and data sources can work together more cohesively.
*   **Client-Server Architecture:** MCP typically involves:
    *   **MCP Hosts/Clients:** Applications (like AI assistants, IDEs, or other AI-powered tools) that want to access data or capabilities. In some demos, LangChain acts as an MCP client.
    *   **MCP Servers:** Lightweight programs that expose specific data sources or tools (e.g., a database, an API) through the standardized MCP. The [`mcp-server-couchbase`](https://github.com/Couchbase-Ecosystem/mcp-server-couchbase) project fulfills this role for Couchbase.

MCP aims to break down data silos, making it easier for AI to integrate with real-world applications and enterprise systems, leading to more powerful and context-aware AI solutions. It is an open-source initiative, often supported by SDKs in various programming languages to facilitate the development of MCP clients and servers.

## Prerequisites

- Python 3.10 or higher.
- A running Couchbase cluster. The easiest way to get started is to use [Capella](https://docs.couchbase.com/cloud/get-started/create-account.html#getting-started) free tier, which is fully managed version of Couchbase server. You can follow [instructions](https://docs.couchbase.com/cloud/clusters/data-service/import-data-documents.html#import-sample-data) to import one of the sample datasets or import your own.
- [uv](https://docs.astral.sh/uv/) installed to run the server.

## Setup

### 1. Clone the repository:
   ```bash
   git clone https://github.com/couchbase-examples/mcp-cookbook.git
   cd mcp-cookbook
   ```

### 2. Fill in environment variables:

Use the `.env` file in each tutorial's directory to fill details about the environment variables required to run each tutorial.

### 3. Run the notebook file

You can either run the notebook file on [Google Colab](https://colab.research.google.com/) or run it on your system by setting up the Python environment.

## Support Policy

Contributions are welcome! Please feel free to submit a pull request or open an issue for any bugs or feature requests.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
