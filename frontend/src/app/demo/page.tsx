import { redirect } from "next/navigation";

/** The scripted public preview is retired; keep the application entry authenticated. */
export default function DemoPage() {
  redirect("/login");
}
