import { redirect } from "next/navigation";

// Keep existing sign-in bookmarks working without creating an extra auth UI.
export default function SignInRedirect() {
  redirect("/login");
}
