window.APP_CONFIG = window.APP_CONFIG || {
  apiBaseUrl: "https://vocareum-prompt-api-379861060062.us-central1.run.app"
};

const form = document.getElementById("promptForm");
const submitButton = document.getElementById("submitButton");
const copyButton = document.getElementById("copyButton");
const outputBox = document.getElementById("outputBox");
const logBox = document.getElementById("logBox");
const modelName = document.getElementById("modelName");
const groundingMode = document.getElementById("groundingMode");
const sourceDate = document.getElementById("sourceDate");
const metaNote = document.getElementById("metaNote");
const assetType = document.getElementById("assetType");
const productSelect = document.getElementById("productSelect");
const audienceInput = document.getElementById("audienceInput");
const promptInput = document.getElementById("promptInput");
const constraintsInput = document.getElementById("constraintsInput");
const workflowLabel = document.getElementById("workflowLabel");
const workflowDescription = document.getElementById("workflowDescription");
const statusTitle = document.getElementById("statusTitle");
const statusBody = document.getElementById("statusBody");
const presetButtons = Array.from(document.querySelectorAll(".preset-button"));
const renderPanel = document.getElementById("renderPanel");
const renderFrame = document.getElementById("renderFrame");
const renderTitle = document.getElementById("renderTitle");
const openPreviewButton = document.getElementById("openPreviewButton");

let meta = {
  deliverable_types: [],
  products: [],
  grounding_warnings: []
};
let currentRenderUrl = "";

function setLog(lines) {
  logBox.textContent = lines.join("\n");
}

function clearRenderPreview() {
  if (currentRenderUrl) {
    URL.revokeObjectURL(currentRenderUrl);
    currentRenderUrl = "";
  }
  renderFrame.removeAttribute("src");
  renderTitle.textContent = "Rendered collateral";
  renderPanel.classList.add("hidden");
}

function setRenderPreview(renderedHtml, renderedTitleText) {
  clearRenderPreview();
  const blob = new Blob([renderedHtml], { type: "text/html" });
  currentRenderUrl = URL.createObjectURL(blob);
  renderFrame.src = currentRenderUrl;
  renderTitle.textContent = renderedTitleText || "Rendered collateral";
  renderPanel.classList.remove("hidden");
}

function renderDeliverableOptions() {
  assetType.innerHTML = "";
  meta.deliverable_types.forEach((item) => {
    const option = document.createElement("option");
    option.value = item.id;
    option.textContent = item.label;
    assetType.appendChild(option);
  });
  assetType.value = "outbound-email";
  renderWorkflowCard();
}

function renderWorkflowCard() {
  const selected = meta.deliverable_types.find((item) => item.id === assetType.value);
  if (!selected) {
    workflowLabel.textContent = "Workflow";
    workflowDescription.textContent = "";
    return;
  }
  workflowLabel.textContent = selected.label;
  workflowDescription.textContent = selected.description;
}

function renderSelectOptions(selectEl, values, placeholder) {
  selectEl.innerHTML = "";
  const emptyOption = document.createElement("option");
  emptyOption.value = "";
  emptyOption.textContent = placeholder;
  selectEl.appendChild(emptyOption);
  values.forEach((value) => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = value;
    selectEl.appendChild(option);
  });
}

function renderGroundingStatus(mode, warnings, source) {
  const isLive = mode === "live";
  groundingMode.textContent = isLive ? "live grounding" : "fallback grounding";
  statusTitle.textContent = isLive ? "Live doc grounding active" : "Fallback snapshot in use";
  if (warnings && warnings.length) {
    statusBody.textContent = warnings.join(" ");
  } else if (isLive) {
    statusBody.textContent = `Using the live catalog and linked approved materials from ${source.last_reviewed}.`;
  } else {
    statusBody.textContent = "Live sources are unavailable, so the app is using a local fallback snapshot.";
  }
  metaNote.textContent = isLive
    ? "Live catalog grounding with deterministic validation before output is returned."
    : "Fallback grounding is active. Generation still validates output, but live sources are currently unavailable.";
}

async function loadMeta() {
  setLog(["loading metadata..."]);
  const response = await fetch(`${window.APP_CONFIG.apiBaseUrl}/api/meta`);
  if (!response.ok) {
    throw new Error("Failed to load site metadata.");
  }

  meta = await response.json();
  modelName.textContent = meta.model;
  groundingMode.textContent = meta.grounding_mode;
  sourceDate.textContent = meta.source.last_reviewed;
  renderDeliverableOptions();
  renderSelectOptions(productSelect, meta.products, "Auto-detect product");
  renderGroundingStatus(meta.grounding_mode, meta.grounding_warnings, meta.source);

  setLog([
    "ready",
    `model: ${meta.model}`,
    `grounding: ${meta.grounding_mode}`,
    `catalog: ${meta.source.last_reviewed}`,
    `workflows: ${meta.deliverable_types.length}`
  ]);
}

assetType.addEventListener("change", () => {
  renderWorkflowCard();
});

presetButtons.forEach((button) => {
  button.addEventListener("click", () => {
    assetType.value = button.dataset.assetType || "outbound-email";
    renderWorkflowCard();
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
    `workflow: ${assetType.value}`,
    `product: ${productSelect.value || "auto"}`,
    `audience: ${audienceInput.value.trim() || "none"}`,
    `prompt chars: ${promptInput.value.trim().length}`,
    "calling backend..."
  ]);
  clearRenderPreview();

  const body = {
    asset_type: assetType.value,
    product: productSelect.value,
    audience: audienceInput.value.trim(),
    objective: promptInput.value.trim(),
    extra_constraints: constraintsInput.value.trim()
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
      const detail = payload.detail || {};
      const message = typeof detail === "string"
        ? detail
        : detail.message || "Request failed.";
      const violations = Array.isArray(detail.violations) ? detail.violations : [];
      throw new Error([message].concat(violations).join(" "));
    }

    outputBox.textContent = payload.output;
    renderGroundingStatus(payload.grounding_mode, payload.grounding_warnings, {
      last_reviewed: payload.source_last_reviewed
    });
    if (payload.rendered_html) {
      setRenderPreview(payload.rendered_html, payload.rendered_title);
    }
    modelName.textContent = payload.model;
    sourceDate.textContent = payload.source_last_reviewed;
    groundingMode.textContent = payload.grounding_mode;
    setLog([
      "request complete",
      `request id: ${payload.request_id}`,
      `workflow: ${assetType.value}`,
      `product: ${productSelect.value || "auto"}`,
      `grounding: ${payload.grounding_mode}`,
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

openPreviewButton.addEventListener("click", () => {
  if (!currentRenderUrl) {
    return;
  }
  window.open(currentRenderUrl, "_blank", "noopener,noreferrer");
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
