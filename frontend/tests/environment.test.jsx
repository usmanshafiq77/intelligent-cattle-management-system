import { resolveApiBaseUrl, validateApiBaseUrl } from "../src/config/environment";

describe("API environment configuration", () => {
  test("selects explicit web and Android URLs", () => {
    const values = {
      defaultApiBaseUrl: "http://192.168.1.20:8000",
      webApiBaseUrl: "http://localhost:8000/",
      androidApiBaseUrl: "http://10.0.2.2:8000/",
    };

    expect(resolveApiBaseUrl({ ...values, platform: "web" })).toBe("http://localhost:8000");
    expect(resolveApiBaseUrl({ ...values, platform: "android" })).toBe("http://10.0.2.2:8000");
  });

  test("falls back to a LAN-reachable default for a physical device", () => {
    expect(resolveApiBaseUrl({
      platform: "android",
      defaultApiBaseUrl: "http://192.168.1.20:8000",
      androidApiBaseUrl: null,
    })).toBe("http://192.168.1.20:8000");
  });

  test("rejects credentials, API paths, Android localhost, and production HTTP", () => {
    expect(() => validateApiBaseUrl("http://user:pass@example.com")).toThrow(/credentials/);
    expect(() => validateApiBaseUrl("http://localhost:8000/api/v1")).toThrow(/only the scheme/);
    expect(() => validateApiBaseUrl("http://localhost:8000", { platform: "android" })).toThrow(/10\.0\.2\.2/);
    expect(() => validateApiBaseUrl("http://api.example.com", { appEnvironment: "production" })).toThrow(/HTTPS/);
    expect(validateApiBaseUrl("https://api.example.com/", { appEnvironment: "production" })).toBe("https://api.example.com");
  });
});
