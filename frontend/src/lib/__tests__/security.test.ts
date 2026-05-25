import { sanitizeRedirect } from "@/lib/security";
import { describe, expect, it } from "vitest";

describe("sanitizeRedirect", () => {
  it("allows root-relative paths", () => {
    expect(sanitizeRedirect("/dashboard")).toBe("/dashboard");
    expect(sanitizeRedirect("/path/to/page?x=1#y")).toBe("/path/to/page?x=1#y");
  });

  it("rejects http external URLs", () => {
    expect(sanitizeRedirect("http://evil.com/x")).toBe("/");
  });

  it("rejects https external URLs", () => {
    expect(sanitizeRedirect("https://evil.com/x")).toBe("/");
  });

  it("rejects javascript: URLs", () => {
    expect(sanitizeRedirect("javascript:alert(1)")).toBe("/");
  });

  it("rejects data: URLs", () => {
    expect(sanitizeRedirect("data:text/html,<script>alert(1)</script>")).toBe("/");
  });

  it("rejects protocol-relative URLs", () => {
    expect(sanitizeRedirect("//evil.com/path")).toBe("/");
  });

  it("rejects backslash-confusion paths", () => {
    expect(sanitizeRedirect("/\\evil.com")).toBe("/");
  });

  it("returns fallback for empty input", () => {
    expect(sanitizeRedirect("")).toBe("/");
  });
});
