import assert from "node:assert/strict";
import test from "node:test";
import { detectChatArtifactIntent, wantsChatArtifactList } from "../src/lib/chat-artifact-intent.ts";

test("explicit user asks for document output in the chat", () => {
  assert.deepEqual(detectChatArtifactIntent("Please create a PDF report on AI").formats, ["pdf"]);
  assert.deepEqual(detectChatArtifactIntent("Make a Word and PowerPoint presentation").formats, ["docx", "pptx"]);
  assert.deepEqual(detectChatArtifactIntent("একটা Excel ফাইল বানাও")?.formats, ["xlsx"]);
  assert.deepEqual(detectChatArtifactIntent("PDF বানিয়ে দাও").formats, ["pdf"]);
  assert.deepEqual(detectChatArtifactIntent("PDFを作成して").formats, ["pdf"]);
});
test("ordinary chat never becomes an unsolicited artifact action", () => {
  assert.equal(detectChatArtifactIntent("How can I create a PDF?"), null);
  assert.equal(detectChatArtifactIntent("Explain what PowerPoint is"), null);
  assert.equal(detectChatArtifactIntent("Summarize this document"), null);
  assert.equal(detectChatArtifactIntent("PDF please"), null);
  assert.equal(detectChatArtifactIntent("Read a PDF document"), null);
});
test("generated files remain accessible from chat by asking for them", () => {
  assert.equal(wantsChatArtifactList("Show my generated files"), true);
  assert.equal(wantsChatArtifactList("What is a file?"), false);
});
