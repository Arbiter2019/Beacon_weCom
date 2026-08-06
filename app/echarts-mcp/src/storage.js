export function createOssStorageFromEnv(env = process.env) {
  const required = [
    "CHART_OSS_ACCESS_KEY_ID",
    "CHART_OSS_ACCESS_KEY_SECRET",
    "CHART_OSS_BUCKET",
    "CHART_OSS_ENDPOINT",
  ];
  for (const key of required) {
    if (!env[key]) {
      throw new Error(`${key} is required`);
    }
  }
  const publicBaseUrl = (env.CHART_OSS_PUBLIC_BASE_URL || "").replace(/\/+$/, "");
  const prefix = normalizePrefix(env.CHART_OSS_PREFIX || "");
  return createAliOssStorage({
    accessKeyId: env.CHART_OSS_ACCESS_KEY_ID,
    accessKeySecret: env.CHART_OSS_ACCESS_KEY_SECRET,
    bucket: env.CHART_OSS_BUCKET,
    endpoint: normalizeEndpoint(env.CHART_OSS_ENDPOINT),
    region: env.CHART_OSS_REGION,
    prefix,
    publicBaseUrl,
  });
}

export function normalizeEndpoint(endpoint) {
  const value = String(endpoint || "").trim();
  if (!value) {
    return value;
  }
  return /^https?:\/\//i.test(value) ? value : `https://${value}`;
}

export function normalizePrefix(prefix = "") {
  const trimmed = String(prefix).replace(/^\/+|\/+$/g, "");
  return trimmed ? `${trimmed}/` : "";
}

export function buildObjectKey(prefix, key) {
  return `${normalizePrefix(prefix)}${String(key).replace(/^\/+/, "")}`;
}

export function buildImageUrl(publicBaseUrl, key) {
  const base = String(publicBaseUrl || "").replace(/\/+$/, "");
  return base ? `${base}/${String(key).replace(/^\/+/, "")}` : "";
}

export async function createAliOssStorage(config) {
  const { default: OSS } = await import("ali-oss");
  const client = new OSS({
    accessKeyId: config.accessKeyId,
    accessKeySecret: config.accessKeySecret,
    bucket: config.bucket,
    endpoint: config.endpoint,
    region: config.region,
  });
  return {
    async putObject(key, data, contentType) {
      const objectKey = buildObjectKey(config.prefix, key);
      const result = await client.put(objectKey, data, {
        headers: { "Content-Type": contentType },
      });
      return {
        image_url: buildImageUrl(config.publicBaseUrl, key) || result.url,
        storage_key: objectKey,
      };
    },
  };
}
