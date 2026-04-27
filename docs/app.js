window.APP_CONFIG = window.APP_CONFIG || {
  apiBaseUrl: "https://vocareum-prompt-api-379861060062.us-central1.run.app"
};

const form = document.getElementById("promptForm");
const submitButton = document.getElementById("submitButton");
const copyButton = document.getElementById("copyButton");
const outputBox = document.getElementById("outputBox");
const modelName = document.getElementById("modelName");
const sourceDate = document.getElementById("sourceDate");

async function loadMeta() {
  const response = await fetch(`${window.APP_CONFIG.apiBaseUrl}/api/meta`);
  if (!response.ok) {
    throw new Error("Failed to load site metadata.");
  }
  const payload = await response.json();
  modelName.textContent = payload.model;
  sourceDate.textContent = payload.source.last_reviewed;
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  submitButton.disabled = true;
  submitButton.textContent = "Generating...";
  outputBox.textContent = "Generating grounded output...";

  const body = {
    asset_type: document.getElementById("assetType").value,
    audience: document.getElementById("audience").value.trim(),
    objective: document.getElementById("objective").value.trim(),
    extra_constraints: document.getElementById("constraints").value.trim()
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
  } catch (error) {
    outputBox.textContent = `Error: ${error.message}`;
  } finally {
    submitButton.disabled = false;
    submitButton.textContent = "Generate";
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
});
