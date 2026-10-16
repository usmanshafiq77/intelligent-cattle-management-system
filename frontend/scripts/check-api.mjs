const includeDatabase = process.argv.includes("--db");
const configured = process.env.EXPO_PUBLIC_API_BASE_URL_WEB
  || process.env.EXPO_PUBLIC_API_BASE_URL;

if (!configured) {
  console.error("No web API address is configured. Set EXPO_PUBLIC_API_BASE_URL_WEB or EXPO_PUBLIC_API_BASE_URL.");
  process.exitCode = 1;
} else {
  let baseUrl;
  try {
    const parsed = new URL(configured);
    if (!["http:", "https:"].includes(parsed.protocol) || parsed.username || parsed.password) {
      throw new Error("The URL must be an HTTP(S) origin without credentials.");
    }
    if ((parsed.pathname && parsed.pathname !== "/") || parsed.search || parsed.hash) {
      throw new Error("The URL must not contain a path, query, or fragment.");
    }
    baseUrl = `${parsed.protocol}//${parsed.host}`;
  } catch (error) {
    console.error(`Invalid API address: ${error.message}`);
    process.exitCode = 1;
  }

  if (baseUrl) {
    const paths = ["/api/v1/health", ...(includeDatabase ? ["/api/v1/health/db"] : [])];
    try {
      for (const path of paths) {
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), 5000);
        try {
          const response = await fetch(`${baseUrl}${path}`, {
            headers: { Accept: "application/json" },
            signal: controller.signal,
          });
          if (!response.ok) throw new Error(`${path} returned HTTP ${response.status}`);
          const payload = await response.json();
          console.log(`${path}: ${payload.status || "ok"}`);
        } finally {
          clearTimeout(timer);
        }
      }
      console.log(`ICMS API reachable at ${baseUrl}`);
    } catch (error) {
      const message = error.name === "AbortError"
        ? "The API health check timed out after 5 seconds."
        : error.message;
      console.error(`ICMS API connectivity failed: ${message}`);
      process.exitCode = 1;
    }
  }
}
