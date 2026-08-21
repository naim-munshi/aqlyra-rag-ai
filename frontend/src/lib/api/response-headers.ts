export function forwardedBackendHeaders(
  response: Response,
): Record<string, string> {
  const headers: Record<string, string> = {};

  const retryAfter =
    response.headers.get("retry-after");

  if (retryAfter) {
    headers["Retry-After"] = retryAfter;
  }

  return headers;
}
