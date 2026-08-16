export function buildConversationTitle(
  value: string,
) {
  const normalized =
    value
      .replace(/\s+/g, " ")
      .trim()
      .replace(/[.!?]+$/g, "");

  if (!normalized) {
    return "New chat";
  }

  const words =
    normalized.split(" ");

  let title =
    words
      .slice(0, 8)
      .join(" ");

  if (title.length > 72) {
    title =
      `${title
        .slice(0, 69)
        .trimEnd()}…`;
  }

  return title;
}
