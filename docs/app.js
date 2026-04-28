window.APP_CONFIG = window.APP_CONFIG || {
  apiBaseUrl: "https://vocareum-prompt-api-379861060062.us-central1.run.app"
};

const form = document.getElementById("promptForm");
const promptInput = document.getElementById("promptInput");
const submitButton = document.getElementById("submitButton");
const copyButton = document.getElementById("copyButton");
const sourceNote = document.getElementById("sourceNote");
const statusPill = document.getElementById("statusPill");
const statusText = document.getElementById("statusText");
const outputBox = document.getElementById("outputBox");

function setStatus(text, tone = "neutral") {
  statusPill.textContent = text;
  statusPill.dataset.tone = tone;
}

async function loadMeta() {
  const response = await fetch(`${window.APP_CONFIG.apiBaseUrl}/api/meta`);
  if (!response.ok) {
    throw new Error("Failed to load source metadata.");
  }
  const meta = await response.json();
  sourceNote.textContent = meta.grounding_mode === "live"
    ? `Grounded in the live catalog doc. Last reviewed ${meta.source.last_reviewed}.`
    : "Using fallback source snapshot because live source access is unavailable.";
}

function formatError(detail) {
  if (typeof detail === "string") {
    return detail;
  }
  if (!detail || typeof detail !== "object") {
    return "Request failed.";
  }

  const lines = [];
  if (detail.message) {
    lines.push(detail.message);
  }
  if (Array.isArray(detail.missing) && detail.missing.length) {
    lines.push(`Need more detail: ${detail.missing.join("; ")}`);
  }
  if (detail.example) {
    lines.push(`Example: ${detail.example}`);
  }
  if (Array.isArray(detail.violations) && detail.violations.length) {
    lines.push(...detail.violations);
  }
  return lines.join("\n") || "Request failed.";
}

function setLoadingState(loading) {
  submitButton.disabled = loading;
  copyButton.disabled = loading;
  setStatus(loading ? "Running" : "Ready", loading ? "working" : "neutral");
}

async function runPrompt(event) {
  event.preventDefault();
  outputBox.textContent = "Running...";
  statusText.textContent = "Building a grounded response from the catalog.";
  setLoadingState(true);

  try {
    const response = await fetch(`${window.APP_CONFIG.apiBaseUrl}/api/generate`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        asset_type: "grounded-answer",
        objective: promptInput.value.trim(),
        product: "",
        audience: "",
        extra_constraints: ""
      })
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(formatError(payload.detail));
    }

    outputBox.textContent = payload.output;
    statusText.textContent = payload.grounding_mode === "live"
      ? `Ready. Grounded in live source material last reviewed ${payload.source_last_reviewed}.`
      : "Ready. Using fallback source snapshot.";
    setStatus("Ready", "success");
  } catch (error) {
    outputBox.textContent = `Error:\n${error.message}`;
    statusText.textContent = "The request did not run cleanly. Add more detail and try again.";
    setStatus("Needs detail", "error");
  } finally {
    if (statusPill.textContent === "Running") {
      setStatus("Ready");
    }
    submitButton.disabled = false;
    copyButton.disabled = false;
  }
}

async function copyOutput() {
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
}

form.addEventListener("submit", runPrompt);
copyButton.addEventListener("click", copyOutput);

loadMeta().catch((error) => {
  sourceNote.textContent = `Source status unavailable: ${error.message}`;
  outputBox.textContent = `Error:\n${error.message}`;
  statusText.textContent = "The page could not load source metadata.";
  setStatus("Offline", "error");
});
