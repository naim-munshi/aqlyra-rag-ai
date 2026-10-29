import { redirect } from "next/navigation";

// Old/shared signup URLs should resolve to the canonical registration flow.
export default function SignUpRedirect() {
  redirect("/register");
}
