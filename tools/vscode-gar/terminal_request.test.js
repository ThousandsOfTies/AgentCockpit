const assert = require("node:assert/strict");
const test = require("node:test");

const {
  processedStatusFor,
  shellQuote,
  terminalCommand,
  validateTerminalRequest,
} = require("./terminal_request");

test("shellQuote preserves spaces, apostrophes, and shell metacharacters", () => {
  assert.equal(shellQuote("/tmp/a b/$HOME's"), "'/tmp/a b/$HOME'\\''s'");
});

test("terminalCommand changes directory only when reusing a terminal", () => {
  const request = {
    command: "printf '%s\\n' hello",
    cwd: "/tmp/a user's workspace",
  };

  assert.equal(terminalCommand(request, true), request.command);
  assert.equal(
    terminalCommand(request, false),
    "cd '/tmp/a user'\\''s workspace' && printf '%s\\n' hello"
  );
});

test("validateTerminalRequest normalizes a valid request", () => {
  const request = validateTerminalRequest(
    { id: "request-1", command: "echo hello" },
    "fallback",
    "/workspace"
  );

  assert.deepEqual(request, {
    valid: true,
    id: "request-1",
    title: "Gapless Agent Runtime",
    command: "echo hello",
    cwd: "/workspace",
    error: null,
  });
});

test("validateTerminalRequest rejects malformed fields and unsafe ids", () => {
  const cases = [
    [null, "Request must be a JSON object."],
    [{ command: "  " }, "Terminal request has no command."],
    [{ command: "true", title: 42 }, "Terminal request title must be a string."],
    [{ command: "true", cwd: [] }, "Terminal request cwd must be a string."],
    [
      { id: "../../terminal-status/other", command: "true" },
      "Request id contains unsupported characters.",
    ],
  ];

  for (const [value, expectedError] of cases) {
    const request = validateTerminalRequest(value, "fallback", "/workspace");
    assert.equal(request.valid, false);
    assert.equal(request.error, expectedError);
  }
});

test("a request is moved only after a valid command was sent", () => {
  const valid = validateTerminalRequest({ command: "true" }, "request-1", "/workspace");
  const invalid = validateTerminalRequest({ command: "" }, "request-2", "/workspace");

  assert.equal(processedStatusFor(valid, false), null);
  assert.equal(processedStatusFor(invalid, true), null);
  assert.equal(processedStatusFor(valid, true), "started");
});
