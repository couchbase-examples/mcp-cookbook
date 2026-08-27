---
# frontmatter
path: "/mcp-server-oauth/cognito-nondcr-setup"
title: "Securing Couchbase MCP Server with AWS Cognito — Non-DCR flow"
short_title: "Couchbase MCP Server OAuth with AWS Cognito - Non-DCR"
description:
  - Learn how to run the Couchbase MCP server in Streamable HTTP mode with OAuth so it can serve browser login clients authenticated by AWS Cognito.
  - This tutorial walks through creating a Cognito User Pool with a public SPA app client, a resource server whose identifier matches the MCP server's canonical resource URI, and a manually created test user.
  - You will complete the authorization code plus PKCE flow, and verify the issued access token end to end using MCP Inspector or VS Code.
content_type: tutorial
filter: mcp
technology:
  - model context protocol (mcp)
tags:
  - Model Context Protocol (MCP)
sdk_language:
  - python
length: 30 Mins
---
