/**
 * Choose the anonymous entrypoint for the currently deployed product mode.
 * The public portfolio walkthrough is explicit opt-in; a real backend
 * deployment should offer authentication instead of hiding it behind /demo.
 */
export function unauthenticatedLanding(
  demoOnly: string | undefined,
): "/demo" | "/login" {
  return demoOnly === "true" ? "/demo" : "/login";
}
