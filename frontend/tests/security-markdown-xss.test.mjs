import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { defaultUrlTransform } from "react-markdown";

const markdownSource = readFileSync(
  new URL("../src/components/chat/markdown-message.tsx", import.meta.url),
  "utf8",
);

test("model-generated Markdown cannot inject raw HTML or inline scripts", () => {
  assert.match(markdownSource, /skipHtml/);
  assert.doesNotMatch(markdownSource, /dangerouslySetInnerHTML/);
  assert.match(markdownSource, /img:\s*\(\) => null/);
  assert.match(markdownSource, /rel="noopener noreferrer"/);
});

test("react-markdown default URL policy rejects script and data schemes", () => {
  const unsafe = [
    "javascript:alert(1)",
    "JaVaScRiPt:alert(1)",
    "data:text/html;base64,PHNjcmlwdD4=",
    "vbscript:msgbox(1)",
  ];
  for (const url of unsafe) {
    assert.equal(defaultUrlTransform(url), "", url);
  }
  assert.equal(
    defaultUrlTransform("https://example.org/research"),
    "https://example.org/research",
  );
});
