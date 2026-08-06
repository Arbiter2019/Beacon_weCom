import express from "express";
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { SSEServerTransport } from "@modelcontextprotocol/sdk/server/sse.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";

import { renderAndStoreChart } from "./render.js";
import { createOssStorageFromEnv } from "./storage.js";

const port = Number(process.env.ECHARTS_MCP_PORT || 8732);
const storage = await createOssStorageFromEnv();

const tool = {
  name: "echarts_render_chart",
  description: "Render an Apache ECharts option to PNG, upload it to OSS, and return image metadata.",
  inputSchema: {
    type: "object",
    required: ["option"],
    properties: {
      option: { type: "object" },
      width: { type: "number" },
      height: { type: "number" },
    },
  },
};

function createMcpServer() {
  const server = new Server(
    { name: "echarts-mcp", version: "0.1.0" },
    { capabilities: { tools: {} } },
  );

  server.setRequestHandler(ListToolsRequestSchema, async () => ({ tools: [tool] }));

  server.setRequestHandler(CallToolRequestSchema, async (request) => {
    if (request.params.name !== tool.name) {
      throw new Error(`Unknown tool: ${request.params.name}`);
    }
    const args = request.params.arguments || {};
    const result = await renderAndStoreChart({
      option: args.option,
      width: args.width,
      height: args.height,
      storage,
    });
    return {
      content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
    };
  });

  return server;
}

const app = express();
const transports = new Map();

app.get("/health", (_req, res) => {
  res.json({ ok: true, service: "echarts-mcp" });
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
  console.log(`echarts-mcp listening on ${port}`);
});
