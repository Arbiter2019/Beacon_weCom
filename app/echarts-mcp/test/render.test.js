import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { buildStorageKey, DEFAULT_FONT_FAMILY, renderAndStoreChart, withDefaultFont } from "../src/render.js";

describe("echarts render service", () => {
  it("renders chart, uploads PNG, and returns image metadata", async () => {
    const uploads = [];
    const result = await renderAndStoreChart({
      option: { xAxis: { type: "category", data: ["A"] }, yAxis: {}, series: [{ type: "bar", data: [1] }] },
      width: 640,
      height: 360,
      renderer: async () => Buffer.from("png-bytes"),
      storage: {
        async putObject(key, data, contentType) {
          uploads.push({ key, data, contentType });
          return { image_url: `https://charts.example.com/${key}` };
        },
      },
      now: new Date("2026-08-05T10:12:00+08:00"),
      idFactory: () => "fixed-id",
    });

    assert.equal(uploads[0].contentType, "image/png");
    assert.equal(uploads[0].data.toString(), "png-bytes");
    assert.equal(result.storage_key, "charts/2026/08/05/fixed-id.png");
    assert.equal(result.image_url, "https://charts.example.com/charts/2026/08/05/fixed-id.png");
    assert.equal(result.width, 640);
    assert.deepEqual(result.option.series[0].data, [1]);
  });

  it("builds date-partitioned storage keys", () => {
    const key = buildStorageKey(new Date("2026-08-05T00:00:00Z"), "abc");

    assert.equal(key, "charts/2026/08/05/abc.png");
  });

  it("adds Alibaba PuHuiTi as the default chart font", () => {
    const option = withDefaultFont({ title: { text: "中文标题" }, textStyle: { color: "#333" } });

    assert.equal(option.textStyle.fontFamily, DEFAULT_FONT_FAMILY);
    assert.equal(option.textStyle.color, "#333");
  });

  it("requires an echarts option object", async () => {
    await assert.rejects(
      () =>
        renderAndStoreChart({
          option: null,
          renderer: async () => Buffer.from("png"),
          storage: { putObject: async () => ({ image_url: "x" }) },
        }),
      /option must be an object/,
    );
  });
});
