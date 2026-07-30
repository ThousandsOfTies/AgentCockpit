const DEFAULT_TERMINAL_TITLE = "Gapless Agent Runtime";
const REQUEST_ID_PATTERN = /^[A-Za-z0-9][A-Za-z0-9._-]*$/;

function shellQuote(value) {
  return `'${String(value).replace(/'/g, "'\\''")}'`;
}

function terminalCommand(request, createdNew) {
  if (createdNew || !request.cwd) {
    return request.command;
  }
  return `cd ${shellQuote(request.cwd)} && ${request.command}`;
}

function validateTerminalRequest(value, fallbackId, fallbackCwd) {
  const fallbackRequestId = validRequestId(fallbackId)
    ? String(fallbackId)
    : "invalid-request";

  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return invalidRequest(fallbackRequestId, fallbackCwd, "Request must be a JSON object.");
  }

  const id = value.id === undefined || value.id === null || value.id === ""
    ? fallbackRequestId
    : String(value.id);
  if (!validRequestId(id)) {
    return invalidRequest(
      fallbackRequestId,
      fallbackCwd,
      "Request id contains unsupported characters."
    );
  }

  if (typeof value.command !== "string" || value.command.trim() === "") {
    return invalidRequest(id, fallbackCwd, "Terminal request has no command.");
  }

  if (value.title !== undefined && typeof value.title !== "string") {
    return invalidRequest(id, fallbackCwd, "Terminal request title must be a string.");
  }

  if (value.cwd !== undefined && typeof value.cwd !== "string") {
    return invalidRequest(id, fallbackCwd, "Terminal request cwd must be a string.");
  }

  return {
    valid: true,
    id,
    title: value.title || DEFAULT_TERMINAL_TITLE,
    command: value.command,
    cwd: value.cwd || fallbackCwd || "",
    error: null,
  };
}

function processedStatusFor(validation, commandSent) {
  if (!validation.valid || !commandSent) {
    return null;
  }
  return "started";
}

function invalidRequest(id, fallbackCwd, error) {
  return {
    valid: false,
    id,
    title: DEFAULT_TERMINAL_TITLE,
    command: "",
    cwd: fallbackCwd || "",
    error,
  };
}

function validRequestId(value) {
  return REQUEST_ID_PATTERN.test(String(value || ""));
}

module.exports = {
  processedStatusFor,
  shellQuote,
  terminalCommand,
  validateTerminalRequest,
};
