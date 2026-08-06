import express from "express";
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { SSEServerTransport } from "@modelcontextprotocol/sdk/server/sse.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";

import { createChatbiClient, createToolDefinitions } from "./tools.js";

const port = Number(process.env.CHATBI_MCP_PORT || 8731);
const baseUrl = process.env.CHATBI_BE_BASE_URL || "http://wecom-api:8717";
const token = process.env.CHATBI_TOKEN || "dev-chatbi-token";

const client = createChatbiClient({ baseUrl, token });
const tools = createToolDefinitions(client);
const toolsByName = new Map(tools.map((tool) => [tool.name, tool]));

function createMcpServer() {
  const server = new Server(
    { name: "chatbi-mcp", version: "0.1.0" },
    { capabilities: { tools: {} } },
  );

  server.setRequestHandler(ListToolsRequestSchema, async () => ({
    tools: tools.map(({ name, description, inputSchema }) => ({ name, description, inputSchema })),
  }));

  server.setRequestHandler(CallToolRequestSchema, async (request) => {
    const tool = toolsByName.get(request.params.name);
    if (!tool) {
      throw new Error(`Unknown tool: ${request.params.name}`);
    }
    const result = await tool.execute(request.params.arguments || {});
    return {
      content: [
        {
          type: "text",
          text: JSON.stringify(result, null, 2),
        },
      ],
    };
  });

  return server;
}

const app = express();
const transports = new Map();

app.get("/health", (_req, res) => {
  res.json({ ok: true, service: "chatbi-mcp" });
});

app.get("/sse", async (_req, res) => {
  const transport = new SSEServerTransport("/messages", res);
  const server = createMcpServer();
  transports.set(transport.sessionId, { transport, server });
  res.on("close", () => {
    transports.delete(transport.sessionId);
    server.close().catch(() => {});
  });
  await server.connect(transport);
});

app.post("/messages", async (req, res) => {
  const sessionId = req.query.sessionId;
  const session = transports.get(sessionId);
  if (!session) {
    res.status(404).send("unknown session");
    return;
  }
  await session.transport.handlePostMessage(req, res);
});

app.listen(port, () => {
  console.log(`chatbi-mcp listening on ${port}`);
});
