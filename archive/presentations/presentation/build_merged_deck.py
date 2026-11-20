"""Merge the earlier presentation ("Todays Presentation.pptx") with the new prototype slides.

The original 7 slides are kept unchanged; new slides are appended in the same white / navy style.
Usage: .venv\\Scripts\\python docs\\presentation\\build_merged_deck.py "C:\\Users\\dipto\\Downloads\\Todays Presentation.pptx"
"""
import sys
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

HERE = Path(__file__).resolve().parent
OUT = HERE / "ONDM_Merged_Presentation.pptx"
IMG = HERE / "img"

NAVY = RGBColor(0x16, 0x36, 0x4A)
TEXT = RGBColor(0x26, 0x32, 0x38)
MUTED = RGBColor(0x60, 0x7D, 0x8B)
CARD = RGBColor(0xF4, 0xF7, 0xFA)
EDGE = RGBColor(0xD5, 0xDE, 0xE6)
BLUE = RGBColor(0x1E, 0x88, 0xE5)
GREEN = RGBColor(0x2E, 0x7D, 0x32)
ORANGE = RGBColor(0xEF, 0x6C, 0x00)
RED = RGBColor(0xD3, 0x2F, 0x2F)
PURPLE = RGBColor(0x6A, 0x1B, 0x9A)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
FONT = "Calibri"


# ------------------------------------------------------------------ helpers
def new_slide(prs, title):
    s = prs.slides.add_slide(prs.slide_layouts[6])  # Blank, like the original slides
    s.background.fill.solid()
    s.background.fill.fore_color.rgb = WHITE
    text(s, title, 0.35, 0.22, 12.6, 0.65, size=28, bold=True, color=NAVY, name="slide-title")
    return s


def text(slide, content, x, y, w, h, size=15, bold=False, color=TEXT, align=PP_ALIGN.LEFT, italic=False,
         anchor=MSO_ANCHOR.TOP, name=None):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    if name:
        tb.name = name
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = Inches(0.05)
    tf.margin_top = tf.margin_bottom = Inches(0.03)
    items = content if isinstance(content, list) else [content]
    for i, item in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        runs = item if isinstance(item, list) else [(item, {})] if isinstance(item, str) else [item]
        for r in runs:
            t, o = (r, {}) if isinstance(r, str) else r
            run = p.add_run()
            run.text = t
            f = run.font
            f.name = FONT
            f.size = Pt(o.get("size", size))
            f.bold = o.get("bold", bold)
            f.italic = o.get("italic", italic)
            f.color.rgb = o.get("color", color)
        p.space_after = Pt(o.get("after", 4)) if runs else Pt(4)
    return tb


def bullets(slide, items, x, y, w, h, size=14, color=TEXT, gap=5):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = Inches(0.05)
    for i, item in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        runs = item if isinstance(item, list) else [(item, {})]
        first = True
        for t, o in runs:
            run = p.add_run()
            run.text = ("• " if first else "") + t
            first = False
            run.font.name = FONT
            run.font.size = Pt(o.get("size", size))
            run.font.bold = o.get("bold", False)
            run.font.color.rgb = o.get("color", color)
        p.space_after = Pt(gap)
    return tb


def box(slide, x, y, w, h, fill=CARD, line=EDGE, shape=MSO_SHAPE.ROUNDED_RECTANGLE, name="card"):
    sh = slide.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    sh.name = name
    sh.fill.solid()
    sh.fill.fore_color.rgb = fill
    sh.line.color.rgb = line
    sh.line.width = Pt(1)
    sh.shadow.inherit = False
    if shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        sh.adjustments[0] = 0.08
    sh.text_frame.text = ""
    return sh


def badge(slide, x, y, label, color, d=0.5, size=16):
    sh = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(x), Inches(y), Inches(d), Inches(d))
    sh.fill.solid()
    sh.fill.fore_color.rgb = color
    sh.line.color.rgb = color
    sh.shadow.inherit = False
    tf = sh.text_frame
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = label
    r.font.name, r.font.size, r.font.bold, r.font.color.rgb = FONT, Pt(size), True, WHITE
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    return sh


def arrow(slide, x, y, w=0.3, h=0.3, color=MUTED):
    sh = slide.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, Inches(x), Inches(y), Inches(w), Inches(h))
    sh.fill.solid()
    sh.fill.fore_color.rgb = color
    sh.line.color.rgb = color
    sh.shadow.inherit = False


def footer(slide, note="Research prototype · synthetic data · work in progress"):
    text(slide, note, 0.35, 7.08, 8, 0.3, size=10, color=MUTED)


def notes(slide, t):
    slide.notes_slide.notes_text_frame.text = t


# ------------------------------------------------------------------ slides
def slide_from_idea(prs):
    s = new_slide(prs, "From Idea to Working Prototype: What Changed")
    text(s, "Revisiting the earlier findings — what the new dataset and prototype address, and what is still open",
         0.35, 0.85, 12.5, 0.4, size=15, color=MUTED, italic=True)
    rows = [
        ("Limited structural diversity", "30 new topologies: star 9 · ring 6 · tree 4 · hybrid 4 · mesh 2 · random 5", GREEN, "Addressed"),
        ("Low reasoning complexity", "6–12 ROADM sites per graph, diameter 2–10 hops (was ≤ 2), multi-hop routing tasks", GREEN, "Addressed"),
        ("Limited optical realism", "ROADM switching sites, fiber spans with in-line amplifiers, GNPy physical-layer simulation", GREEN, "Addressed"),
        ("Insufficient generalization testing", "Splits are still random; topology-aware holdouts planned", ORANGE, "Open"),
        ("Unverified visual annotations", "VLM diagram reading is now checked against ground truth; full YOLO/pixel QA still pending", ORANGE, "Partly"),
    ]
    text(s, "Earlier finding", 0.45, 1.45, 3.6, 0.35, size=14, bold=True, color=NAVY)
    text(s, "Current status", 4.25, 1.45, 7.0, 0.35, size=14, bold=True, color=NAVY)
    for i, (a, b, col, tag) in enumerate(rows):
        y = 1.85 + i * 1.0
        box(s, 0.35, y, 12.6, 0.85, name=f"row {i + 1}")
        text(s, a, 0.5, y + 0.1, 3.6, 0.65, size=15, bold=True, color=NAVY, anchor=MSO_ANCHOR.MIDDLE)
        text(s, b, 4.25, y + 0.1, 7.2, 0.65, size=14, anchor=MSO_ANCHOR.MIDDLE)
        pill = box(s, 11.55, y + 0.24, 1.25, 0.38, fill=col, line=col, name=f"status {i + 1}")
        tf = pill.text_frame
        tf.margin_top = tf.margin_bottom = 0
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        r = p.add_run()
        r.text = tag
        r.font.name, r.font.size, r.font.bold, r.font.color.rgb = FONT, Pt(12), True, WHITE
    footer(s)
    notes(s, "Link back to the Findings and Limitations slide: three items addressed, two still open.")


def slide_architecture(prs):
    s = new_slide(prs, "Prototype Architecture: An Agentic VLM Digital Twin")
    text(s, "One small local VLM plans, writes its own code and calls engineering tools — every number comes from an "
         "executed tool", 0.35, 0.85, 12.6, 0.4, size=15, color=MUTED, italic=True)
    steps = [("1", "Plan", "VLM reads diagram + request", BLUE), ("2", "Inventory", "NetBox (read-only)", PURPLE),
             ("3", "Code", "VLM writes NetworkX code", BLUE), ("4", "Execute", "isolated sandbox", MUTED),
             ("5", "Check", "validator vs ground truth", ORANGE), ("6", "Physics", "GNPy simulation", GREEN),
             ("7", "Explain", "VLM, evidence only", BLUE)]
    for i, (n, h, b, col) in enumerate(steps):
        x = 0.35 + i * 1.82
        box(s, x, 1.65, 1.6, 1.85, name=f"step {h}")
        badge(s, x + 0.55, 1.78, n, col)
        text(s, h, x + 0.05, 2.35, 1.5, 0.4, size=16, bold=True, color=NAVY, align=PP_ALIGN.CENTER)
        text(s, b, x + 0.05, 2.75, 1.5, 0.7, size=12, color=MUTED, align=PP_ALIGN.CENTER)
        if i < len(steps) - 1:
            arrow(s, x + 1.6, 2.45, 0.22, 0.25)
    loop = s.shapes.add_shape(MSO_SHAPE.U_TURN_ARROW, Inches(5.7), Inches(3.6), Inches(3.4), Inches(0.55))
    loop.rotation = 180
    loop.fill.solid()
    loop.fill.fore_color.rgb = ORANGE
    loop.line.color.rgb = ORANGE
    loop.shadow.inherit = False
    text(s, "If the code fails or the check finds an error, the VLM corrects it (up to 3 attempts); otherwise a "
         "clearly labelled built-in tool is used", 2.3, 4.2, 9.6, 0.4, size=13, color=ORANGE, align=PP_ALIGN.CENTER)
    stack = [("Interface", "Streamlit console", BLUE), ("Model", "Qwen3-VL-8B-Instruct via Ollama (local GPU)", ORANGE),
             ("Tools", "NetworkX · GNPy 3.0.1 · NetBox 4.7 · Docker sandbox", GREEN),
             ("Data", "30 synthetic ROADM topologies (graph JSON + diagram image)", MUTED)]
    for i, (h, b, col) in enumerate(stack):
        x = 0.35 + (i % 2) * 6.35
        y = 4.85 + (i // 2) * 1.0
        box(s, x, y, 6.25, 0.85, name=f"stack {h}")
        tag = box(s, x + 0.15, y + 0.2, 1.3, 0.45, fill=col, line=col, name=f"stack tag {h}")
        tf = tag.text_frame
        tf.margin_top = tf.margin_bottom = 0
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        r = p.add_run()
        r.text = h
        r.font.name, r.font.size, r.font.bold, r.font.color.rgb = FONT, Pt(13), True, WHITE
        text(s, b, x + 1.6, y + 0.12, 4.55, 0.6, size=14, anchor=MSO_ANCHOR.MIDDLE)
    footer(s)


def slide_functionalities(prs):
    s = new_slide(prs, "Functionalities Implemented")
    cards = [
        ("Diagram understanding", BLUE, "The VLM reads topology images; its extraction is compared with the ground truth (nodes, links, km)."),
        ("Autonomous code generation", BLUE, "The VLM writes Python/NetworkX code for each request; generated code is shown to the user."),
        ("Safe execution + self-correction", ORANGE, "Code runs in an isolated container (no network, no secrets); errors are fed back for correction."),
        ("GNPy physical layer", GREEN, "Candidate routes are simulated (GSNR/OSNR, margin); feasibility is stated only from the simulation."),
        ("NetBox inventory", PURPLE, "Live read-only inventory: ROADMs, ports, fiber cables, transponders, correlated with the topology."),
        ("Transparent console", NAVY, "Streamlit app with topology view, step-by-step agent trace, code viewer, GNPy and NetBox panels."),
    ]
    for i, (h, col, b) in enumerate(cards):
        x = 0.35 + (i % 3) * 4.25
        y = 1.35 + (i // 3) * 2.6
        box(s, x, y, 4.05, 2.3, name=f"function {i + 1}")
        badge(s, x + 0.25, y + 0.25, str(i + 1), col)
        text(s, h, x + 0.9, y + 0.25, 3.0, 0.55, size=17, bold=True, color=NAVY, anchor=MSO_ANCHOR.MIDDLE)
        text(s, b, x + 0.25, y + 0.95, 3.6, 1.5, size=14)
    footer(s)


def slide_bc(prs, n, title, color, img, request, steps, result, value, note=""):
    s = new_slide(prs, f"Business Case {n}: {title}")
    s.shapes.add_picture(str(IMG / img), Inches(0.35), Inches(1.05), height=Inches(5.85))
    x0 = 6.75
    box(s, x0, 1.05, 6.2, 0.85, fill=RGBColor(0xE3, 0xF2, 0xFD), line=RGBColor(0xBB, 0xDE, 0xFB), name="request")
    text(s, [[("Operator request: ", {"bold": True, "color": NAVY}), (request, {"italic": True})]], x0 + 0.15, 1.1,
         5.9, 0.75, size=14, anchor=MSO_ANCHOR.MIDDLE)
    text(s, "What the agent does", x0, 2.05, 6.2, 0.35, size=15, bold=True, color=NAVY)
    bullets(s, steps, x0, 2.4, 6.2, 1.9, size=13, gap=3)
    box(s, x0, 4.35, 6.2, 1.45, name="result")
    text(s, "Example result (executed tools)", x0 + 0.15, 4.4, 5.9, 0.35, size=14, bold=True, color=color)
    bullets(s, result, x0 + 0.1, 4.75, 6.0, 1.05, size=13, gap=2)
    text(s, [[("Value for the operator: ", {"bold": True, "color": NAVY}), (value, {})]], x0, 5.95, 6.2, 0.9, size=14)
    footer(s)
    if note:
        notes(s, note)


def slide_bcs(prs):
    slide_bc(prs, 1, "Intelligent Optical Service Provisioning", GREEN, "bc1_provisioning.png",
             "“Provision a 400G service between ROADM A and ROADM G.”",
             ["Checks NetBox: link A–B cable is only “planned”, C–D degree port is disabled → excluded",
              "Writes and runs k-shortest-path code that avoids unusable links",
              "Simulates each candidate in GNPy; tries a lower rate if 400G fails",
              "Explains the decision with numbers and assumptions"],
             ["Route A-F-E-D-G (590 km): 400G not feasible (margin −0.98 dB)",
              "Route A-L-F-E-D-G (1010 km): not feasible (−2.74 dB)",
              "Same 590 km route at 300G: feasible (+1.81 dB margin)"],
             "a route that is inventory-aware and physically checked, not just the shortest line on a map.",
             "topo_0013. Numbers from GNPy 3.0.1 with example equipment parameters.")
    slide_bc(prs, 2, "Fiber Failure and Restoration", RED, "bc2_failure.png",
             "“Analyse the failure of fiber link H–J and find restoration paths.”",
             ["Writes failure-analysis code on a copy of the network (data never changed)",
              "Finds every site pair whose route used H–J and computes a new route",
              "Validator re-checks each restoration path against the failed network",
              "Simulates the longest restoration routes in GNPy"],
             ["Network stays connected; 10 site pairs affected, all re-routable",
              "But the longest restoration routes (520–560 km) fail 400G in GNPy (−0.27 to −0.66 dB)",
              "→ connectivity restored ≠ 400G service restored"],
             "quick impact assessment that separates “reachable” from “restorable at the same rate”.",
             "topo_0023 mesh. In the smoke run the VLM's failure code was correct on the first attempt.")
    slide_bc(prs, 3, "Inventory-Aware Troubleshooting", ORANGE, "bc3_troubleshooting.png",
             "“Inspect ROADM D and its fiber connections. What limits provisioning?”",
             ["Queries NetBox for D: devices, 12 degree ports, cables, transponders",
              "Correlates inventory with the topology to find mismatches",
              "Writes graph code: degree, single points of failure, reachability",
              "Uses GNPy for the physical question: can D reach its farthest site?"],
             ["Degree port DEG-1 (link C–D) disabled → D effectively loses C–D",
              "No transponder installed at D → cannot terminate a new service",
              "Farthest reachable site K via D-E-F-K (650 km): 400G not feasible (−0.96 dB)"],
             "one evidence-based view across inventory, topology and physical layer.",
             "The disabled port and planned cable are synthetic scenarios injected and tagged in NetBox for the demo.")


def slide_demo(prs):
    s = new_slide(prs, "Live Demonstration")
    text(s, "Short walk-through of the running prototype — fully local on one laptop (Ollama + Docker + NetBox)",
         0.35, 0.85, 12.6, 0.4, size=15, color=MUTED, italic=True)
    steps = [("1", "Overview", "Topology graph next to the original diagram image", BLUE),
             ("2", "Provisioning", "A → G at 400G: watch the agent write code, check NetBox, run GNPy", GREEN),
             ("3", "Failure", "Cut one fiber link and see affected services and restoration paths", RED),
             ("4", "Troubleshooting", "Inspect ROADM D: inventory issues + physical reach", ORANGE),
             ("5", "Free question", "Ask the chat anything; the VLM chooses its own tools", PURPLE),
             ("6", "Verify", "Re-run a GNPy result by hand in the GNPy lab tab", NAVY)]
    for i, (n, h, b, col) in enumerate(steps):
        x = 0.35 + (i % 3) * 4.25
        y = 1.5 + (i // 3) * 2.3
        box(s, x, y, 4.05, 2.05, name=f"demo {n}")
        badge(s, x + 0.25, y + 0.25, n, col)
        text(s, h, x + 0.9, y + 0.25, 3.0, 0.5, size=17, bold=True, color=NAVY, anchor=MSO_ANCHOR.MIDDLE)
        text(s, b, x + 0.25, y + 0.9, 3.6, 1.05, size=14)
    box(s, 0.35, 6.2, 12.6, 0.7, fill=RGBColor(0xFF, 0xF8, 0xE1), line=RGBColor(0xFF, 0xE0, 0x82), name="demo note")
    text(s, "Each request takes about 1–2 minutes. The model sometimes makes mistakes — you will see them corrected or "
         "flagged live in the agent trace.", 0.5, 6.25, 12.3, 0.6, size=14, anchor=MSO_ANCHOR.MIDDLE)
    footer(s)


def slide_observations(prs):
    s = new_slide(prs, "Preliminary Observations and Limitations")
    box(s, 0.35, 1.1, 6.2, 4.4, name="observations")
    text(s, "What we observed so far (early runs, not a benchmark)", 0.55, 1.2, 5.8, 0.4, size=15, bold=True, color=GREEN)
    bullets(s, ["The VLM read a test diagram exactly (6/6 sites, 6/6 links, all km labels)",
                "Generated code often fails at first; with error feedback it corrected itself in some runs",
                "When it could not fix its code, the labelled built-in tool took over",
                "The validator caught wrong-but-running code (same route returned three times)",
                "GNPy changes the conclusion: long routes that look fine on the graph fail at 400G"],
            0.55, 1.7, 5.85, 3.7, size=15, gap=8)
    box(s, 6.75, 1.1, 6.2, 4.4, name="limitations")
    text(s, "Limitations", 6.95, 1.2, 5.8, 0.4, size=15, bold=True, color=RED)
    bullets(s, ["All topologies and inventory are synthetic (3 demo issues injected in NetBox)",
                "GNPy uses example equipment parameters, not vendor or field data",
                "One VLM, small number of runs — no quantitative evaluation yet",
                "Each workflow takes ~1–2 minutes on a laptop GPU",
                "Dataset splits are still random (not leakage-free)"],
            6.95, 1.7, 5.85, 3.7, size=15, gap=8)
    box(s, 0.35, 5.75, 12.6, 1.0, fill=RGBColor(0xE3, 0xF2, 0xFD), line=RGBColor(0xBB, 0xDE, 0xFB), name="takeaway")
    text(s, [[("Takeaway: ", {"bold": True, "color": NAVY}),
              ("grounding a small model in executed tools makes its answers checkable — errors become visible "
               "instead of silent.", {})]], 0.55, 5.8, 12.2, 0.9, size=16, anchor=MSO_ANCHOR.MIDDLE)
    footer(s)


def slide_future(prs):
    s = new_slide(prs, "Future Work")
    items = [("Dataset", "Expand to larger, more complex and realistic diagrams; draw amplifiers/transceivers; topology-aware test sets", BLUE),
             ("Models", "Compare and fine-tune 3–4 compact VLMs (e.g. Qwen, InternVL, Gemma) on held-out optical tasks", ORANGE),
             ("Evaluation", "Measure graph extraction (node/edge F1, distance error), reasoning, tool use and end-to-end accuracy; TopoBench study", GREEN),
             ("Tooling", "Expose GNPy, NetBox and graph tools through MCP interfaces; stronger planning and self-correction", PURPLE),
             ("Journal extension", "More complex operational scenarios, richer physical simulation, autonomous engineering workflows", NAVY)]
    s.shapes.add_connector(1, Inches(0.95), Inches(1.6), Inches(0.95), Inches(6.55)).line.color.rgb = EDGE
    for i, (h, b, col) in enumerate(items):
        y = 1.15 + i * 1.12
        badge(s, 0.7, y + 0.2, str(i + 1), col)
        box(s, 1.45, y, 11.5, 0.95, name=f"future {h}")
        text(s, h, 1.65, y + 0.1, 2.4, 0.75, size=16, bold=True, color=NAVY, anchor=MSO_ANCHOR.MIDDLE)
        text(s, b, 4.1, y + 0.1, 8.7, 0.75, size=14, anchor=MSO_ANCHOR.MIDDLE)
    footer(s)


def slide_ideas(prs):
    s = new_slide(prs, "We Would Value Your Ideas")
    text(s, "This is an early research prototype. We are not presenting final results — we are asking for your "
         "suggestions on where to take it next.", 0.35, 0.95, 12.6, 0.7, size=17, color=TEXT)
    qs = [("Use cases", "Which operator problems would be most valuable to target? Are the three business cases the right ones?"),
          ("Data", "Could realistic (anonymised) diagrams, inventory or equipment profiles be made available?"),
          ("Physical layer", "Which transceiver modes, margins and acceptance criteria should we use with GNPy?"),
          ("Models & evaluation", "Which VLMs and which metrics would make the comparison convincing?"),
          ("Integration", "Which tools beyond NetBox and GNPy matter in practice (planning, monitoring, ticketing)?"),
          ("Anything else", "What would make this useful for you or your team?")]
    for i, (h, b) in enumerate(qs):
        x = 0.35 + (i % 2) * 6.35
        y = 1.85 + (i // 2) * 1.6
        box(s, x, y, 6.25, 1.4, name=f"question {i + 1}")
        badge(s, x + 0.2, y + 0.42, "?", BLUE, d=0.55, size=18)
        text(s, h, x + 0.95, y + 0.12, 5.1, 0.4, size=16, bold=True, color=NAVY)
        text(s, b, x + 0.95, y + 0.5, 5.15, 0.85, size=14)
    footer(s, "Thank you — feedback and ideas welcome")


def main(src):
    prs = Presentation(src)
    original = len(prs.slides)
    slide_from_idea(prs)
    slide_architecture(prs)
    slide_functionalities(prs)
    slide_bcs(prs)
    slide_demo(prs)
    slide_observations(prs)
    slide_future(prs)
    slide_ideas(prs)
    prs.save(OUT)
    print(f"kept {original} original slides, added {len(prs.slides) - original}; wrote {OUT}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\dipto\Downloads\Todays Presentation.pptx")
