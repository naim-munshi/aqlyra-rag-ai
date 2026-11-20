/**
 * Anonymous visitors are routed to the real account entrypoint.
 * Legacy demo-only environment values are intentionally ignored.
 */
export function unauthenticatedLanding(
  demoOnly: string | undefined,
): "/login" {
  void demoOnly;
  return "/login";
}
