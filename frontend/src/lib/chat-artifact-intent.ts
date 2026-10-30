/** Explicit user requests only: file creation never triggers from retrieved content. */
export type ChatArtifactFormat = "docx" | "xlsx" | "pptx" | "pdf" | "md";

const FORMAT_PATTERNS: { kind: ChatArtifactFormat; pattern: RegExp }[] = [
  { kind: "docx", pattern: /\b(?:docx?|word(?:\s+document)?)\b|ওয়ার্ড|ワード|文書/i },
  { kind: "xlsx", pattern: /\b(?:xlsx?|excel|spreadsheet)\b|এক্সেল|スプレッドシート|エクセル/i },
  { kind: "pptx", pattern: /\b(?:pptx?|power\s?point|slide\s?deck|slides?)\b|পাওয়ারপয়েন্ট|スライド|パワーポイント/i },
  { kind: "pdf", pattern: /\bpdf\b|পিডিএফ|ＰＤＦ/i },
  { kind: "md", pattern: /\b(?:markdown|\.md)\b|মার্কডাউন|マークダウン/i },
];

const MAKE = /\b(?:create|make|generate|draft|prepare|export|save|produce|build|write|convert|give(?:\s+me)?|turn\s+(?:this|it)\s+into)\b|(?:বানাও|বানিয়ে|বানিয়ে|তৈরি|করো|করে\s*দাও|দিয়ে\s*দাও|দিয়ে\s*দাও|দাও|বনাও|বনিয়ে)|(?:作成|作って|作る|生成|にして|ファイルに|書いて)/i;
const HOWTO = /^\s*(?:how\s+(?:do|can|to|does|would)|what\s+is|why\s+|কীভাবে|কিভাবে|কেন\s+|どうやって|作り方)/i;
const LIST = /\b(?:show|list|find|open|display|see)\b.{0,60}\b(?:my\s+)?(?:generated\s+|created\s+)?(?:files?|documents?|artifacts?)\b|(?:আমার|আগের).{0,30}(?:ফাইল|ডকুমেন্ট).{0,30}(?:দেখাও|দেখতে|লিস্ট)|(?:作成した|生成した).{0,20}(?:ファイル|文書).{0,10}(?:一覧|見せて)/i;

export function detectChatArtifactIntent(message: string): {
  formats: ChatArtifactFormat[];
  prompt: string;
  title: string;
} | null {
  const prompt = message.trim();
  if (prompt.length < 5 || prompt.length > 4000 || HOWTO.test(prompt) || !MAKE.test(prompt)) {
    return null;
  }
  const matches = FORMAT_PATTERNS.filter(entry => entry.pattern.test(prompt));
  if (!matches.length) return null;
  const formats = matches.map(entry => entry.kind);
  return {
    formats,
    prompt,
    title: ("Aqlyra " + formats[0].toUpperCase() + " file").slice(0, 120),
  };
}

export function wantsChatArtifactList(message: string): boolean {
  return LIST.test(message.trim()) && !HOWTO.test(message);
}
