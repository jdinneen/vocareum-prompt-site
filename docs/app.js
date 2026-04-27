window.APP_CONFIG = window.APP_CONFIG || {
  apiBaseUrl: "https://vocareum-prompt-api-379861060062.us-central1.run.app"
};

const form = document.getElementById("promptForm");
const submitButton = document.getElementById("submitButton");
const copyButton = document.getElementById("copyButton");
const outputBox = document.getElementById("outputBox");
const logBox = document.getElementById("logBox");
const modelName = document.getElementById("modelName");
const sourceDate = document.getElementById("sourceDate");

function setLog(lines) {
  logBox.textContent = lines.join("\n");
}

async function loadMeta() {
  setLog(["loading site metadata..."]);
  const response = await fetch(`${window.APP_CONFIG.apiBaseUrl}/api/meta`);
  if (!response.ok) {
    throw new Error("Failed to load site metadata.");
  }
  const payload = await response.json();
  modelName.textContent = payload.model;
  sourceDate.textContent = payload.source.last_reviewed;
  setLog([
    `ready`,
    `model: ${payload.model}`,
    `catalog: ${payload.source.last_reviewed}`
  ]);
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const startedAt = performance.now();
  const prompt = document.getElementById("promptInput").value.trim();
  submitButton.disabled = true;
  submitButton.textContent = "Executing...";
  outputBox.textContent = "Executing...";
  setLog([
    "request started",
    `prompt chars: ${prompt.length}`,
    "calling backend..."
  ]);

  const body = {
    asset_type: "custom",
    audience: "",
    objective: prompt,
    extra_constraints: ""
  };

  try {
    const response = await fetch(`${window.APP_CONFIG.apiBaseUrl}/api/generate`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(body)
    });

    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail || "Request failed.");
    }

    outputBox.textContent = payload.output;
    modelName.textContent = payload.model;
    sourceDate.textContent = payload.source_last_reviewed;
    setLog([
      "request complete",
      `request id: ${payload.request_id}`,
      `model: ${payload.model}`,
      `server duration: ${payload.duration_ms} ms`,
      `browser total: ${Math.round(performance.now() - startedAt)} ms`
    ]);
  } catch (error) {
    outputBox.textContent = `Error: ${error.message}`;
    setLog([
      "request failed",
      `error: ${error.message}`,
      `browser total: ${Math.round(performance.now() - startedAt)} ms`
    ]);
  } finally {
    submitButton.disabled = false;
    submitButton.textContent = "Execute";
  }
});

copyButton.addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText(outputBox.textContent);
    copyButton.textContent = "Copied";
    setTimeout(() => {
      copyButton.textContent = "Copy";
    }, 1200);
  } catch (_error) {
    copyButton.textContent = "Copy failed";
    setTimeout(() => {
      copyButton.textContent = "Copy";
    }, 1200);
  }
});

loadMeta().catch((error) => {
  outputBox.textContent = `Error: ${error.message}`;
  setLog([`metadata load failed`, `error: ${error.message}`]);
});
