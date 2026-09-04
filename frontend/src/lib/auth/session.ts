import { cookies } from "next/headers";

const ACCESS_TOKEN_COOKIE = "aqlyra_access_token";
const EMAIL_VERIFICATION_COOKIE =
  "aqlyra_email_verification_token";

export async function setAccessToken(token: string) {
  const cookieStore = await cookies();

  cookieStore.set({
    name: ACCESS_TOKEN_COOKIE,
    value: token,
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
  });
}

export async function getAccessToken() {
  const cookieStore = await cookies();

  return cookieStore.get(ACCESS_TOKEN_COOKIE)?.value ?? null;
}

export async function clearAccessToken() {
  const cookieStore = await cookies();

  cookieStore.delete(ACCESS_TOKEN_COOKIE);
}

export async function setEmailVerificationToken(
  token: string,
) {
  const cookieStore = await cookies();

  cookieStore.set({
    name: EMAIL_VERIFICATION_COOKIE,
    value: token,
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
  });
}

export async function getEmailVerificationToken() {
  const cookieStore = await cookies();

  return (
    cookieStore.get(EMAIL_VERIFICATION_COOKIE)?.value ?? null
  );
}

export async function clearEmailVerificationToken() {
  const cookieStore = await cookies();

  cookieStore.delete(EMAIL_VERIFICATION_COOKIE);
}
