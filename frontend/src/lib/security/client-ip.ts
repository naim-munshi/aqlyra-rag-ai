import { isIP } from "node:net";

/**
 * Only a trusted reverse proxy may supply a client IP to the backend
 * rate limiter. Browser-supplied X-Aqlyra-Client-IP is untrusted.
 *
 * Our Docker Caddy ingress overwrites this header with the socket IP.
 * Never opt in on direct Vercel/public ingress without a trusted
 * upstream that reliably overwrites inbound client-supplied headers.
 */
export function trustedProxyClientIp(
  request: Request,
  trustCaddyHeader = process.env.AQLYRA_TRUST_CADDY_IP_HEADER === "true",
): string | null {
  if (!trustCaddyHeader) {
    return null;
  }

  const candidate = request.headers.get("x-aqlyra-client-ip")?.trim();

  return candidate && isIP(candidate) !== 0 ? candidate : null;
}
