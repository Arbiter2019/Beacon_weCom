import crypto from "node:crypto";
import { fileURLToPath } from "node:url";

export const DEFAULT_FONT_FAMILY = "Alibaba PuHuiTi 3.0";

const FONT_FILES = [
  ["AlibabaPuHuiTi-3-55-Regular.ttf", "normal"],
  ["AlibabaPuHuiTi-3-65-Medium.ttf", "500"],
  ["AlibabaPuHuiTi-3-75-SemiBold.ttf", "600"],
  ["AlibabaPuHuiTi-3-85-Bold.ttf", "bold"],
];

let fontsRegistered = false;

export function buildStorageKey(now = new Date(), id = crypto.randomUUID()) {
  const year = String(now.getUTCFullYear());
  const month = String(now.getUTCMonth() + 1).padStart(2, "0");
  const day = String(now.getUTCDate()).padStart(2, "0");
  return `charts/${year}/${month}/${day}/${id}.png`;
}

export function withDefaultFont(option, fontFamily = DEFAULT_FONT_FAMILY) {
  return {
    ...option,
    textStyle: {
      fontFamily,
      ...(option.textStyle || {}),
    },
  };
}

async function registerChineseFonts(registerFont, fontFamily = DEFAULT_FONT_FAMILY) {
  if (fontsRegistered) {
    return;
  }
  for (const [fileName, weight] of FONT_FILES) {
    const fontPath = fileURLToPath(
      new URL(`../node_modules/@fontpkg/alibaba-pu-hui-ti-3-0/${fileName}`, import.meta.url),
    );
    registerFont(fontPath, { family: fontFamily, weight });
  }
  fontsRegistered = true;
}

export async function defaultRenderer(option, width = 800, height = 480) {
  const echarts = await import("echarts");
  const { createCanvas, registerFont } = await import("canvas");
  await registerChineseFonts(registerFont);
  const canvas = createCanvas(width, height);
  const chart = echarts.init(canvas, null, { renderer: "canvas", width, height });
  chart.setOption(withDefaultFont(option));
  const buffer = canvas.toBuffer("image/png");
  chart.dispose();
  return buffer;
}

export async function renderAndStoreChart({
  option,
  width = 800,
  height = 480,
  renderer = defaultRenderer,
  storage,
  now = new Date(),
  idFactory = crypto.randomUUID,
}) {
  if (!option || typeof option !== "object" || Array.isArray(option)) {
    throw new Error("option must be an object");
  }
  if (!storage || typeof storage.putObject !== "function") {
    throw new Error("storage.putObject is required");
  }

  const png = await renderer(option, width, height);
  const storageKey = buildStorageKey(now, idFactory());
  const stored = await storage.putObject(storageKey, png, "image/png");
  return {
    image_url: stored.image_url,
    storage_key: stored.storage_key || storageKey,
    width,
    height,
    option,
  };
}
