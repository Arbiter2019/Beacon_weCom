import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { createChatbiClient, createToolDefinitions } from "../src/tools.js";

describe("chatbi tools", () => {
  it("calls BE with X-ChatBI-Token and returns rows/meta", async () => {
    const calls = [];
    const client = createChatbiClient({
      baseUrl: "http://wecom-api:8717",
      token: "secret",
      fetchImpl: async (url, init) => {
        calls.push({ url, init });
        return {
          ok: true,
          status: 200,
          async json() {
            return {
              request_id: "req_1",
              sql: "select 1",
              rows: [{ value: 1 }],
              meta: { row_count: 1 },
            };
          },
        };
      },
    });

    const result = await client.get("/api/chatbi/freshness", { request_id: "req_1" });

    assert.equal(calls[0].url, "http://wecom-api:8717/api/chatbi/freshness?request_id=req_1");
    assert.equal(calls[0].init.headers["X-ChatBI-Token"], "secret");
    assert.deepEqual(result.rows, [{ value: 1 }]);
    assert.deepEqual(result.meta, { row_count: 1 });
  });

  it("throws a useful error when BE rejects the request", async () => {
    const client = createChatbiClient({
      baseUrl: "http://wecom-api:8717/",
      token: "secret",
      fetchImpl: async () => ({
        ok: false,
        status: 401,
        async text() {
          return "invalid chatbi token";
        },
      }),
    });

    await assert.rejects(
      () => client.get("/api/chatbi/freshness", {}),
      /BE request failed 401: invalid chatbi token/,
    );
  });

  it("exposes one tool per ChatBI endpoint", () => {
    const tools = createToolDefinitions(createChatbiClient({ baseUrl: "http://x", token: "t" }));

    assert.deepEqual(
      tools.map((tool) => tool.name),
      [
        "chatbi_freshness",
        "chatbi_message_volume",
        "chatbi_response_time",
        "chatbi_questions",
        "chatbi_sentiment",
        "chatbi_hotwords",
        "chatbi_archive_search",
      ],
    );
  });
});
