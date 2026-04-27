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
const assetType = document.getElementById("assetType");
const examplePattern = document.getElementById("examplePattern");
const audienceInput = document.getElementById("audienceInput");
const promptInput = document.getElementById("promptInput");
const constraintsInput = document.getElementById("constraintsInput");
const exampleLabel = document.getElementById("exampleLabel");
const exampleUseWhen = document.getElementById("exampleUseWhen");
const exampleSource = document.getElementById("exampleSource");
const presetButtons = Array.from(document.querySelectorAll(".preset-button"));

let meta = {
  deliverable_types: [],
  example_patterns: []
};

function setLog(lines) {
  logBox.textContent = lines.join("\n");
}

function currentExamples() {
  const selectedAsset = assetType.value;
  return meta.example_patterns.filter((item) => {
    return selectedAsset === "custom" || item.asset_types.includes(selectedAsset);
  });
}

function renderExampleOptions(preferredId) {
  const examples = currentExamples();
  examplePattern.innerHTML = "";

  const autoOption = document.createElement("option");
  autoOption.value = "";
  autoOption.textContent = "Auto-select best pattern";
  examplePattern.appendChild(autoOption);

  examples.forEach((item) => {
    const option = document.createElement("option");
    option.value = item.id;
    option.textContent = item.label;
    examplePattern.appendChild(option);
  });

  if (preferredId && examples.some((item) => item.id === preferredId)) {
    examplePattern.value = preferredId;
  } else {
    examplePattern.value = "";
  }

  renderExampleCard();
}

function renderExampleCard() {
  const selected = meta.example_patterns.find((item) => item.id === examplePattern.value);
  if (!selected) {
    exampleLabel.textContent = "Auto-select best pattern";
    exampleUseWhen.textContent = "The backend will pick the closest approved email or collateral pattern for this deliverable.";
    exampleSource.textContent = "Source: approved example library";
    return;
  }

  exampleLabel.textContent = selected.label;
  exampleUseWhen.textContent = selected.use_when;
  exampleSource.textContent = `Source: ${selected.source}`;
}

function renderDeliverableOptions() {
  assetType.innerHTML = "";
  meta.deliverable_types.forEach((item) => {
    const option = document.createElement("option");
    option.value = item.id;
    option.textContent = item.label;
    assetType.appendChild(option);
  });
  assetType.value = "outreach-email";
  renderExampleOptions("");
}

async function loadMeta() {
  setLog(["loading metadata..."]);
  const response = await fetch(`${window.APP_CONFIG.apiBaseUrl}/api/meta`);
  if (!response.ok) {
    throw new Error("Failed to load site metadata.");
  }

  meta = await response.json();
  modelName.textContent = meta.model;
  sourceDate.textContent = meta.source.last_reviewed;
  renderDeliverableOptions();

  setLog([
    "ready",
    `model: ${meta.model}`,
    `catalog: ${meta.source.last_reviewed}`,
    `patterns: ${meta.example_patterns.length}`
  ]);
}

assetType.addEventListener("change", () => {
  renderExampleOptions("");
});

examplePattern.addEventListener("change", () => {
  renderExampleCard();
});

presetButtons.forEach((button) => {
  button.addEventListener("click", () => {
    assetType.value = button.dataset.assetType || "custom";
    renderExampleOptions(button.dataset.examplePattern || "");
    promptInput.value = button.dataset.prompt || "";
    constraintsInput.value = button.dataset.constraints || "";
    audienceInput.focus();
  });
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const startedAt = performance.now();
  submitButton.disabled = true;
  submitButton.textContent = "Generating...";
  outputBox.textContent = "Generating...";
  setLog([
    "request started",
    `asset type: ${assetType.value}`,
    `example pattern: ${examplePattern.value || "auto"}`,
    `prompt chars: ${promptInput.value.trim().length}`,
    "calling backend..."
  ]);

  const body = {
    asset_type: assetType.value,
    audience: audienceInput.value.trim(),
    objective: promptInput.value.trim(),
    extra_constraints: constraintsInput.value.trim(),
    example_pattern: examplePattern.value
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
      `asset type: ${assetType.value}`,
      `example pattern: ${examplePattern.value || "auto"}`,
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
    submitButton.textContent = "Generate";
  }
});

copyButton.addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText(outputBox.textContent);
    copyButton.textContent = "Copied";
    setTimeout(() => {
      copyButton.textContent = "Copy output";
    }, 1200);
  } catch (_error) {
    copyButton.textContent = "Copy failed";
    setTimeout(() => {
      copyButton.textContent = "Copy output";
    }, 1200);
  }
});

loadMeta().catch((error) => {
  outputBox.textContent = `Error: ${error.message}`;
  setLog(["metadata load failed", `error: ${error.message}`]);
});
