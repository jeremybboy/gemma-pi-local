"use strict";

const MAX_FILE_BYTES = 8 * 1024 * 1024;
const MAX_HISTORY_MESSAGES = 12;

const state = {
  messages: [],
  pendingImage: null,
  pendingAudio: null,
  busy: false,
};

const elements = {
  messages: document.querySelector("#messages"),
  welcome: document.querySelector("#welcome"),
  composer: document.querySelector("#composer"),
  prompt: document.querySelector("#prompt-input"),
  send: document.querySelector("#send-button"),
  reset: document.querySelector("#reset-button"),
  imageButton: document.querySelector("#image-button"),
  audioButton: document.querySelector("#audio-button"),
  imageInput: document.querySelector("#image-input"),
  audioInput: document.querySelector("#audio-input"),
  pending: document.querySelector("#pending"),
  model: document.querySelector("#model-select"),
  temperatureInput: document.querySelector("#temperature-input"),
  tokensInput: document.querySelector("#tokens-input"),
  runtimeState: document.querySelector("#runtime-state"),
  runtimeLabel: document.querySelector("#runtime-label"),
  temperature: document.querySelector("#temperature"),
  memory: document.querySelector("#memory"),
  throttling: document.querySelector("#throttling"),
};

function formatBytes(bytes) {
  if (!Number.isFinite(bytes)) return "—";
  const units = ["B", "KB", "MB", "GB"];
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${value.toFixed(unit >= 2 ? 1 : 0)} ${units[unit]}`;
}

function readAsDataURL(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(reader.error || new Error("Could not read file"));
    reader.readAsDataURL(file);
  });
}

function assertFileSize(file) {
  if (file.size > MAX_FILE_BYTES) {
    throw new Error("Files must be 8 MB or smaller in V0.");
  }
}

function setBusy(busy) {
  state.busy = busy;
  elements.send.disabled = busy;
  elements.imageButton.disabled = busy;
  elements.audioButton.disabled = busy;
  elements.reset.disabled = busy;
  elements.send.querySelector("span").textContent = busy ? "Thinking" : "Send";
}

function resizePrompt() {
  elements.prompt.style.height = "auto";
  elements.prompt.style.height = `${Math.min(elements.prompt.scrollHeight, 180)}px`;
}

function renderPending() {
  elements.pending.replaceChildren();
  const attachments = [
    state.pendingImage && { type: "image", ...state.pendingImage },
    state.pendingAudio && { type: "audio", ...state.pendingAudio },
  ].filter(Boolean);
  elements.pending.hidden = attachments.length === 0;

  for (const attachment of attachments) {
    const item = document.createElement("div");
    item.className = "pending-item";
    if (attachment.type === "image") {
      const image = document.createElement("img");
      image.src = attachment.dataUrl;
      image.alt = "Selected image preview";
      item.append(image);
    }
    const meta = document.createElement("div");
    meta.className = "pending-meta";
    const name = document.createElement("strong");
    name.textContent = attachment.file.name;
    const size = document.createElement("small");
    size.textContent = `${attachment.type} · ${formatBytes(attachment.file.size)}`;
    meta.append(name, size);
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "remove-attachment";
    remove.setAttribute("aria-label", `Remove ${attachment.type}`);
    remove.textContent = "×";
    remove.addEventListener("click", () => {
      if (attachment.type === "image") state.pendingImage = null;
      if (attachment.type === "audio") state.pendingAudio = null;
      renderPending();
    });
    item.append(meta, remove);
    elements.pending.append(item);
  }
}

function createMessage(role, text, media = {}, isError = false) {
  elements.welcome?.remove();
  const article = document.createElement("article");
  article.className = `message ${role}${isError ? " error" : ""}`;

  const avatar = document.createElement("div");
  avatar.className = "message-avatar";
  avatar.textContent = role === "user" ? "YOU" : "G";

  const body = document.createElement("div");
  body.className = "message-body";
  const label = document.createElement("div");
  label.className = "message-role";
  label.textContent = role === "user" ? "You" : "Gemma Pi Local";

  const mediaContainer = document.createElement("div");
  mediaContainer.className = "message-media";
  if (media.imageUrl) {
    const image = document.createElement("img");
    image.src = media.imageUrl;
    image.alt = media.imageName || "Attached image";
    mediaContainer.append(image);
  }
  if (media.audioUrl) {
    const audio = document.createElement("audio");
    audio.src = media.audioUrl;
    audio.controls = true;
    audio.preload = "metadata";
    mediaContainer.append(audio);
  }

  const content = document.createElement("div");
  content.className = "message-text";
  content.textContent = text;
  body.append(label);
  if (mediaContainer.childNodes.length) body.append(mediaContainer);
  body.append(content);
  article.append(avatar, body);
  elements.messages.append(article);
  elements.messages.scrollTop = elements.messages.scrollHeight;
  return content;
}

function trimHistory() {
  while (state.messages.length > MAX_HISTORY_MESSAGES) {
    state.messages.splice(0, Math.min(2, state.messages.length));
  }
}

async function parseEventStream(response, output) {
  if (!response.body) throw new Error("Streaming is unavailable in this browser.");
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let completeText = "";

  while (true) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
    const events = buffer.split(/\r?\n\r?\n/);
    buffer = events.pop() || "";
    for (const event of events) {
      for (const line of event.split(/\r?\n/)) {
        if (!line.startsWith("data:")) continue;
        const data = line.slice(5).trim();
        if (!data || data === "[DONE]") continue;
        let payload;
        try {
          payload = JSON.parse(data);
        } catch {
          continue;
        }
        if (payload.error) {
          throw new Error(payload.error);
        }
        const delta = payload.choices?.[0]?.delta?.content;
        if (typeof delta === "string") {
          completeText += delta;
          output.textContent = completeText;
          elements.messages.scrollTop = elements.messages.scrollHeight;
        }
      }
    }
    if (done) break;
  }
  return completeText;
}

async function sendMessage(event) {
  event.preventDefault();
  if (state.busy) return;

  const typedText = elements.prompt.value.trim();
  if (!typedText && !state.pendingImage && !state.pendingAudio) return;
  const promptText = typedText || "Describe the attached media.";
  const parts = [];
  const displayMedia = {};

  // LiteRT-LM receives media before the text instruction for reliable grounding.
  if (state.pendingImage) {
    parts.push({
      type: "image_url",
      image_url: { url: state.pendingImage.dataUrl },
    });
    displayMedia.imageUrl = state.pendingImage.dataUrl;
    displayMedia.imageName = state.pendingImage.file.name;
  }
  if (state.pendingAudio) {
    parts.push({
      type: "input_audio",
      input_audio: { data: state.pendingAudio.base64, format: "wav" },
    });
    displayMedia.audioUrl = state.pendingAudio.dataUrl;
  }
  parts.push({ type: "text", text: promptText });

  state.messages.push({ role: "user", content: parts });
  trimHistory();
  createMessage("user", promptText, displayMedia);
  elements.prompt.value = "";
  resizePrompt();
  state.pendingImage = null;
  state.pendingAudio = null;
  renderPending();

  const output = createMessage("assistant", "");
  setBusy(true);
  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        model: elements.model.value,
        messages: state.messages,
        temperature: Number(elements.temperatureInput.value),
        max_tokens: Number(elements.tokensInput.value),
      }),
    });
    if (!response.ok) {
      const payload = await response.json().catch(() => ({}));
      throw new Error(payload.detail || payload.error || `Request failed (${response.status})`);
    }
    const answer = await parseEventStream(response, output);
    const finalAnswer = answer || "The model returned no text.";
    output.textContent = finalAnswer;
    state.messages.push({ role: "assistant", content: finalAnswer });
    trimHistory();
  } catch (error) {
    output.closest(".message").classList.add("error");
    output.textContent = error instanceof Error ? error.message : String(error);
  } finally {
    setBusy(false);
    elements.prompt.focus();
    void refreshStatus();
  }
}

async function selectImage(file) {
  if (!file) return;
  const allowed = ["image/png", "image/jpeg", "image/webp"];
  if (!allowed.includes(file.type)) throw new Error("Choose a PNG, JPEG, or WebP image.");
  assertFileSize(file);
  state.pendingImage = { file, dataUrl: await readAsDataURL(file) };
  renderPending();
}

async function selectAudio(file) {
  if (!file) return;
  if (!file.name.toLowerCase().endsWith(".wav")) throw new Error("V0 accepts WAV audio only.");
  assertFileSize(file);
  const dataUrl = await readAsDataURL(file);
  state.pendingAudio = { file, dataUrl, base64: dataUrl.split(",", 2)[1] };
  renderPending();
}

function reportSelectionError(error) {
  createMessage("assistant", error instanceof Error ? error.message : String(error), {}, true);
}

function resetChat() {
  state.messages = [];
  state.pendingImage = null;
  state.pendingAudio = null;
  elements.prompt.value = "";
  resizePrompt();
  elements.messages.replaceChildren();
  const welcome = document.createElement("div");
  welcome.className = "welcome";
  welcome.id = "welcome";
  const text = document.createElement("p");
  text.textContent = "New in-memory session. Attach media or ask a question.";
  welcome.append(text);
  elements.messages.append(welcome);
  elements.welcome = welcome;
  renderPending();
  elements.prompt.focus();
}

function setModelOptions(models, fallback) {
  const ids = models
    .map((model) => (typeof model?.id === "string" ? model.id : null))
    .filter(Boolean);
  if (!ids.length) ids.push(fallback);
  const previous = elements.model.value;
  elements.model.replaceChildren();
  for (const id of ids) {
    const option = document.createElement("option");
    option.value = id;
    option.textContent = id;
    elements.model.append(option);
  }
  elements.model.value = ids.includes(previous) ? previous : ids.includes(fallback) ? fallback : ids[0];
}

async function refreshStatus() {
  try {
    const response = await fetch("/api/status", { cache: "no-store" });
    if (!response.ok) throw new Error(`Status failed (${response.status})`);
    const payload = await response.json();
    const litertReady = Boolean(payload.litert?.ok);
    elements.runtimeState.dataset.state = litertReady ? "ready" : "offline";
    elements.runtimeLabel.textContent = litertReady ? "Model server ready" : "Model server offline";
    setModelOptions(payload.litert?.models || [], payload.default_model || "gemma4-e4b");
    const system = payload.system || {};
    elements.temperature.textContent = Number.isFinite(system.temperature_c)
      ? `${system.temperature_c.toFixed(1)} °C`
      : "Unavailable";
    const available = system.memory?.available_bytes;
    const total = system.memory?.total_bytes;
    elements.memory.textContent = Number.isFinite(available)
      ? `${formatBytes(available)} / ${formatBytes(total)}`
      : "Unavailable";
    const throttle = system.throttled?.active_or_historical;
    elements.throttling.textContent = throttle === false ? "None" : throttle === true ? "Detected" : "Unavailable";
    elements.throttling.classList.toggle("warning", throttle === true);
  } catch {
    elements.runtimeState.dataset.state = "offline";
    elements.runtimeLabel.textContent = "App status unavailable";
  }
}

elements.composer.addEventListener("submit", sendMessage);
elements.prompt.addEventListener("input", resizePrompt);
elements.prompt.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    elements.composer.requestSubmit();
  }
});
elements.imageButton.addEventListener("click", () => elements.imageInput.click());
elements.audioButton.addEventListener("click", () => elements.audioInput.click());
elements.imageInput.addEventListener("change", () => {
  selectImage(elements.imageInput.files?.[0]).catch(reportSelectionError);
  elements.imageInput.value = "";
});
elements.audioInput.addEventListener("change", () => {
  selectAudio(elements.audioInput.files?.[0]).catch(reportSelectionError);
  elements.audioInput.value = "";
});
elements.reset.addEventListener("click", resetChat);

document.querySelectorAll("[data-prompt]").forEach((button) => {
  button.addEventListener("click", () => {
    elements.prompt.value = button.dataset.prompt || "";
    resizePrompt();
    elements.prompt.focus();
  });
});
document.querySelectorAll("[data-action]").forEach((button) => {
  button.addEventListener("click", () => {
    if (button.dataset.action === "image") elements.imageInput.click();
    if (button.dataset.action === "audio") elements.audioInput.click();
  });
});

void refreshStatus();
window.setInterval(refreshStatus, 15_000);
