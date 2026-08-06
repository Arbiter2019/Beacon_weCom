import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { buildImageUrl, buildObjectKey, normalizeEndpoint, normalizePrefix } from "../src/storage.js";

describe("echarts OSS storage helpers", () => {
  it("normalizes OSS endpoint to https when protocol is omitted", () => {
    assert.equal(
      normalizeEndpoint("oss-cn-shanghai-internal.aliyuncs.com"),
      "https://oss-cn-shanghai-internal.aliyuncs.com",
    );
    assert.equal(
      normalizeEndpoint("https://oss-cn-shanghai.aliyuncs.com"),
      "https://oss-cn-shanghai.aliyuncs.com",
    );
  });

  it("normalizes OSS prefix for object keys", () => {
    assert.equal(normalizePrefix("wecom"), "wecom/");
    assert.equal(normalizePrefix("/wecom/"), "wecom/");
    assert.equal(normalizePrefix(""), "");
  });

  it("uploads under prefix but returns URL relative to public base", () => {
    assert.equal(buildObjectKey("wecom/", "charts/2026/08/05/a.png"), "wecom/charts/2026/08/05/a.png");
    assert.equal(
      buildImageUrl("https://res.jhpy.com/wecom/", "charts/2026/08/05/a.png"),
      "https://res.jhpy.com/wecom/charts/2026/08/05/a.png",
    );
  });
});
