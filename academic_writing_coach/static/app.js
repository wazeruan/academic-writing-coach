// Academic Writing Coach: a Learn course of ordered units, plus a daily challenge. Graded by a local model.
"use strict";

// The question stays on the left at all times. The work on the right moves through these four tabs.
const STEP_NAMES = ["Plan", "Write", "Check", "Feedback"];
const PLAN = 0;
const WRITE = 1;
const CHECK = 2;
const FEEDBACK = 3;
const MIN_WORDS = 30; // Matches the server's minimum for a submission.
// `plan` and `draft` hold the live text; the server copy is updated by autosave.
const state = {
  view: "today",
  data: null,
  step: PLAN,
  plan: "",
  draft: "",
  saveTimer: null,
  saveStatus: "Saved",
  busy: false,
  submitHint: "",
  learn: null,       // { overview } from /api/learn
  unit: null,        // unit detail from /api/learn/unit
  practice: null,    // { task, text, result } for the open unit, held in memory
  practiceLoading: null,  // id of the unit whose exercise the model is writing, if any
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

function capitalise(text) {
  return text ? text[0].toUpperCase() + text.slice(1) : text;
}

// Views ---------------------------------------------------------------------

function setView(view) {
  state.view = view;
  for (const button of document.querySelectorAll(".tab")) {
    const active = button.dataset.view === view;
    button.classList.toggle("active", active);
    button.setAttribute("aria-selected", String(active));
  }
  $("today-view").hidden = view !== "today";
  $("learn-view").hidden = view !== "learn";
  if (view === "learn") loadLearn();
  else render();
}

// Header and daily view ----------------------------------------------------

function targetRange() {
  return state.data.challenge.word_range || [state.data.min_words, 300];
}

function renderHeader() {
  const { progress, level, levels, challenge, source, date, focus } = state.data;
  $("stats").replaceChildren(
    el("span", { text: `🔥 ${progress.streak}-day streak` }),
    el("span", { text: `⭐ ${progress.total_xp} XP` }),
    el("span", { text: `📘 ${progress.units_completed}/${progress.units_total} units` }),
  );
  $("level").replaceChildren(...levels.map((name) =>
    el("option", { value: name, selected: name === level, text: capitalise(name) })
  ));
  $("eyebrow").textContent = `Focus: ${focus.title}`;
  $("title").textContent = challenge.title;
  showNotice(source === "template"
    ? "The local model is offline, so this challenge came from the built-in template. Start the LM Studio server to get AI challenges and feedback."
    : "");
}

// The question: always visible on the left, so the task is in view while you plan and write.
function renderQuestion(challenge) {
  const [low, high] = targetRange();
  $("question-body").replaceChildren(
    el("p", { class: "q-task", text: challenge.task }),
    el("p", { class: "q-target", text: `${low}–${high} words` }),
    el("h3", { text: "Requirements" }),
    el("ul", { class: "q-list" }, challenge.requirements.map((rule) => el("li", { text: rule }))),
    el("h3", { text: "Facts to use" }),
    el("ul", { class: "q-list" }, challenge.background.map((fact) => el("li", { text: fact }))),
    el("h3", { text: "Vocabulary" }),
    el("div", { class: "q-chips" }, (challenge.key_vocabulary || []).map((item) =>
      el("span", { title: item.meaning, text: item.term }))),
  );
}

function renderSteps() {
  const hasFeedback = Boolean(state.data.latest);
  $("steps").replaceChildren(...STEP_NAMES.map((name, index) => {
    const done = index < state.step || (index === FEEDBACK && hasFeedback);
    const classes = ["step-btn", index === state.step ? "active" : "", done ? "done" : ""].join(" ").trim();
    return el("button", {
      class: classes,
      type: "button",
      disabled: index === FEEDBACK && !hasFeedback,
      "aria-current": index === state.step ? "step" : false,
      onclick: () => goToStep(index),
    }, el("span", { class: "num", text: String(index + 1) }), el("span", { class: "label", text: name }));
  }));
}

function goToStep(index) {
  if (index === FEEDBACK && !state.data.latest) return;
  state.step = index;
  render();
  // On desktop, put the cursor in the text box so you can type straight away.
  // Phones skip this, so the on-screen keyboard does not pop up on every tab change.
  const box = $("draft") || $("plan");
  if (box && window.matchMedia("(min-width: 900px)").matches) {
    box.focus();
    box.setSelectionRange(box.value.length, box.value.length);
  }
}

// Shortcut label for the platform: ⌘ on macOS, Ctrl elsewhere.
const MOD_KEY = /Mac|iPhone|iPad/.test(navigator.platform) ? "⌘" : "Ctrl";

function primaryAction(label, onclick, { disabled = false } = {}) {
  return el("div", { class: "actions" },
    el("kbd", { class: "kbd-hint", title: "Keyboard shortcut", text: `${MOD_KEY} ↵` }),
    el("button", { class: "btn", type: "button", disabled, onclick }, label));
}

function stepPlan(challenge) {
  return [
    el("ol", { class: "hints" }, challenge.plan_hints.map((hint) => el("li", { text: hint }))),
    el("textarea", {
      id: "plan",
      class: "plan",
      placeholder: "One line per paragraph or idea…",
      oninput: (event) => onEdit("plan", event.target.value),
    }, state.plan),
    el("div", { class: "row" },
      el("span", { class: "saved", id: "saved", text: state.saveStatus }),
      primaryAction("Next: Write", () => goToStep(WRITE))),
  ];
}

// While writing, a side rail keeps your plan and the focus unit's checklist in view.
function writingRail() {
  const focus = state.data.focus;
  return el("aside", { class: "rail", "aria-label": "Plan and focus" },
    el("h3", { text: "Your plan" }),
    state.plan.trim()
      ? el("p", { class: "rail-plan", text: state.plan })
      : el("p", { class: "meta", text: "No plan yet. Add one in the Plan tab." }),
    el("h3", { text: `Focus: ${focus.title}` }),
    el("ul", { class: "q-list" }, (focus.checklist || []).map((item) => el("li", { text: item }))));
}

function stepWrite() {
  const [low, high] = targetRange();
  const count = el("span", { class: "wc", id: "wc" });
  const meter = el("div", { class: "meter", id: "meter" }, el("div"));
  const writeNode = el("textarea", {
    id: "draft",
    class: "draft",
    placeholder: "Write your text here…",
    spellcheck: "true",
    oninput: (event) => onEdit("draft", event.target.value),
  }, state.draft);
  return [
    el("div", { class: "write-grid" }, el("div", { class: "editor-col" }, writeNode), writingRail()),
    el("div", { class: "row" },
      el("div", { class: "footer-left" },
        count, meter, el("span", { class: "saved", id: "saved", text: state.saveStatus })),
      primaryAction("Next: Check", () => goToStep(CHECK))),
    updateCount(count, low, high, meter),
  ];
}

// Shows words against the target range, with a thin progress bar that turns green inside it.
function updateCount(node, low, high, meter = $("meter")) {
  const words = wordCount(state.draft);
  const inRange = words >= low && words <= high;
  node.textContent = `${words} / ${low}–${high} words`;
  node.classList.toggle("ok", inRange);
  if (meter) {
    meter.classList.toggle("ok", inRange);
    meter.firstChild.style.width = high > 0 ? `${Math.min(100, (words / high) * 100)}%` : "0%";
  }
  return null;
}

function stepCheck(challenge) {
  const boxes = challenge.requirements.map((rule) =>
    el("label", { class: "check" }, el("input", { type: "checkbox" }), el("span", { text: rule })));
  return [
    el("h2", { text: "Did you meet each requirement?" }),
    boxes,
    el("div", { class: "row" },
      el("span", { class: "wc", text: state.submitHint || `Minimum ${state.data.min_words} words to submit.` }),
      primaryAction(state.busy ? "Grading…" : "Submit to teacher", submitDraft, { disabled: state.busy })),
    state.busy ? loadingNote("The teacher is grading your text. This usually takes about a minute.") : null,
  ];
}

function stepFeedback() {
  const latest = state.data.latest;
  if (!latest) {
    return [
      el("h2", { text: "Feedback" }),
      el("p", { text: "Submit your text in the Check tab to see the teacher's feedback." }),
    ];
  }
  return [
    feedbackNodes(latest),
    el("div", { class: "row" },
      el("button", { class: "btn secondary", type: "button", onclick: () => goToStep(WRITE) }, "Revise my draft")),
  ];
}

// Feedback, shared by daily and Learn practice. `result` has overall, xp and feedback.
function feedbackNodes(result) {
  const fb = result.feedback;
  const scoreRows = Object.entries(fb.scores).map(([key, value]) => {
    const label = key.replaceAll("_", " ");
    return el("div", { class: "score-row" },
      el("div", { text: `${capitalise(label)}: ${value}/5` }),
      el("div", { class: "bar" }, el("div", { style: `width:${value * 20}%` })));
  });
  // Two columns on wide screens: the verdict on the left, the detailed fixes on the right.
  const verdict = el("div", { class: "fb-col" },
    el("div", { class: "score-head" },
      el("span", { class: "big", text: String(result.overall) }),
      el("span", { class: "of", text: `/ 100 · +${result.xp} XP` })),
    el("div", { class: "score" }, scoreRows),
    fb.next_focus ? el("p", { class: "brief" }, el("strong", { text: "Next focus: " }), fb.next_focus) : null,
    // The teacher's check of each requirement. Older feedback saved before this existed has none.
    (fb.requirements_met || []).length ? el("div", { class: "fb-section" }, el("h2", { text: "Requirements" }),
      el("ul", { class: "req-list" }, fb.requirements_met.map((r) =>
        el("li", { class: r.met ? "met" : "missed" },
          el("span", { class: "mark", text: r.met ? "✓" : "✗" }),
          el("span", {}, el("strong", { text: r.requirement }), r.note ? ` ${r.note}` : ""))))) : null,
    fb.strengths.length ? el("div", { class: "fb-section" }, el("h2", { text: "What works" }),
      el("ul", { class: "list" }, fb.strengths.map((s) => el("li", { text: s })))) : null,
  );
  const fixes = el("div", { class: "fb-col" },
    fb.corrections.length ? el("div", {}, el("h2", { text: "Corrections" }), fb.corrections.map((c) =>
      el("div", { class: "correction" },
        el("span", { class: "old", text: c.original }), " → ", el("span", { class: "new", text: c.revised }),
        c.explanation ? el("p", { text: c.explanation }) : null))) : null,
    fb.mini_exercise ? el("div", { class: "brief" }, el("strong", { text: "Mini exercise: " }), fb.mini_exercise) : null,
    fb.improved_version ? el("div", { class: "fb-section" }, el("h2", { text: "Model version" }),
      el("div", { class: "improved", text: fb.improved_version })) : null,
  );
  return el("div", { class: "fb-grid" }, verdict, fixes);
}

// Daily actions -------------------------------------------------------------

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
    if (state.step === CHECK) state.step = FEEDBACK; // Respect a tab the user moved to while grading.
    showNotice(result.unit_passed ? "Today's writing passed the focus unit. It is marked complete in Learn." : "");
  } catch (error) {
    showNotice(error.message);
  } finally {
    state.busy = false;
    render();
  }
}

function renderDaily() {
  renderHeader();
  renderSteps();
  const challenge = state.data.challenge;
  renderQuestion(challenge);
  const builders = [stepPlan, stepWrite, stepCheck, stepFeedback];
  $("panel").replaceChildren(...builders[state.step](challenge).flat().filter(Boolean));
}

// Learn view ----------------------------------------------------------------

async function loadLearn() {
  $("learn-panel").replaceChildren(el("p", { class: "meta", text: "Loading units…" }));
  try {
    state.learn = await api("/api/learn");
    if (state.unit) await openUnit(state.unit.id, { silent: true });
    else renderLearn();
  } catch (error) {
    $("learn-panel").replaceChildren(el("p", { class: "error", text: error.message }));
  }
}

function renderLearn() {
  if (state.unit) return renderUnit();
  const { units, completed, total, pass_score } = state.learn;
  const cards = units.map((unit) => {
    const badge = { done: "Complete", current: "Focus now", locked: "Locked" }[unit.status];
    const score = unit.best_overall === null ? "" : ` · best ${unit.best_overall}/100`;
    return el("button", {
      class: `unit-card ${unit.status}`,
      type: "button",
      disabled: unit.status === "locked",
      onclick: () => openUnit(unit.id),
    },
      el("span", { class: "unit-top" }, el("span", { class: "unit-num", text: String(unit.index + 1) }),
        el("strong", { text: unit.title }), el("span", { class: "badge", text: badge })),
      el("span", { class: "meta unit-skill", text: unit.skill + score }));
  });
  $("learn-panel").replaceChildren(
    el("div", { class: "learn-head" },
      el("h2", { text: `${completed} of ${total} units complete` }),
      el("p", { class: "meta", text: `Units unlock in order. Score ${pass_score}/100 or more on a practice to pass. Today's challenge follows the current unit.` })),
    el("div", { class: "unit-grid" }, cards),
  );
}

async function openUnit(unitId, options = {}) {
  try {
    state.unit = await api(`/api/learn/unit?id=${encodeURIComponent(unitId)}`);
    if (!options.silent) state.practice = null;
    renderLearn();
  } catch (error) {
    showNotice(error.message);
  }
}

function closeUnit() {
  state.unit = null;
  state.practice = null;
  loadLearn();
}

function renderUnit() {
  const unit = state.unit;
  const back = el("button", { class: "btn secondary", type: "button", onclick: closeUnit }, "← All units");
  const lesson = [
    el("p", { class: "eyebrow", text: `Unit ${unit.index + 1}` }),
    el("h1", { text: unit.title }),
    el("p", { text: unit.skill }),
    el("h2", { text: "The rule" }),
    el("p", { text: unit.explanation }),
    el("div", { class: "compare" },
      el("div", { class: "weak" }, el("strong", { text: "Weaker" }), el("p", { text: unit.weak })),
      el("div", { class: "strong" }, el("strong", { text: "Stronger" }), el("p", { text: unit.strong }))),
    el("p", { class: "meta", text: unit.why_it_works }),
    el("h2", { text: "Checklist" }),
    el("ul", { class: "list" }, unit.checklist.map((item) => el("li", { text: item }))),
  ];
  const practiceSection = unit.status === "done" && !state.practice
    ? el("p", { class: "meta", text: `Completed. Best score ${unit.best_overall}/100. You can practise again below.` })
    : null;
  const loadingHere = state.practiceLoading === unit.id;
  const practice = state.practice
    ? renderPractice(unit)
    : [
      loadingHere
        ? loadingNote("The local model is writing a new exercise. This usually takes 10–30 seconds.")
        : el("p", { class: "meta", text: "Start a practice to get a short exercise on this unit's skill." }),
      el("div", { class: "row" },
        el("span", { class: "wc", text: `Pass with ${unit.pass_score}/100 or more.` }),
        el("button", { class: "btn", type: "button", disabled: loadingHere, onclick: startPractice },
          loadingHere ? "Preparing…" : "Start practice")),
    ];
  // Lesson on the left, practice on the right, so the rule stays in view while you write.
  $("learn-panel").replaceChildren(
    el("div", { class: "unit-layout" },
      el("div", { class: "card scroll" }, back, ...lesson, practiceSection),
      el("div", { class: "card scroll" }, el("h2", { text: "Practice" }), practice)),
  );
}

async function startPractice() {
  const unitId = state.unit.id;
  if (state.practiceLoading === unitId) return;
  state.practiceLoading = unitId;
  renderUnit();
  // The reply only counts if you are still on the same unit; otherwise it is dropped.
  const stillHere = () => state.view === "learn" && state.unit && state.unit.id === unitId;
  try {
    const result = await api("/api/practice/start", { method: "POST", body: { unit_id: unitId } });
    if (stillHere()) {
      state.practice = { task: result.task, source: result.source, text: "", result: null, busy: false };
    }
  } catch (error) {
    if (stillHere()) showNotice(error.message);
  } finally {
    if (state.practiceLoading === unitId) state.practiceLoading = null;
    if (stillHere()) renderUnit();
  }
}

// A spinner with a live seconds counter, so a slow local model visibly shows it is working.
function loadingNote(text) {
  const seconds = el("span", { class: "elapsed", text: "0 s" });
  const node = el("p", { class: "loading", role: "status" },
    el("span", { class: "spinner", "aria-hidden": "true" }), el("span", { text }), seconds);
  const started = Date.now();
  let attached = false;
  const timer = setInterval(() => {
    if (node.isConnected) attached = true;
    // Stop once the note is replaced, or if it was never shown at all.
    if ((attached && !node.isConnected) || (!attached && Date.now() - started > 5000)) {
      clearInterval(timer);
      return;
    }
    seconds.textContent = `${Math.round((Date.now() - started) / 1000)} s`;
  }, 1000);
  return node;
}

function renderPractice(unit) {
  const practice = state.practice;
  const textarea = el("textarea", {
    class: "draft",
    placeholder: "Write your answer here…",
    oninput: (event) => { practice.text = event.target.value; updatePracticeCount(); },
  }, practice.text);
  const hint = el("span", { class: "wc", id: "practice-count" });
  const children = [
    practice.source === "template" ? el("p", { class: "notice", text: "Offline exercise from the built-in set; start the local model for new ones." }) : null,
    el("div", { class: "brief" }, el("strong", { text: "Exercise" }), el("p", { text: practice.task })),
    textarea,
    el("div", { class: "row" }, hint,
      el("button", { class: "btn", type: "button", disabled: practice.busy, onclick: submitPractice },
        practice.busy ? "Grading…" : "Submit practice")),
    practice.busy ? loadingNote("The teacher is grading your answer. This usually takes about a minute.") : null,
    practice.result ? practiceResultNodes(practice.result, unit) : null,
  ];
  queueMicrotask(updatePracticeCount);
  return children;
}

function updatePracticeCount() {
  const node = $("practice-count");
  if (node && state.practice) node.textContent = `${wordCount(state.practice.text)} words`;
}

function practiceResultNodes(result, unit) {
  const verdict = result.passed
    ? `Passed with ${result.overall}/100. ${unit.index < state.learn.total - 1 ? "The next unit is unlocked." : "You finished the course."}`
    : `${result.overall}/100. You need ${unit.pass_score} to pass. Revise using the feedback and resubmit.`;
  return el("div", {},
    el("h2", { text: "Feedback" }),
    el("p", { class: result.passed ? "" : "error", text: verdict }),
    feedbackNodes(result));
}

async function submitPractice() {
  const practice = state.practice;
  if (!practice || practice.busy) return;
  const words = wordCount(practice.text);
  if (words < MIN_WORDS) {
    showNotice(`Write at least ${MIN_WORDS} words before submitting (${words} now).`);
    return;
  }
  practice.busy = true;
  renderUnit();
  try {
    const result = await api("/api/practice/submit", {
      method: "POST",
      body: { unit_id: state.unit.id, task: practice.task, plan: "", draft: practice.text },
    });
    practice.result = result;
    state.unit = result.unit;
    state.learn = await api("/api/learn");
    showNotice("");
  } catch (error) {
    showNotice(error.message);
  } finally {
    practice.busy = false;
    renderUnit();
  }
}

// Shared ---------------------------------------------------------------------

function render() {
  if (state.view === "today" && state.data) renderDaily();
}

async function loadToday({ keepStep = false } = {}) {
  state.data = await api("/api/today");
  state.plan = state.data.draft.plan;
  state.draft = state.data.draft.draft;
  if (!keepStep) state.step = state.draft ? WRITE : PLAN;
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

// Keyboard: ⌘/Ctrl+Enter moves to the next step (or submits on Check); Alt+1–4 jumps to a step.
document.addEventListener("keydown", (event) => {
  // Skip while an input method (for example Chinese pinyin) is composing, and ignore held-down keys.
  if (state.view !== "today" || !state.data || event.isComposing || event.repeat) return;
  if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
    event.preventDefault();
    if (state.step === CHECK) submitDraft();
    else if (state.step < CHECK) goToStep(state.step + 1);
  } else if (event.altKey && /^Digit[1-4]$/.test(event.code)) {
    event.preventDefault();
    goToStep(Number(event.code.slice(-1)) - 1);
  }
});

for (const button of document.querySelectorAll(".tab")) {
  button.addEventListener("click", () => setView(button.dataset.view));
}

$("level").addEventListener("change", async (event) => {
  try {
    await saveDraft(); // Keep unsaved words before the page reloads today's challenge.
    await api("/api/level", { method: "POST", body: { level: event.target.value } });
    $("title").textContent = "Preparing today's challenge…";
    $("question-body").replaceChildren(loadingNote("The local model is writing a challenge at the new level."));
    await loadToday({ keepStep: true });
  } catch (error) {
    // Put back the previous challenge, so the spinner does not keep running.
    if (state.data) render();
    else $("question-body").textContent = "";
    showNotice(error.message);
  }
});

// On phones the question can fold away, to give the writing area the full screen.
$("q-toggle").addEventListener("click", () => {
  const collapsed = $("question").classList.toggle("collapsed");
  $("q-toggle").setAttribute("aria-expanded", String(!collapsed));
  $("q-toggle").textContent = collapsed ? "Show task" : "Hide task";
});

$("title").textContent = "Preparing today's challenge…";
$("question-body").replaceChildren(loadingNote("Loading today's challenge. If the model is writing a new one, this can take up to a minute."));
loadToday().catch((error) => {
  $("question-body").textContent = "";
  $("title").textContent = "Could not load today's challenge";
  showNotice(error.message);
});
checkHealth();
