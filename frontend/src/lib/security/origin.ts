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


/**
 * Allow only the backend's non-browser POST to the fixed semantic relay.
 * Existing cookie/Origin/Sec-Fetch CSRF checks remain unchanged elsewhere.
 * This is NOT final authentication: /v1/embed forwards the Bearer credential
 * to the existing worker, whose constant-time secret check remains required.
 */
export function isServerSemanticRelayRequest(request: Request): boolean {
  if (
    request.method !== "POST" ||
    new URL(request.url).pathname !== "/api/internal/semantic/v1/embed"
  ) {
    return false;
  }
  // Browser requests carry provenance or cookies and still require normal
  // CSRF verification. Do not accept arbitrary forged Origin/Referer values.
  for (const name of ["origin", "referer", "sec-fetch-site", "cookie"]) {
    if (request.headers.has(name)) {
      return false;
    }
  }
  const authorization = request.headers.get("authorization") || "";
  return /^Bearer [A-Za-z0-9._~+/=-]{32,1024}$/.test(authorization);
}
