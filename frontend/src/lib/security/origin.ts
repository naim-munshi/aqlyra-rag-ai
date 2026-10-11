/**
 * Reject cross-site state changes to cookie-authenticated API routes.
 * Caddy preserves the public Host and sets X-Forwarded-Proto.
 */
export function hasTrustedRequestOrigin(request: Request): boolean {
  if (!["POST", "PUT", "PATCH", "DELETE"].includes(request.method)) {
    return true;
  }

  const fetchSite = request.headers.get("sec-fetch-site");
  if (fetchSite === "cross-site" || fetchSite === "same-site") {
    return false;
  }

  const url = new URL(request.url);
  const host = request.headers.get("host") ?? url.host;
  const protocol =
    request.headers.get("x-forwarded-proto") ??
    url.protocol.slice(0, -1);

  if (!["http", "https"].includes(protocol)) {
    return false;
  }

  let expected: string;
  try {
    expected = new URL(protocol + "://" + host).origin;
  } catch {
    return false;
  }

  const origin = request.headers.get("origin");
  if (origin !== null) {
    try {
      return new URL(origin).origin === expected && origin === expected;
    } catch {
      return false;
    }
  }

  // Without Origin, require independent same-origin browser metadata.
  if (fetchSite === "same-origin") {
    return true;
  }

  const referer = request.headers.get("referer");
  if (!referer) {
    return false;
  }

  try {
    return new URL(referer).origin === expected;
  } catch {
    return false;
  }
}
