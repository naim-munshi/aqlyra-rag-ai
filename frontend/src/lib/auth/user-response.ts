import type { UserResponse } from "@/types/auth";

/** Treat a malformed upstream 200 as an outage, never a logged-out user.
 * The backend validates the JWT and supplies these fields as UserResponse.
 * This check is only a response-shape guard; it does not authorize a user.
 */
export function isValidUserIdentity(value: unknown): value is UserResponse {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    return false;
  }
  const user = value as Record<string, unknown>;
  return (
    typeof user.id === "string" &&
    user.id.trim().length > 0 &&
    typeof user.username === "string" &&
    user.username.trim().length > 0 &&
    typeof user.email === "string" &&
    user.email.trim().length > 0 &&
    user.is_active === true &&
    (user.email_verified_at === null || typeof user.email_verified_at === "string") &&
    typeof user.created_at === "string" &&
    typeof user.updated_at === "string"
  );
}
