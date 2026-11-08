/** All credential-bearing JSON responses use an explicit non-cacheable boundary. */
export function privateJsonResponse(
  body: unknown,
  init: ResponseInit = {},
): Response {
  const headers = new Headers(init.headers);
  // Override upstream headers, never forward a cache-friendly policy.
  headers.set("Cache-Control", "private, no-store, max-age=0");
  const vary = headers.get("Vary");
  if (!vary?.split(",").some((part) => part.trim().toLowerCase() === "cookie")) {
    headers.set("Vary", vary ? `${vary}, Cookie` : "Cookie");
  }
  headers.set("Pragma", "no-cache");
  headers.set("Expires", "0");
  return Response.json(body, { ...init, headers });
}
