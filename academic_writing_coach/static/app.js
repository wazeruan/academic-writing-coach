// Academic Writing Coach: a five-step daily challenge, graded by a local model.
"use strict";

const STEP_NAMES = ["Understand", "Plan", "Write", "Check", "Feedback"];
// `plan` and `draft` hold the live text; the server copy is updated by autosave.
const state = {
  data: null,
  step: 0,
  plan: "",
  draft: "",
  saveTimer: null,
  saveStatus: "Saved",
  busy: false,
  submitHint: "",
};

const $ = (id) => document.getElementById(id);

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (key === "class") node.className = value;
    else if (key === "text") node.textContent = value;
    else if (key.startsWith("on") && typeof value === "function") node.addEventListener(key.slice(2), value);
    else if (value !== false) node.setAttribute(key, value === true ? "" : value);
  }
  for (const child of children.flat()) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    method: options.body ? "POST" : "GET",
    headers: { "Content-Type": "application/json" },
    body: options.body ? JSON.stringify(options.body) : undefined,
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.error || `Request failed (${response.status})`);
  return payload;
}

function wordCount(text) {
  return text.trim() ? text.trim().split(/\s+/).length : 0;
}

function showNotice(message) {
  const notice = $("notice");
  notice.textContent = message || "";
  notice.hidden = !message;
}

function targetRange() {
  return state.data.challenge.word_range || [state.data.min_words, 300];
}

// Header -------------------------------------------------------------------

function renderHeader() {
  const { progress, level, levels, challenge, source, date } = state.data;
  $("stats").replaceChildren(
    el("span", { text: `🔥 ${progress.streak}-day streak` }),
    el("span", { text: `⭐ ${progress.total_xp} XP` }),
    el("span", { text: `✅ ${progress.days_completed} days` }),
  );
  $("level").replaceChildren(...levels.map((name) =>
    el("option", { value: name, selected: name === level, text: name[0].toUpperCase() + name.slice(1) })
  ));
  $("eyebrow").textContent = `Today's challenge · ${date}`;
  $("title").textContent = challenge.title;
  const [low, high] = targetRange();
  const scenario = (challenge.scenario || "writing").replaceAll("_", " ");
  $("meta").textContent = `${scenario} · target ${low}–${high} words`;
  showNotice(source === "template"
    ? "The local model is offline, so this challenge came from the built-in template. Start the LM Studio server to get AI challenges and feedback."
    : "");
}

function renderSteps() {
  const hasFeedback = Boolean(state.data.latest);
  $("steps").replaceChildren(...STEP_NAMES.map((name, index) => {
    const done = index < state.step || (index === 4 && hasFeedback);
    const classes = ["step-btn", index === state.step ? "active" : "", done ? "done" : ""].join(" ").trim();
    return el("button", {
      class: classes,
      type: "button",
      "aria-current": index === state.step ? "step" : false,
      onclick: () => goToStep(index),
    }, el("span", { class: "num", text: String(index + 1) }), name);
  }));
}

function goToStep(index) {
  if (index === 4 && !state.data.latest) return;
  state.step = index;
  render();
}

// Steps --------------------------------------------------------------------

function stepUnderstand(challenge) {
  return [
    el("h2", { text: "1. Understand the situation" }),
    el("p", { text: challenge.situation }),
    el("div", { class: "brief" }, el("strong", { text: "Your task" }), el("p", { text: challenge.task })),
    el("h2", { text: "Background facts to use" }),
    el("ul", { class: "list" }, challenge.background.map((fact) => el("li", { text: fact }))),
    el("h2", { text: "Key vocabulary", style: "margin-top:16px" }),
    el("div", { class: "vocab" }, (challenge.key_vocabulary || []).map((item) =>
      el("div", {}, el("strong", { text: item.term }), el("span", { text: item.meaning })))),
    el("div", { class: "row" },
      el("span", { class: "wc", text: "Read the task, then plan." }),
      el("button", { class: "btn", type: "button", onclick: () => goToStep(1) }, "Next: Plan")),
  ];
}

function stepPlan(challenge) {
  return [
    el("h2", { text: "2. Plan your structure" }),
    el("p", { class: "meta", text: "Outline the parts before you write. The teacher reads this too." }),
    el("ol", { class: "hints" }, challenge.plan_hints.map((hint) => el("li", { text: hint }))),
    el("textarea", {
      id: "plan",
      placeholder: "One line per paragraph or idea…",
      oninput: (event) => onEdit("plan", event.target.value),
    }, state.plan),
    el("div", { class: "row" },
      el("button", { class: "btn secondary", type: "button", onclick: () => goToStep(0) }, "Back"),
      el("button", { class: "btn", type: "button", onclick: () => goToStep(2) }, "Next: Write")),
  ];
}

function stepWrite(challenge) {
  const [low, high] = targetRange();
  const count = el("span", { class: "wc", id: "wc" });
  const writeNode = el("textarea", {
    id: "draft",
    class: "draft",
    placeholder: "Write your text here…",
    oninput: (event) => onEdit("draft", event.target.value),
  }, state.draft);
  return [
    el("h2", { text: "3. Write" }),
    el("p", { class: "meta", text: `Aim for ${low}–${high} words. Use the vocabulary and background facts.` }),
    writeNode,
    el("div", { class: "row" },
      count,
      el("span", { class: "saved", id: "saved", text: state.saveStatus }),
      el("button", { class: "btn", type: "button", onclick: () => goToStep(3) }, "Next: Check")),
    updateCount(count, low, high),
  ];
}

function updateCount(node, low, high) {
  const words = wordCount(state.draft);
  node.textContent = `${words} words (target ${low}–${high})`;
  node.classList.toggle("ok", words >= low && words <= high);
  return null;
}

function stepCheck(challenge) {
  const boxes = challenge.requirements.map((rule) =>
    el("label", { class: "check" }, el("input", { type: "checkbox" }), el("span", { text: rule })));
  return [
    el("h2", { text: "4. Check against the requirements" }),
    el("p", { class: "meta", text: "Tick each item you believe you met. The teacher checks them too." }),
    boxes,
    el("div", { class: "row" },
      el("span", { class: "wc", text: state.submitHint || `Minimum ${state.data.min_words} words to submit.` }),
      el("button", { class: "btn", type: "button", disabled: state.busy, onclick: submitDraft },
        state.busy ? "Grading…" : "Submit to teacher")),
    state.busy ? el("p", { class: "meta", text: "A local model can take a minute. Keep this tab open." }) : null,
  ];
}

function stepFeedback() {
  const latest = state.data.latest;
  if (!latest) {
    return [
      el("h2", { text: "5. Feedback" }),
      el("p", { text: "Submit your text in step 4 to see the teacher's feedback." }),
    ];
  }
  const fb = latest.feedback;
  const scoreRows = Object.entries(fb.scores).map(([key, value]) => {
    const label = key.replaceAll("_", " ");
    return el("div", { class: "score-row" },
      el("div", { text: `${label[0].toUpperCase()}${label.slice(1)}: ${value}/5` }),
      el("div", { class: "bar" }, el("div", { style: `width:${value * 20}%` })));
  });
  return [
    el("h2", { text: "5. Feedback" }),
    el("p", {}, el("strong", { text: `Overall ${latest.overall}/100` }), ` · +${latest.xp} XP`),
    el("div", { class: "score" }, scoreRows),
    fb.strengths.length ? el("div", {}, el("h2", { text: "What works" }),
      el("ul", { class: "list" }, fb.strengths.map((s) => el("li", { text: s })))) : null,
    fb.corrections.length ? el("div", {}, el("h2", { text: "Corrections" }), fb.corrections.map((c) =>
      el("div", { class: "correction" },
        el("span", { class: "old", text: c.original }), " → ", el("span", { class: "new", text: c.revised }),
        c.explanation ? el("p", { text: c.explanation }) : null))) : null,
    fb.improved_version ? el("div", {}, el("h2", { text: "Model version" }),
      el("div", { class: "improved", text: fb.improved_version })) : null,
    fb.next_focus ? el("p", {}, el("strong", { text: "Next focus: " }), fb.next_focus) : null,
    fb.mini_exercise ? el("div", { class: "brief" }, el("strong", { text: "Mini exercise" }),
      el("p", { text: fb.mini_exercise })) : null,
    el("div", { class: "row" },
      el("button", { class: "btn secondary", type: "button", onclick: () => goToStep(2) }, "Revise my draft")),
  ];
}

// Actions ------------------------------------------------------------------

function onEdit(field, value) {
  state[field] = value;
  state.submitHint = "";
  state.saveStatus = "Saving…";
  const saved = $("saved");
  if (saved) saved.textContent = state.saveStatus;
  const count = $("wc");
  if (count) {
    const [low, high] = targetRange();
    updateCount(count, low, high);
  }
  clearTimeout(state.saveTimer);
  state.saveTimer = setTimeout(saveDraft, 800);
}

async function saveDraft() {
  clearTimeout(state.saveTimer);
  try {
    await api("/api/draft", { method: "POST", body: { plan: state.plan, draft: state.draft } });
    state.saveStatus = "Saved";
  } catch (error) {
    state.saveStatus = "Not saved (server unreachable)";
  }
  const saved = $("saved");
  if (saved) saved.textContent = state.saveStatus;
}

async function submitDraft() {
  if (state.busy) return;
  const words = wordCount(state.draft);
  if (words < state.data.min_words) {
    state.submitHint = `Write at least ${state.data.min_words} words first (${words} now).`;
    render();
    return;
  }
  state.submitHint = "";
  state.busy = true;
  render();
  try {
    await saveDraft();
    const result = await api("/api/submit", { method: "POST", body: { plan: state.plan, draft: state.draft } });
    state.data.progress = result.progress;
    state.data.latest = { overall: result.overall, xp: result.xp, feedback: result.feedback };
    state.data.submissions.push({ id: result.submission_id, overall: result.overall, xp: result.xp });
    if (state.step === 3) state.step = 4; // Respect a step the user moved to while grading.
    showNotice("");
  } catch (error) {
    showNotice(error.message);
  } finally {
    state.busy = false;
    render();
  }
}

function render() {
  renderHeader();
  renderSteps();
  const challenge = state.data.challenge;
  const builders = [stepUnderstand, stepPlan, stepWrite, stepCheck, stepFeedback];
  $("panel").replaceChildren(...builders[state.step](challenge).flat().filter(Boolean));
}

async function loadToday() {
  state.data = await api("/api/today");
  state.plan = state.data.draft.plan;
  state.draft = state.data.draft.draft;
  state.step = state.draft ? 2 : 0;
  render();
}

async function checkHealth() {
  const pill = $("llm-status");
  try {
    const health = await api("/api/health");
    pill.textContent = health.online ? `Model online: ${health.model}` : "Model offline";
    pill.classList.toggle("online", health.online);
  } catch (error) {
    pill.textContent = "Server error";
  }
}

$("level").addEventListener("change", async (event) => {
  try {
    await saveDraft(); // Keep unsaved words before the page reloads today's challenge.
    await api("/api/level", { method: "POST", body: { level: event.target.value } });
    $("title").textContent = "Preparing today's challenge…";
    await loadToday();
  } catch (error) {
    showNotice(error.message);
  }
});

$("title").textContent = "Preparing today's challenge…";
loadToday().catch((error) => {
  $("title").textContent = "Could not load today's challenge";
  showNotice(error.message);
});
checkHealth();
