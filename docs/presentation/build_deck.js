// Builds docs/presentation/ONDM_Agentic_Digital_Twin_2026-11-16.pptx
// Usage: node build_deck.js <path-to-apply_theme.js>   (pptxgenjs must be resolvable)
const path = require("path");
const pptxgen = require("pptxgenjs");
const { applyTheme } = require(process.argv[2]);

const OUT = path.join(__dirname, "ONDM_Agentic_Digital_Twin_2026-11-16.pptx");
const IMG = (f) => path.join(__dirname, "img", f);

const THEME = {
  name: "ONDM NOC",
  headFontFace: "Calibri",
  bodyFontFace: "Calibri",
  colors: {
    dk1: "0B1220", lt1: "E8F1FA", dk2: "111A2E", lt2: "1C2742",
    accent1: "00B0FF", accent2: "76FF03", accent3: "FFAB00", accent4: "FF1744",
    accent5: "B388FF", accent6: "90A4AE", hlink: "40C4FF", folHlink: "B388FF",
  },
};
const HEX = THEME.colors;

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.33 x 7.5
pres.title = "ONDM Agentic Optical Network Digital Twin";
pres.author = "ONDM research team";
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
const C = pres.SchemeColor;

pres.defineSlideMaster({
  title: "ONDM Title",
  background: { color: HEX.dk1 },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.8, y: 2.2, w: 11.7, h: 1.6, fontSize: 44, bold: true,
      color: C.background1, valign: "bottom", align: "left" }, text: "" } },
    { placeholder: { options: { name: "body", type: "body", x: 0.8, y: 3.95, w: 11.7, h: 1.4, fontSize: 20,
      color: C.accent1, valign: "top" }, text: "" } },
  ],
});
pres.defineSlideMaster({
  title: "ONDM Content",
  background: { color: HEX.dk1 },
  margin: [0.5, 0.6, 0.6, 0.6],
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.6, y: 0.35, w: 12.1, h: 0.85, fontSize: 34, bold: true,
      color: C.background1, valign: "middle" }, text: "" } },
    { text: { text: "ONDM 2027 · research prototype · synthetic data", options: { x: 0.6, y: 7.0, w: 7, h: 0.3,
      fontSize: 10, color: C.accent6, isTextBox: true, margin: 0 } } },
  ],
  slideNumber: { x: 12.3, y: 7.0, w: 0.5, h: 0.3, fontSize: 10, color: HEX.accent6 },
});

function card(slide, x, y, w, h, opts = {}) {
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.12,
    fill: { color: opts.fill || HEX.dk2 }, line: { color: opts.line || HEX.lt2, width: 1 },
    objectName: opts.name || "card" });
}
function chip(slide, x, y, label, color, name) {
  slide.addShape(pres.shapes.OVAL, { x, y, w: 0.55, h: 0.55, fill: { color }, line: { color }, objectName: name + " icon" });
  slide.addText(label, { x, y, w: 0.55, h: 0.55, align: "center", valign: "middle", fontSize: 16, bold: true,
    color: C.text1, isTextBox: true, margin: 0, objectName: name + " icon label" });
}
function txt(slide, text, o) { slide.addText(text, { isTextBox: true, color: C.background1, fontSize: 14, valign: "top", ...o }); }
function bullets(items, size = 14, color) {
  return items.map((t, i) => ({ text: t, options: { bullet: true, breakLine: i < items.length - 1, fontSize: size,
    paraSpaceAfter: 6, ...(color ? { color } : {}) } }));
}

// ---------------------------------------------------------------- 1 Title
pres.addSection({ title: "Introduction" });
let s = pres.addSlide({ masterName: "ONDM Title", sectionTitle: "Introduction" });
s.addText("Agentic VLM Digital Twin for Optical Network Engineering", { placeholder: "title" });
s.addText([{ text: "Small local VLM · GNPy physical layer · live NetBox inventory · self-correcting NetworkX code",
  options: { breakLine: true } }, { text: "ONDM research prototype — demonstration, 16 November 2026",
  options: { color: C.accent6, fontSize: 16 } }], { placeholder: "body" });
s.addNotes("Opening: this is a working research prototype, not a product. Everything runs locally on one laptop GPU. All network data is synthetic.");

// ---------------------------------------------------------------- 2 Problem
s = pres.addSlide({ masterName: "ONDM Content", sectionTitle: "Introduction" });
s.addText("Optical engineering decisions span disconnected tools", { placeholder: "title" });
const probs = [
  ["1", HEX.accent1, "Diagrams & topology", "Network knowledge lives in drawings and graphs that engineers must interpret manually."],
  ["2", HEX.accent3, "Inventory", "Equipment, ports and fiber records sit in a separate system (e.g. NetBox) and drift from plans."],
  ["3", HEX.accent5, "Physical layer", "Route feasibility needs OSNR/GSNR simulation (e.g. GNPy) — a graph path alone proves nothing."],
];
probs.forEach(([n, col, h, b], i) => {
  const x = 0.6 + i * 4.1;
  card(s, x, 1.6, 3.8, 2.9, { name: `problem ${n}` });
  chip(s, x + 0.3, 1.85, n, col, `problem ${n}`);
  txt(s, h, { x: x + 0.3, y: 2.55, w: 3.3, h: 0.5, fontSize: 20, bold: true, margin: 0 });
  txt(s, b, { x: x + 0.3, y: 3.1, w: 3.3, h: 1.3, fontSize: 14, color: C.accent6, margin: 0 });
});
card(s, 0.6, 4.85, 12.1, 1.5, { fill: HEX.lt2, name: "motivation" });
txt(s, "Motivation", { x: 0.9, y: 5.0, w: 3, h: 0.4, fontSize: 18, bold: true, color: C.accent1, margin: 0 });
txt(s, "Can a compact, locally hosted vision-language model read the network, plan the task, write its own analysis code, "
  + "call inventory and physical-layer tools, and explain a decision — while every claim stays traceable to executed evidence?",
  { x: 0.9, y: 5.45, w: 11.5, h: 1.0, fontSize: 16, margin: 0 });
s.addNotes("Three silos. LLM assistants hallucinate numbers; our design goal is grounding: every number in an answer comes from executed code, NetBox, or GNPy.");

// ---------------------------------------------------------------- 3 Proposed approach
pres.addSection({ title: "Approach" });
s = pres.addSlide({ masterName: "ONDM Content", sectionTitle: "Approach" });
s.addText("Proposed: an agentic VLM loop grounded in executed tools", { placeholder: "title" });
const steps = [["Plan", "VLM reads diagram + request", HEX.accent1], ["Inventory", "NetBox read-only query", HEX.accent5],
  ["Code", "VLM writes NetworkX code", HEX.accent1], ["Execute", "Docker sandbox", HEX.accent6],
  ["Inspect", "validator vs ground truth", HEX.accent3], ["Physics", "GNPy design + propagation", HEX.accent2],
  ["Explain", "VLM, evidence only", HEX.accent1]];
steps.forEach(([h, b, col], i) => {
  const x = 0.6 + i * 1.75;
  card(s, x, 1.7, 1.55, 1.9, { name: `step ${h}` });
  chip(s, x + 0.5, 1.85, String(i + 1), col, `step ${h}`);
  txt(s, h, { x: x + 0.08, y: 2.5, w: 1.4, h: 0.4, fontSize: 16, bold: true, align: "center", margin: 0 });
  txt(s, b, { x: x + 0.08, y: 2.9, w: 1.4, h: 0.65, fontSize: 11, color: C.accent6, align: "center", margin: 0 });
  if (i < steps.length - 1) s.addShape(pres.shapes.RIGHT_ARROW, { x: x + 1.56, y: 2.5, w: 0.18, h: 0.3,
    fill: { color: HEX.accent6 }, line: { color: HEX.accent6 }, objectName: `arrow ${i}` });
});
s.addShape(pres.shapes.CURVED_UP_ARROW, { x: 5.4, y: 3.7, w: 3.2, h: 0.6, fill: { color: HEX.accent3 },
  line: { color: HEX.accent3 }, rotate: 180, objectName: "correction loop arrow" });
txt(s, "error or failed inspection → VLM corrects its code (max 3 attempts) → else labelled trusted fallback",
  { x: 2.2, y: 4.35, w: 9.8, h: 0.4, fontSize: 13, color: C.accent3, align: "center", margin: 0 });
card(s, 0.6, 5.0, 5.9, 1.35, { name: "principle 1" });
txt(s, [{ text: "Transparency by design", options: { bold: true, color: C.accent1, fontSize: 16, breakLine: true } },
  { text: "Every trace step is tagged VLM · SANDBOX · VALIDATOR · NETBOX · GNPY · TRUSTED, so a viewer always knows who produced a number.",
    options: { fontSize: 14 } }], { x: 0.85, y: 5.15, w: 5.4, h: 1.4, margin: 0 });
card(s, 6.8, 5.0, 5.9, 1.35, { name: "principle 2" });
txt(s, [{ text: "Feasibility only from simulation", options: { bold: true, color: C.accent2, fontSize: 16, breakLine: true } },
  { text: "A route is called feasible only when executed GNPy results meet explicitly configured acceptance criteria.",
    options: { fontSize: 14 } }], { x: 7.05, y: 5.15, w: 5.4, h: 1.4, margin: 0 });

// ---------------------------------------------------------------- 4 Architecture
s = pres.addSlide({ masterName: "ONDM Content", sectionTitle: "Approach" });
s.addText("Software architecture and technology stack", { placeholder: "title" });
const layers = [
  ["Interface", "Streamlit NOC console — topology view, diagram viewer, live agent trace, code viewer, GNPy tables, NetBox explorer", HEX.accent1],
  ["Agent", "ondm/agent.py — planning, code-generation loop, validator, tool orchestration, tool-calling chat", HEX.accent5],
  ["Model", "Qwen3-VL-8B-Instruct (Q4_K_M, ~6 GB) on Ollama · RTX 3500 Ada 12 GB · swappable backend interface", HEX.accent3],
  ["Tools", "Docker sandbox (NetworkX) · GNPy 3.0.1 · NetBox 4.7.5 REST via pynetbox (read-only token)", HEX.accent2],
  ["Data", "30 synthetic ROADM topologies: graph JSON + diagram PNG (immutable source of truth)", HEX.accent6],
];
layers.forEach(([h, b, col], i) => {
  const y = 1.5 + i * 1.05;
  card(s, 0.6, y, 7.6, 0.9, { name: `layer ${h}` });
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.75, y: y + 0.17, w: 1.5, h: 0.56, rectRadius: 0.1,
    fill: { color: col }, line: { color: col }, objectName: `layer ${h} tag` });
  txt(s, h, { x: 0.75, y: y + 0.17, w: 1.5, h: 0.56, fontSize: 15, bold: true, color: C.text1, align: "center",
    valign: "middle", margin: 0 });
  txt(s, b, { x: 2.45, y: y + 0.1, w: 5.6, h: 0.72, fontSize: 13, valign: "middle", margin: 0 });
});
card(s, 8.5, 1.5, 4.2, 5.1, { fill: HEX.lt2, name: "sandbox box" });
txt(s, "Sandbox isolation", { x: 8.75, y: 1.65, w: 3.8, h: 0.45, fontSize: 18, bold: true, color: C.accent1, margin: 0 });
txt(s, bullets(["Fresh container per run", "--network none", "Read-only root FS, non-root user", "All capabilities dropped",
  "256 MB RAM · 1 CPU · 64 PIDs · 20 s", "No host mounts, no env → no NetBox token reachable",
  "AST policy pre-check (imports, dunders, eval/open)"], 13), { x: 8.75, y: 2.15, w: 3.8, h: 4.3, margin: 0 });
s.addNotes("Verified: network blocked, memory kill, timeout, and policy rejection all tested (tests/test_core.py + manual).");

// ---------------------------------------------------------------- 5 GNPy + NetBox
pres.addSection({ title: "Integrations" });
s = pres.addSlide({ masterName: "ONDM Content", sectionTitle: "Integrations" });
s.addText("GNPy and NetBox integration", { placeholder: "title" });
s.addChart(pres.charts.BAR, [{ name: "Remaining margin (dB)",
  labels: ["topo_0003 A-F 90 km 400G", "topo_0003 A-F-E-D-C 370 km 400G", "topo_0003 A-B-C 740 km 400G",
    "topo_0013 A-F-E-D-G 590 km 400G", "topo_0013 A-F-E-D-G 590 km 300G"],
  values: [5.75, 0.32, -0.68, -0.98, 1.81] }], {
  x: 0.6, y: 1.45, w: 6.6, h: 4.2, barDir: "bar", showTitle: true, title: "GNPy worst-channel remaining margin (dB)",
  titleColor: HEX.lt1, titleFontSize: 14, titleFontFace: "+mn-lt", showValue: true, dataLabelPosition: "outEnd",
  dataLabelColor: HEX.lt1, dataLabelFontSize: 11, dataLabelFontFace: "+mn-lt", dataLabelFormatCode: "0.00",
  chartColors: [HEX.accent2, HEX.accent3, HEX.accent4, HEX.accent4, HEX.accent2], invertedColors: [HEX.accent4],
  catAxisLabelColor: HEX.accent6, valAxisLabelColor: HEX.accent6, catAxisLabelFontSize: 11, valAxisLabelFontSize: 10,
  catAxisLabelFontFace: "+mn-lt", valAxisLabelFontFace: "+mn-lt", valGridLine: { color: HEX.lt2, size: 0.5 },
  catGridLine: { style: "none" }, showLegend: false, catAxisOrientation: "maxMin", valAxisMinVal: -2, valAxisMaxVal: 7,
  catAxisLabelPos: "low",
});
txt(s, "Margin = GSNR(0.1 nm) − required OSNR − penalties − 2 dB library system margin. Accept if ≥ 1 dB (configurable). "
  + "Example equipment library; synthetic spans.", { x: 0.6, y: 5.75, w: 6.6, h: 0.8, fontSize: 11, color: C.accent6, margin: 0 });
card(s, 7.5, 1.45, 5.2, 2.45, { name: "gnpy card" });
txt(s, [{ text: "GNPy 3.0.1 — executed, not mocked", options: { bold: true, color: C.accent2, fontSize: 16, breakLine: true } },
  ...bullets(["Original research converter reused unchanged", "Every ROADM → GNPy Roadm; links → spans ≤ 80 km + ILAs",
    "Strict ROADM path, Voyager modes 100–400G", "Lower-rate fallback when 400G fails"], 13)],
  { x: 7.75, y: 1.6, w: 4.8, h: 2.2, margin: 0 });
card(s, 7.5, 4.1, 5.2, 2.5, { name: "netbox card" });
txt(s, [{ text: "NetBox 4.7.5 — live, read-only", options: { bold: true, color: C.accent5, fontSize: 16, breakLine: true } },
  ...bullets(["283 ROADMs · 114 transponders · 310 fiber cables", "All tagged ondm-synthetic; one-command rollback",
    "3 tagged demo constraints: planned cable, disabled port, offline transponder", "Topology ↔ inventory correlation feeds routing"], 13)],
  { x: 7.75, y: 4.25, w: 4.8, h: 2.25, margin: 0 });

// ---------------------------------------------------------------- 6 Use cases
pres.addSection({ title: "Use cases" });
s = pres.addSlide({ masterName: "ONDM Content", sectionTitle: "Use cases" });
s.addText("Three operator workflows", { placeholder: "title" });
const ucs = [
  ["1", HEX.accent1, "Service provisioning", "“Provision 400G between ROADM A and G”",
    ["NetBox marks unusable links (planned cable, disabled port)", "VLM writes k-shortest-path code avoiding them",
      "GNPy per candidate route + lower-rate fallback"], "topo_0013 A→G: 590 km best route fails 400G (−0.98 dB); 300G passes (+1.81 dB)"],
  ["2", HEX.accent4, "Fiber failure & restoration", "“Analyse failure of link H–J”",
    ["VLM writes failure code on a graph copy", "Affected site pairs + restoration paths", "GNPy on the longest restoration routes"],
    "Validator re-checks every restoration path against the failed network"],
  ["3", HEX.accent3, "Inventory-aware troubleshooting", "“Inspect ROADM D and its fibers”",
    ["NetBox devices, ports, cables correlated with topology", "VLM graph code: degree, articulation, reachability",
      "GNPy to the farthest reachable site"], "topo_0013 D: disabled DEG-1 on C–D, no transponder, D–E–F–K 650 km fails 400G"],
];
ucs.forEach(([n, col, h, q, b, res], i) => {
  const x = 0.6 + i * 4.1;
  card(s, x, 1.45, 3.8, 5.2, { name: `use case ${i + 1}` });
  chip(s, x + 0.25, 1.65, n, col, `use case ${i + 1}`);
  txt(s, h, { x: x + 0.95, y: 1.65, w: 2.75, h: 0.6, fontSize: 17, bold: true, valign: "middle", margin: 0 });
  txt(s, q, { x: x + 0.25, y: 2.4, w: 3.35, h: 0.6, fontSize: 13, italic: true, color: C.accent1, margin: 0 });
  txt(s, bullets(b, 13), { x: x + 0.25, y: 3.05, w: 3.35, h: 2.0, margin: 0 });
  card(s, x + 0.2, 5.15, 3.4, 1.3, { fill: HEX.lt2, name: `use case ${i + 1} result` });
  txt(s, res, { x: x + 0.35, y: 5.25, w: 3.1, h: 1.1, fontSize: 13, color: C.background1, valign: "middle", margin: 0 });
});

// ---------------------------------------------------------------- 7 Demo
s = pres.addSlide({ masterName: "ONDM Content", sectionTitle: "Use cases" });
s.addText("Live demonstration", { placeholder: "title" });
s.addImage({ path: IMG("app_bc3_troubleshooting.jpg"), x: 0.6, y: 1.4, w: 7.7, h: 4.81, objectName: "app screenshot troubleshooting",
  altText: "Streamlit console showing the troubleshooting workflow result for ROADM D" });
card(s, 8.6, 1.4, 4.1, 5.2, { name: "demo script" });
txt(s, [{ text: "Demo script (~8 min)", options: { bold: true, color: C.accent1, fontSize: 17, breakLine: true } },
  { text: "Overview: graph vs original diagram", options: { bullet: { type: "number" }, breakLine: true, fontSize: 14, paraSpaceAfter: 6 } },
  { text: "Provisioning topo_0013 A→G — watch code self-correct", options: { bullet: { type: "number" }, breakLine: true, fontSize: 14, paraSpaceAfter: 6 } },
  { text: "Failure of a mesh link — restoration paths", options: { bullet: { type: "number" }, breakLine: true, fontSize: 14, paraSpaceAfter: 6 } },
  { text: "Troubleshoot ROADM D — NetBox evidence", options: { bullet: { type: "number" }, breakLine: true, fontSize: 14, paraSpaceAfter: 6 } },
  { text: "Chat: free question → VLM picks tools", options: { bullet: { type: "number" }, breakLine: true, fontSize: 14, paraSpaceAfter: 6 } },
  { text: "GNPy lab: verify a verdict by hand", options: { bullet: { type: "number" }, fontSize: 14 } }],
  { x: 8.85, y: 1.55, w: 3.7, h: 4.9, margin: 0 });
txt(s, "Runs fully offline: Ollama + Docker + NetBox on one laptop. A workflow takes ~1–2.5 min, dominated by VLM generation.",
  { x: 0.6, y: 6.3, w: 7.7, h: 0.5, fontSize: 12, color: C.accent6, margin: 0 });

// ---------------------------------------------------------------- 8 Findings & limitations
pres.addSection({ title: "Findings and roadmap" });
s = pres.addSlide({ masterName: "ONDM Content", sectionTitle: "Findings and roadmap" });
s.addText("Preliminary implementation findings and limitations", { placeholder: "title" });
card(s, 0.6, 1.45, 6.0, 4.6, { name: "findings" });
txt(s, [{ text: "What we observed (development runs, not a benchmark)", options: { bold: true, color: C.accent2, fontSize: 16, breakLine: true } },
  ...bullets(["Diagram reading: Qwen3-VL-8B extracted topo_0003 exactly (6/6 sites, 6/6 links, all km correct)",
    "Smoke run, 13 Nov: failure-analysis code verified on attempt 1; troubleshooting code self-corrected to a verified result on attempt 3",
    "Provisioning code repeated the same bug 3x, so the labelled trusted fallback was used (never shown as generated)",
    "Chat agent self-corrected a failing sandbox call and answered from the tool result",
    "Validator caught silently wrong output (same route returned three times)",
    "GNPy turns graph routes into decisions: 590 km route fails 400G, passes 300G"], 13)],
  { x: 0.85, y: 1.6, w: 5.5, h: 4.95, margin: 0 });
card(s, 6.9, 1.45, 5.8, 4.6, { name: "limitations" });
txt(s, [{ text: "Limitations", options: { bold: true, color: C.accent4, fontSize: 16, breakLine: true } },
  ...bullets(["All topologies and inventory are synthetic; 3 constraints injected for the demo",
    "GNPy example equipment library — not vendor or field-calibrated",
    "Test transceivers at every ROADM are a simulation assumption",
    "No spectrum occupancy, ageing, or ROADM filtering penalties beyond GNPy defaults",
    "Single VLM, small number of runs; no quantitative evaluation yet",
    "Dataset splits preliminary — not leakage-free holdouts"], 13)],
  { x: 7.15, y: 1.6, w: 5.3, h: 3.95, margin: 0 });

// ---------------------------------------------------------------- 9 Roadmap
s = pres.addSlide({ masterName: "ONDM Content", sectionTitle: "Findings and roadmap" });
s.addText("ONDM research roadmap", { placeholder: "title" });
const road = [["Now", "Prototype", "VLM + GNPy + NetBox + sandboxed code, 3 workflows"],
  ["Next", "Dataset", "Larger multimodal set; rendered ILA/transceiver symbols; grouped holdouts"],
  ["Next", "Models", "Fine-tune and compare 3–4 compact VLMs on held-out optical tasks"],
  ["Then", "Evaluation", "Task metrics for reading, code success, tool use; TopoBench compatibility"],
  ["Then", "Tooling", "MCP-based engineering tool interfaces; richer planning and self-correction"],
  ["Journal", "Extension", "Complex scenarios, richer physics, autonomous engineering workflows"]];
road.forEach(([when, h, b], i) => {
  const x = 0.6 + i * 2.05;
  const col = [HEX.accent2, HEX.accent1, HEX.accent1, HEX.accent5, HEX.accent5, HEX.accent3][i];
  s.addShape(pres.shapes.OVAL, { x: x + 0.7, y: 1.8, w: 0.45, h: 0.45, fill: { color: col }, line: { color: col },
    objectName: `milestone ${i + 1}` });
  if (i < road.length - 1) s.addShape(pres.shapes.LINE, { x: x + 1.15, y: 2.025, w: 1.6, h: 0, line: { color: HEX.lt2, width: 2 },
    objectName: `timeline segment ${i + 1}` });
  txt(s, when, { x: x, y: 2.35, w: 1.85, h: 0.35, fontSize: 12, color: C.accent6, align: "center", margin: 0 });
  card(s, x, 2.8, 1.85, 2.6, { name: `roadmap ${h}` });
  txt(s, h, { x: x + 0.12, y: 2.95, w: 1.6, h: 0.45, fontSize: 16, bold: true, margin: 0 });
  txt(s, b, { x: x + 0.12, y: 3.45, w: 1.6, h: 1.85, fontSize: 12, color: C.accent6, margin: 0 });
});
card(s, 0.6, 5.7, 12.1, 0.95, { fill: HEX.lt2, name: "modularity" });
txt(s, "Built for the roadmap: swappable VLM backend, model-independent trace format, deterministic validator for future scoring.",
  { x: 0.85, y: 5.8, w: 11.6, h: 0.75, fontSize: 15, valign: "middle", margin: 0 });

(async () => {
  await pres.writeFile({ fileName: OUT });
  await applyTheme(OUT, THEME);
  console.log("wrote", OUT);
})();
