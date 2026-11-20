/** Pure safety gate for retrying the signed-in workspace after an outage.
 *
 * A healthy infrastructure probe by itself is NOT proof that the user's
 * session endpoint is back. Only the authenticated user endpoint returning
 * 200, or a definitive 401 requiring a public redirect, can cause a reload.
 * In particular, never reload repeatedly on 5xx/timeout responses.
 */
export function canReloadAfterRecovery(
  healthStatus: number,
  healthBody: unknown,
  sessionStatus: number,
): boolean {
  if (
    healthStatus !== 200 ||
    typeof healthBody !== "object" ||
    healthBody === null ||
    !("status" in healthBody) ||
    healthBody.status !== "ready"
  ) {
    return false;
  }
  return sessionStatus === 200 || sessionStatus === 401;
}

export const RECOVERY_CHECK_INTERVAL_MS = 7_000;
export const RECOVERY_CHECK_TIMEOUT_MS = 14_000;
export const RECOVERY_MAX_CHECKS = 12;
