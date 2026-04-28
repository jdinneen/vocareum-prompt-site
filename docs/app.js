window.APP_CONFIG = window.APP_CONFIG || {
  apiBaseUrl: "https://vocareum-prompt-api-379861060062.us-central1.run.app"
};

function ensureCurrentMarkup() {
  const hasCurrentShell = document.getElementById("sourceNote")
    && document.getElementById("statusPill")
    && document.getElementById("promptInput");
  if (hasCurrentShell) {
    return;
  }

  const shell = document.querySelector(".page-shell") || document.body;
  shell.innerHTML = `
    <section class="hero">
      <p class="eyebrow">Vocareum Grounded Assistant</p>
      <h1>Ask for anything grounded in the catalog.</h1>
      <p class="lede">Ask a question, request copy, or paste a rough note. The response stays inside supported Vocareum source material.</p>
      <p id="sourceNote" class="source-note">Loading source status...</p>
    </section>

    <section class="workspace">
      <form id="promptForm" class="prompt-panel">
        <label class="field" for="promptInput">
          <span>Your prompt</span>
          <textarea
            id="promptInput"
            name="promptInput"
            rows="12"
            placeholder="Example: Explain AI Gateway for a university CIO in three short paragraphs, focusing on governed AI access for students and faculty."
            required
          ></textarea>
        </label>

        <div class="action-row">
          <button id="submitButton" class="primary-button" type="submit">Ask</button>
          <button id="copyButton" class="secondary-button" type="button">Copy</button>
        </div>
      </form>

      <section class="response-panel">
        <div class="response-head">
          <p class="section-label">Response</p>
          <span id="statusPill" class="status-pill">Ready</span>
        </div>
        <p id="statusText" class="status-text">Enter a prompt and run it.</p>
        <pre id="outputBox" class="output-box">Your grounded response will appear here.</pre>
      </section>
    </section>
  `;
}

ensureCurrentMarkup();

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
