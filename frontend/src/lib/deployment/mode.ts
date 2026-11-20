/**
 * Anonymous visitors are routed to the real account entrypoint.
 * Legacy demo-only environment values are intentionally ignored.
 */
export function unauthenticatedLanding(
  _demoOnly: string | undefined,
): "/login" {
  return "/login";
}
