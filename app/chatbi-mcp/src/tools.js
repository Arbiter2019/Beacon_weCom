const ENDPOINTS = [
  {
    name: "chatbi_freshness",
    description: "Get latest successful analysis date and T+1 freshness metadata.",
    path: "/api/chatbi/freshness",
    schema: {
      type: "object",
      properties: {
        request_id: { type: "string" },
      },
    },
  },
  {
    name: "chatbi_message_volume",
    description: "Query message volume from analysis DB.",
    path: "/api/chatbi/message-volume",
    schema: {
      type: "object",
      required: ["start_date", "end_date"],
      properties: {
        request_id: { type: "string" },
        start_date: { type: "string" },
        end_date: { type: "string" },
        conversation_type: { type: "string", enum: ["all", "single", "room"] },
      },
    },
  },
  {
    name: "chatbi_response_time",
    description: "Query response time from analysis DB.",
    path: "/api/chatbi/response-time",
    schema: {
      type: "object",
      required: ["start_date", "end_date"],
      properties: {
        request_id: { type: "string" },
        start_date: { type: "string" },
        end_date: { type: "string" },
        conversation_type: { type: "string", enum: ["all", "single", "room"] },
      },
    },
  },
  {
    name: "chatbi_questions",
    description: "Query question detail samples from analysis DB.",
    path: "/api/chatbi/questions",
    schema: {
      type: "object",
      required: ["start_date", "end_date"],
      properties: {
        request_id: { type: "string" },
        start_date: { type: "string" },
        end_date: { type: "string" },
        limit: { type: "number" },
      },
    },
  },
  {
    name: "chatbi_sentiment",
    description: "Query sentiment summary from analysis DB.",
    path: "/api/chatbi/sentiment",
    schema: {
      type: "object",
      required: ["start_date", "end_date"],
      properties: {
        request_id: { type: "string" },
        start_date: { type: "string" },
        end_date: { type: "string" },
      },
    },
  },
  {
    name: "chatbi_hotwords",
    description: "Query hotwords from analysis DB.",
    path: "/api/chatbi/hotwords",
    schema: {
      type: "object",
      required: ["start_date", "end_date"],
      properties: {
        request_id: { type: "string" },
        start_date: { type: "string" },
        end_date: { type: "string" },
        top_n: { type: "number" },
      },
    },
  },
  {
    name: "chatbi_archive_search",
    description: "Search archive message text with Beijing-time input and archive row limit.",
    path: "/api/chatbi/archive-search",
    schema: {
      type: "object",
      required: ["keyword", "start_datetime", "end_datetime"],
      properties: {
        request_id: { type: "string" },
        keyword: { type: "string" },
        start_datetime: { type: "string" },
        end_datetime: { type: "string" },
        conversation_type: { type: "string", enum: ["all", "single", "room"] },
        limit: { type: "number" },
      },
    },
  },
];

export function createChatbiClient({ baseUrl, token, fetchImpl = globalThis.fetch }) {
  const normalizedBaseUrl = baseUrl.replace(/\/+$/, "");
  return {
    async get(path, params = {}) {
      const url = new URL(`${normalizedBaseUrl}${path}`);
      for (const [key, value] of Object.entries(params)) {
        if (value !== undefined && value !== null && value !== "") {
          url.searchParams.set(key, String(value));
        }
      }
      const response = await fetchImpl(url.toString(), {
        method: "GET",
        headers: {
          "X-ChatBI-Token": token,
          Accept: "application/json",
        },
      });
      if (!response.ok) {
        const body = await response.text();
        throw new Error(`BE request failed ${response.status}: ${body}`);
      }
      return response.json();
    },
  };
}

export function createToolDefinitions(client) {
  return ENDPOINTS.map((endpoint) => ({
    name: endpoint.name,
    description: endpoint.description,
    inputSchema: endpoint.schema,
    async execute(args = {}) {
      return client.get(endpoint.path, args);
    },
  }));
}

export function getEndpointDefinitions() {
  return ENDPOINTS;
}
