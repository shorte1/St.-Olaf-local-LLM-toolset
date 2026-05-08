from fuzzywuzzy import fuzz
import html

SEVERITY_COLORS = {
    "strength": "#d4edda",
    "minor": "#fff3cd",
    "major": "#f8d7da"
}

SEVERITY_BORDER = {
    "strength": "#28a745",
    "minor": "#ffc107",
    "major": "#dc3545"
}

CATEGORY_ICONS = {
    "Argument & Evidence": "💡",
    "Structure & Organization": "🏗",
    "Clarity & Style": "✏️",
    "Counterargument Handling": "⚖️",
    "Grammar": "📝",
    "Accessibility": "♿"
}

# ── Shared CSS injected into every page ──────────────────────────────────────

_BASE_CSS = """
    * { box-sizing: border-box; margin: 0; padding: 0; }

    body {
        font-family: Georgia, serif;
        background: #f5f5f5;
        color: #333;
    }

    .top-bar {
        background: #2c3e50;
        color: white;
        padding: 12px 24px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        position: sticky;
        top: 0;
        z-index: 100;
    }

    .top-bar h1 { font-size: 1.1em; font-weight: normal; }

    .top-bar .mode-badge {
        font-size: 0.75em;
        background: rgba(255,255,255,0.15);
        padding: 3px 10px;
        border-radius: 12px;
        font-family: Arial, sans-serif;
        margin-left: 12px;
    }

    .legend {
        display: flex;
        gap: 8px;
        align-items: center;
        font-size: 0.8em;
    }

    .legend-item {
        padding: 2px 8px;
        border-radius: 3px;
        font-family: Arial, sans-serif;
        color: #333;
    }

    .overview-bar {
        background: white;
        border-bottom: 1px solid #ddd;
        padding: 16px 24px;
    }

    .overview-bar h2 {
        font-size: 0.9em;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: #666;
        margin-bottom: 8px;
        font-family: Arial, sans-serif;
    }

    .overview-bar p {
        font-size: 0.95em;
        line-height: 1.6;
        color: #444;
        font-family: Arial, sans-serif;
    }

    .main-layout {
        display: grid;
        grid-template-columns: 1fr 360px;
        gap: 0;
        min-height: calc(100vh - 100px);
    }

    .paper-column {
        background: white;
        padding: 48px;
        border-right: 1px solid #ddd;
        font-size: 1em;
        line-height: 1.8;
    }

    .paper-column p { margin-bottom: 1.2em; }

    .right-column {
        background: #f9f9f9;
        padding: 16px;
        overflow-y: auto;
    }

    .right-column h2 {
        font-size: 0.85em;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: #666;
        margin-bottom: 12px;
        font-family: Arial, sans-serif;
    }

    .annotation-card {
        background: white;
        border-radius: 4px;
        padding: 12px;
        margin-bottom: 10px;
        cursor: pointer;
        transition: box-shadow 0.15s;
        font-family: Arial, sans-serif;
        font-size: 0.85em;
    }

    .annotation-card:hover { box-shadow: 0 2px 8px rgba(0,0,0,0.15); }
    .annotation-card.active { box-shadow: 0 0 0 2px #2c3e50; }

    .card-header {
        display: flex;
        align-items: center;
        gap: 6px;
        margin-bottom: 6px;
        flex-wrap: wrap;
    }

    .card-category { font-weight: bold; font-size: 0.85em; flex: 1; }
    .card-id { color: #999; font-size: 0.8em; }

    .card-rubric-criterion {
        width: 100%;
        font-size: 0.78em;
        color: #555;
        background: #f0f0f0;
        border-radius: 3px;
        padding: 2px 6px;
        margin-bottom: 4px;
        font-style: italic;
    }

    .card-quote {
        color: #666;
        font-style: italic;
        font-size: 0.82em;
        margin-bottom: 6px;
        border-left: 2px solid #ddd;
        padding-left: 8px;
    }

    .card-feedback { line-height: 1.5; color: #333; }

    .suggested-phrasing {
        margin-top: 8px;
        padding-top: 8px;
        border-top: 1px solid #eee;
        font-size: 0.9em;
        color: #555;
    }

    mark.annotation-highlight {
        border-radius: 2px;
        padding: 1px 0;
    }

    mark.annotation-highlight.active { outline: 2px solid #2c3e50; }

    /* Rephrase-mode cards */
    .rephrase-card {
        background: white;
        border-radius: 4px;
        padding: 14px;
        margin-bottom: 12px;
        font-family: Arial, sans-serif;
        font-size: 0.85em;
        border-left: 4px solid #007bff;
    }

    .rephrase-card .option-number {
        font-weight: bold;
        color: #007bff;
        font-size: 0.8em;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 6px;
    }

    .rephrase-card .option-text {
        font-family: Georgia, serif;
        font-size: 1em;
        line-height: 1.6;
        color: #222;
        margin-bottom: 8px;
        padding: 8px;
        background: #f8f9ff;
        border-radius: 3px;
    }

    .rephrase-card .option-changes {
        color: #555;
        font-size: 0.82em;
        line-height: 1.4;
        margin-bottom: 4px;
    }

    .rephrase-card .option-note {
        color: #888;
        font-size: 0.78em;
        font-style: italic;
    }

    .original-passage-box {
        background: #fff8e1;
        border-left: 4px solid #ffc107;
        border-radius: 4px;
        padding: 14px;
        margin-bottom: 16px;
        font-family: Arial, sans-serif;
        font-size: 0.85em;
    }

    .original-passage-box .label {
        font-size: 0.78em;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: #888;
        margin-bottom: 6px;
    }

    .original-passage-box .passage-text {
        font-family: Georgia, serif;
        font-size: 0.95em;
        line-height: 1.6;
        color: #333;
    }

    /* Brainstorm-mode cards */
    .brainstorm-card {
        background: white;
        border-radius: 4px;
        padding: 14px;
        margin-bottom: 10px;
        font-family: Arial, sans-serif;
        font-size: 0.85em;
        border-left: 4px solid #6c757d;
    }

    .brainstorm-card .question-number {
        font-size: 0.75em;
        color: #6c757d;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 6px;
    }

    .brainstorm-card .question-text {
        color: #222;
        line-height: 1.5;
        margin-bottom: 8px;
        font-weight: 500;
    }

    .brainstorm-card .question-purpose {
        color: #888;
        font-size: 0.82em;
        font-style: italic;
        line-height: 1.4;
    }

    .topic-reading-box {
        background: #e8f4fd;
        border-left: 4px solid #17a2b8;
        border-radius: 4px;
        padding: 14px;
        margin-bottom: 16px;
        font-family: Arial, sans-serif;
        font-size: 0.85em;
    }

    .topic-reading-box .label {
        font-size: 0.78em;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: #17a2b8;
        margin-bottom: 6px;
    }

    .topic-reading-box .reading-text {
        color: #333;
        line-height: 1.5;
    }

    @media print {
        .top-bar { position: static; }
        .right-column { display: none; }
        .main-layout { grid-template-columns: 1fr; }
    }
"""

# ── Text processing helpers ───────────────────────────────────────────────────

def find_passage_position(text, quote, threshold=80):
    if quote in text:
        return text.index(quote), len(quote)

    lower_text = text.lower()
    lower_quote = quote.lower()
    if lower_quote in lower_text:
        pos = lower_text.index(lower_quote)
        return pos, len(quote)

    import re
    stripped_quote = quote.rstrip('.,;:!?"\'')
    if stripped_quote in text:
        pos = text.index(stripped_quote)
        end = pos + len(stripped_quote)
        while end < len(text) and text[end] in '.,;:!?"\'':
            end += 1
        return pos, end - pos

    lower_stripped = stripped_quote.lower()
    if lower_stripped in lower_text:
        pos = lower_text.index(lower_stripped)
        end = pos + len(lower_stripped)
        while end < len(text) and text[end] in '.,;:!?"\'':
            end += 1
        return pos, end - pos

    def normalize(s):
        return re.sub(r'[^\w\s]', '', s).lower().strip()

    normalized_quote = normalize(quote)
    words = text.split()
    quote_words = normalized_quote.split()
    quote_word_count = len(quote_words)

    best_ratio = 0
    best_word_start = None
    best_word_end = None

    for i in range(len(words) - quote_word_count + 1):
        window_words = words[i:i + quote_word_count]
        window = ' '.join(window_words)
        ratio = fuzz.ratio(normalized_quote, normalize(window))
        if ratio > best_ratio:
            best_ratio = ratio
            best_word_start = i
            best_word_end = i + quote_word_count

    if best_ratio < threshold or best_word_start is None:
        return None, None

    word_idx = 0
    i = 0
    start_char = None
    end_char = None

    while i < len(text):
        if text[i].isspace():
            i += 1
            continue

        word_start = i
        while i < len(text) and not text[i].isspace():
            i += 1
        word_end = i

        if word_idx == best_word_start:
            start_char = word_start
        if word_idx == best_word_end - 1:
            end_char = word_end
            break

        word_idx += 1

    if start_char is not None and end_char is not None:
        natural_end = start_char + len(quote)
        if natural_end <= len(text) and text[start_char:natural_end].lower() == quote.lower():
            return start_char, len(quote)
        return start_char, end_char - start_char

    return None, None


def convert_newlines(text):
    paragraphs = text.split('\n\n')
    result = []
    for para in paragraphs:
        if para.strip():
            result.append(para.replace('\n', '<br>'))
    return '</p><p>'.join(result)


def build_highlighted_text(paper_text, annotations, highlight_style="annotation"):
    spans = []
    for ann in annotations:
        pos, length = find_passage_position(paper_text, ann['quoted_passage'])
        if pos is not None:
            spans.append((pos, pos + length, ann['id'], ann.get('severity', 'minor')))

    spans.sort(key=lambda x: x[0])
    clean_spans = []
    last_end = 0
    for span in spans:
        if span[0] >= last_end:
            clean_spans.append(span)
            last_end = span[1]

    result = []
    last_pos = 0

    for start, end, ann_id, severity in clean_spans:
        before = paper_text[last_pos:start]
        result.append(convert_newlines(html.escape(before)))

        color = SEVERITY_COLORS.get(severity, "#fff3cd")
        border = SEVERITY_BORDER.get(severity, "#ffc107")
        highlighted = convert_newlines(html.escape(paper_text[start:end]))
        result.append(
            f'<mark class="annotation-highlight" '
            f'data-id="{ann_id}" '
            f'style="background-color:{color}; border-bottom: 2px solid {border}; cursor: pointer;" '
            f'onclick="selectAnnotation({ann_id})">'
            f'{highlighted}'
            f'<sup style="color:{border}; font-size:0.7em;">[{ann_id}]</sup>'
            f'</mark>'
        )
        last_pos = end

    result.append(convert_newlines(html.escape(paper_text[last_pos:])))
    return ''.join(result)


def build_rephrase_highlighted_text(paper_text, original_passage):
    """Highlight just the passage being rephrased in blue."""
    pos, length = find_passage_position(paper_text, original_passage)
    if pos is None:
        return f'<p>{convert_newlines(html.escape(paper_text))}</p>'

    before = html.escape(paper_text[:pos])
    passage = html.escape(paper_text[pos:pos + length])
    after = html.escape(paper_text[pos + length:])

    highlighted = (
        f'<mark style="background-color:#cce5ff; border-bottom: 2px solid #007bff; border-radius: 2px;">'
        f'{convert_newlines(passage)}'
        f'</mark>'
    )
    return f'<p>{convert_newlines(before)}{highlighted}{convert_newlines(after)}</p>'


# ── Card renderers ────────────────────────────────────────────────────────────

def render_annotation_card(ann):
    color = SEVERITY_COLORS.get(ann['severity'], "#fff3cd")
    border = SEVERITY_BORDER.get(ann['severity'], "#ffc107")
    icon = CATEGORY_ICONS.get(ann.get('category', ''), "📌")

    rubric_line = ""
    if ann.get('rubric_criterion'):
        rubric_line = f'<div class="card-rubric-criterion">Rubric: {html.escape(ann["rubric_criterion"])}</div>'

    suggested = ""
    if ann.get('suggested_phrasing'):
        suggested = f"""
        <div class="suggested-phrasing">
            <strong>Suggested phrasing:</strong>
            <em>"{html.escape(ann['suggested_phrasing'])}"</em>
        </div>"""

    return f"""
    <div class="annotation-card"
         id="card-{ann['id']}"
         data-id="{ann['id']}"
         style="border-left: 4px solid {border}; background: {color};"
         onclick="selectAnnotation({ann['id']})">
        <div class="card-header">
            <span class="card-icon">{icon}</span>
            <span class="card-category">{html.escape(ann.get('category', ''))}</span>
            <span class="card-id">[{ann['id']}]</span>
            {rubric_line}
        </div>
        <div class="card-quote">
            "{html.escape(ann['quoted_passage'][:80])}{'...' if len(ann['quoted_passage']) > 80 else ''}"
        </div>
        <div class="card-feedback">
            {html.escape(ann['feedback'])}
        </div>
        {suggested}
    </div>"""


def render_rephrase_card(option):
    return f"""
    <div class="rephrase-card">
        <div class="option-number">Option {option['id']}</div>
        <div class="option-text">{html.escape(option['text'])}</div>
        <div class="option-changes"><strong>What changed:</strong> {html.escape(option['changes'])}</div>
        <div class="option-note">{html.escape(option['note'])}</div>
    </div>"""


def render_brainstorm_card(q):
    return f"""
    <div class="brainstorm-card">
        <div class="question-number">Question {q['id']}</div>
        <div class="question-text">{html.escape(q['question'])}</div>
        <div class="question-purpose">{html.escape(q['purpose'])}</div>
    </div>"""


# ── Page renderers ────────────────────────────────────────────────────────────


def _render_annotated(paper_text, result, filename, mode):
    overview = html.escape(result.get('overview', ''))
    annotations = result.get('annotations', [])

    highlighted_text = build_highlighted_text(paper_text, annotations)
    paper_html = f'<p>{highlighted_text}</p>'
    annotation_cards = ''.join(render_annotation_card(ann) for ann in annotations)

    legend_items = ''.join(
        f'<span class="legend-item" style="background:{color}; border-left: 3px solid {SEVERITY_BORDER[sev]}">{sev.capitalize()}</span>'
        for sev, color in SEVERITY_COLORS.items()
    )

    mode_label = "Rubric Check" if mode == "rubric" else "General Review"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Writing Review — {html.escape(filename)}</title>
    <style>
        {_BASE_CSS}
        /* Cards are absolutely positioned to align with their highlight in the text */
        .right-column {{
            overflow-y: visible;
            position: relative;
            padding: 0;
        }}
        .annotation-card {{
            position: absolute;
            left: 8px;
            right: 8px;
            margin-bottom: 0;
        }}
    </style>
</head>
<body>
    <div class="top-bar">
        <h1>Writing Review — {html.escape(filename)} <span class="mode-badge">{mode_label}</span></h1>
        <div class="legend">
            <span style="color:#aaa; font-family:Arial;">Highlight key:</span>
            {legend_items}
        </div>
    </div>

    <div class="overview-bar">
        <h2>Overview</h2>
        <p>{overview}</p>
    </div>

    <div class="main-layout">
        <div class="paper-column" id="paper-column">
            {paper_html}
        </div>
        <div class="right-column" id="right-col">
            {annotation_cards}
        </div>
    </div>

    <script>
        let activeId = null;

        function selectAnnotation(id) {{
            if (activeId !== null) {{
                const prevMark = document.querySelector(`mark[data-id="${{activeId}}"]`);
                const prevCard = document.getElementById(`card-${{activeId}}`);
                if (prevMark) prevMark.classList.remove('active');
                if (prevCard) prevCard.classList.remove('active');
            }}
            activeId = id;
            const mark = document.querySelector(`mark[data-id="${{id}}"]`);
            const card = document.getElementById(`card-${{id}}`);
            if (mark) {{ mark.classList.add('active'); mark.scrollIntoView({{ behavior: 'smooth', block: 'center' }}); }}
            if (card) card.classList.add('active');
        }}

        function positionCards() {{
            const rightCol = document.getElementById('right-col');
            if (!rightCol) return;
            const scrollY = window.scrollY || document.documentElement.scrollTop;
            const rightColTop = rightCol.getBoundingClientRect().top + scrollY;

            // Collect each card alongside its mark's Y position in the text
            const entries = [];
            document.querySelectorAll('.annotation-card').forEach(card => {{
                const mark = document.querySelector(`mark[data-id="${{card.dataset.id}}"]`);
                const markTop = mark
                    ? mark.getBoundingClientRect().top + scrollY - rightColTop
                    : Infinity;
                entries.push({{ card, markTop }});
            }});

            // Sort by text position so cards appear in the same order as their highlights
            entries.sort((a, b) => a.markTop - b.markTop);

            let minNextTop = 8;
            entries.forEach(({{ card, markTop }}) => {{
                const targetTop = Math.max(Math.floor(markTop), minNextTop);
                card.style.top = targetTop + 'px';
                minNextTop = targetTop + card.offsetHeight + 10;
            }});

            rightCol.style.minHeight = minNextTop + 'px';
        }}

        window.addEventListener('load', () => requestAnimationFrame(positionCards));
        window.addEventListener('resize', positionCards);
    </script>
</body>
</html>"""


def _render_rephrase(paper_text, result, filename):
    original = result.get('original_passage', '')
    context_note = result.get('context_note', '')
    options = result.get('options', [])

    paper_html = build_rephrase_highlighted_text(paper_text, original)
    option_cards = ''.join(render_rephrase_card(o) for o in options)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Rephrasing Options — {html.escape(filename)}</title>
    <style>{_BASE_CSS}</style>
</head>
<body>
    <div class="top-bar">
        <h1>Writing Review — {html.escape(filename)} <span class="mode-badge">Rephrase Options</span></h1>
    </div>

    <div class="overview-bar">
        <h2>Context</h2>
        <p style="font-family:Arial;">{html.escape(context_note)}</p>
    </div>

    <div class="main-layout">
        <div class="paper-column">
            {paper_html}
        </div>
        <div class="right-column">
            <div class="original-passage-box">
                <div class="label">Original passage</div>
                <div class="passage-text">{html.escape(original)}</div>
            </div>
            <h2>4 Rephrasing Options</h2>
            {option_cards}
        </div>
    </div>
</body>
</html>"""


def _render_brainstorm(paper_text, result, filename):
    topic_reading = result.get('topic_reading', '')
    questions = result.get('questions', [])

    paper_html = f'<p>{convert_newlines(html.escape(paper_text))}</p>'
    question_cards = ''.join(render_brainstorm_card(q) for q in questions)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Brainstorm Questions — {html.escape(filename)}</title>
    <style>{_BASE_CSS}</style>
</head>
<body>
    <div class="top-bar">
        <h1>Writing Review — {html.escape(filename)} <span class="mode-badge">Brainstorm</span></h1>
    </div>

    <div class="main-layout">
        <div class="paper-column">
            {paper_html}
        </div>
        <div class="right-column">
            <div class="topic-reading-box">
                <div class="label">How I read your paper</div>
                <div class="reading-text">{html.escape(topic_reading)}</div>
            </div>
            <h2>Questions to explore ({len(questions)})</h2>
            {question_cards}
        </div>
    </div>
</body>
</html>"""


# ── Reading mode renderers ────────────────────────────────────────────────────

def build_reading_annotated_text(paper_text, paragraphs, flat_highlights):
    """Build annotated text as <p> blocks with badge anchors and highlights.

    Anchors are placed based on where highlights actually appear in the text,
    not on excerpt fuzzy-matching. This guarantees the anchor (and therefore
    the positioned card) is always at the same Y level as its highlights.
    Paragraphs with no highlights fall back to excerpt position.
    """
    from collections import defaultdict

    text_paras = paper_text.split('\n\n')

    # Absolute character offset of each text paragraph
    offsets = []
    pos = 0
    for tp in text_paras:
        offsets.append(pos)
        pos += len(tp) + 2

    def tp_index_for_char(char_pos):
        for i, (start, tp) in enumerate(zip(offsets, text_paras)):
            if start <= char_pos < start + len(tp):
                return i
        return None

    # Locate every highlight in the full text by exact/fuzzy quote match
    highlight_char_pos = {}  # hid -> (abs_start, abs_end)
    for h in flat_highlights:
        hpos, hlen = find_passage_position(paper_text, h['quoted_passage'])
        if hpos is not None:
            highlight_char_pos[h['id']] = (hpos, hpos + hlen)

    # Anchor position for each analysis paragraph:
    # use the earliest highlight (exact position), fall back to excerpt match
    para_anchor_char = {}
    for para in paragraphs:
        pid = para['id']
        h_positions = [
            highlight_char_pos[h['id']][0]
            for h in flat_highlights
            if h['para_id'] == pid and h['id'] in highlight_char_pos
        ]
        if h_positions:
            para_anchor_char[pid] = min(h_positions)
        else:
            excerpt = para.get('excerpt', '').strip()
            if excerpt:
                epos, _ = find_passage_position(paper_text, excerpt)
                if epos is not None:
                    para_anchor_char[pid] = epos

    # Map each para_id to the text paragraph index it lands in
    para_id_to_tp = {}
    for pid, char_pos in para_anchor_char.items():
        idx = tp_index_for_char(char_pos)
        if idx is not None:
            para_id_to_tp[pid] = idx

    # Group para_ids by text paragraph, sorted by anchor position
    tp_to_para_ids = defaultdict(list)
    for pid, tp_idx in para_id_to_tp.items():
        tp_to_para_ids[tp_idx].append(pid)
    for tp_idx in tp_to_para_ids:
        tp_to_para_ids[tp_idx].sort(key=lambda pid: para_anchor_char.get(pid, 0))

    # Assign highlights to their text paragraph
    tp_highlights = defaultdict(list)
    for h in flat_highlights:
        if h['id'] not in highlight_char_pos:
            continue
        abs_start, abs_end = highlight_char_pos[h['id']]
        idx = tp_index_for_char(abs_start)
        if idx is not None:
            tp_start = offsets[idx]
            tp_highlights[idx].append({
                **h,
                'rel_start': abs_start - tp_start,
                'rel_end': min(abs_end - tp_start, len(text_paras[idx])),
            })

    # Build one <p> per non-empty text paragraph
    html_parts = []
    for i, tp in enumerate(text_paras):
        if not tp.strip():
            continue

        para_ids_here = tp_to_para_ids.get(i, [])

        raw = sorted(tp_highlights.get(i, []), key=lambda h: h['rel_start'])
        clean, last_end = [], 0
        for h in raw:
            if h['rel_start'] >= last_end:
                clean.append(h)
                last_end = h['rel_end']

        parts = []

        for pid in para_ids_here:
            parts.append(
                f'<span id="para-anchor-{pid}" class="para-anchor-point"></span>'
                f'<span class="para-badge" data-para-id="{pid}" '
                f'onclick="activatePara({pid})">&#182;{pid}</span> '
            )

        cursor = 0
        for h in clean:
            s, e = h['rel_start'], h['rel_end']
            if s > cursor:
                parts.append(html.escape(tp[cursor:s]).replace('\n', '<br>'))
            parts.append(
                f'<mark class="reading-highlight" '
                f'data-id="{h["id"]}" data-para-id="{h["para_id"]}" '
                f'onclick="activatePara({h["para_id"]})">'
                f'{html.escape(tp[s:e]).replace(chr(10), "<br>")}'
                f'<sup class="reading-sup">[{h["id"]}]</sup>'
                f'</mark>'
            )
            cursor = e

        if cursor < len(tp):
            parts.append(html.escape(tp[cursor:]).replace('\n', '<br>'))

        html_parts.append('<p>' + ''.join(parts) + '</p>')

    return '\n'.join(html_parts)


def _render_reading(paper_text, result, filename):
    structure_note = html.escape(result.get('structure_note', ''))
    paragraphs = result.get('paragraphs', [])

    # Flatten highlights with globally unique IDs
    flat_highlights = []
    para_highlights = {}
    for para in paragraphs:
        para_highlights[para['id']] = []
        for h in para.get('highlights', []):
            hid = len(flat_highlights) + 1
            entry = {
                'id': hid,
                'para_id': para['id'],
                'quoted_passage': h['quoted_passage'],
                'reason': h['reason'],
            }
            flat_highlights.append(entry)
            para_highlights[para['id']].append(entry)

    paper_html = build_reading_annotated_text(paper_text, paragraphs, flat_highlights)

    # Build cards (no excerpt — the badge in the text already identifies the paragraph)
    cards_html = ''
    for para in paragraphs:
        highlights_html = ''
        for h in para_highlights.get(para['id'], []):
            short_quote = h['quoted_passage'][:70] + ('...' if len(h['quoted_passage']) > 70 else '')
            highlights_html += f"""
            <div class="reading-highlight-note">
                <span class="highlight-ref">[{h['id']}]</span>
                <span class="highlight-quote">"{html.escape(short_quote)}"</span>
                <div class="highlight-reason">{html.escape(h['reason'])}</div>
            </div>"""

        cards_html += f"""
        <div class="reading-card" id="para-card-{para['id']}" data-para-id="{para['id']}">
            <div class="card-header-row">
                <span class="card-para-pill">&#182;{para['id']}</span>
            </div>
            <div class="card-movement">{html.escape(para.get('movement', ''))}</div>
            {highlights_html}
        </div>"""

    total_highlights = len(flat_highlights)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Reading Analysis — {html.escape(filename)}</title>
    <style>
        {_BASE_CSS}

        /* Reading-mode layout: page scrolls, right column holds absolutely-positioned cards */
        .right-column {{
            overflow-y: visible;
            position: relative;
            padding: 0;
            background: #f0f2f4;
        }}

        /* Badge in text — small pill matching the card pill */
        .para-badge {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            min-width: 22px;
            height: 20px;
            padding: 0 5px;
            background: #dee2e6;
            color: #495057;
            border-radius: 10px;
            font-size: 0.72em;
            font-family: Arial, sans-serif;
            font-weight: bold;
            cursor: pointer;
            vertical-align: middle;
            user-select: none;
            transition: background 0.12s, color 0.12s;
        }}
        .para-badge:hover {{ background: #6c757d; color: white; }}
        .para-badge.active {{ background: #2c3e50; color: white; }}

        /* Highlight marks in text */
        mark.reading-highlight {{
            background-color: #e8f4ff;
            border-bottom: 2px solid #93c5fd;
            border-radius: 2px;
            cursor: pointer;
            padding: 1px 0;
            transition: background-color 0.12s;
        }}
        mark.reading-highlight.active {{
            background-color: #bfdbfe;
            border-bottom-color: #3b82f6;
        }}
        .reading-sup {{
            color: #93c5fd;
            font-size: 0.7em;
            vertical-align: super;
        }}
        mark.reading-highlight.active .reading-sup {{ color: #3b82f6; }}

        /* Cards — absolutely positioned so they align with their paragraph anchor */
        .reading-card {{
            position: absolute;
            left: 8px;
            right: 8px;
            background: white;
            border-radius: 4px;
            padding: 12px;
            font-family: Arial, sans-serif;
            font-size: 0.85em;
            border-left: 3px solid #dee2e6;
            box-shadow: 0 1px 3px rgba(0,0,0,0.08);
            transition: border-color 0.12s, box-shadow 0.12s;
        }}
        .reading-card.active {{
            border-left-color: #2c3e50;
            box-shadow: 0 0 0 2px rgba(44,62,80,0.2);
        }}

        .card-header-row {{
            margin-bottom: 6px;
        }}

        /* Pill in card — same visual as the badge in text, so the match is obvious */
        .card-para-pill {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            min-width: 22px;
            height: 20px;
            padding: 0 5px;
            background: #dee2e6;
            color: #495057;
            border-radius: 10px;
            font-size: 0.72em;
            font-weight: bold;
            transition: background 0.12s, color 0.12s;
        }}
        .reading-card.active .card-para-pill {{
            background: #2c3e50;
            color: white;
        }}

        .card-movement {{
            color: #333;
            line-height: 1.5;
        }}

        .reading-highlight-note {{
            margin-top: 8px;
            padding-top: 8px;
            border-top: 1px solid #eee;
            font-size: 0.88em;
        }}
        .highlight-ref {{
            font-weight: bold;
            color: #93c5fd;
            margin-right: 4px;
        }}
        .reading-card.active .highlight-ref {{ color: #3b82f6; }}
        .highlight-quote {{
            color: #666;
            font-style: italic;
            font-size: 0.88em;
        }}
        .highlight-reason {{
            color: #555;
            margin-top: 4px;
            line-height: 1.4;
        }}
    </style>
</head>
<body>
    <div class="top-bar">
        <h1>Reading Analysis — {html.escape(filename)} <span class="mode-badge">Reading</span></h1>
        {f'<span style="color:#aaa;font-family:Arial;font-size:0.85em;">{total_highlights} passage{"s" if total_highlights!=1 else ""} highlighted</span>' if total_highlights else ''}
    </div>

    <div class="overview-bar">
        <h2>Rhetorical Structure</h2>
        <p>{structure_note}</p>
    </div>

    <div class="main-layout">
        <div class="paper-column">
            {paper_html}
        </div>
        <div class="right-column" id="right-col">
            {cards_html}
        </div>
    </div>

    <script>
        function positionCards() {{
            const rightCol = document.getElementById('right-col');
            if (!rightCol) return;
            const scrollY = window.scrollY || document.documentElement.scrollTop;
            const rightColTop = rightCol.getBoundingClientRect().top + scrollY;

            let minNextTop = 8;
            document.querySelectorAll('.reading-card').forEach(card => {{
                const paraId = card.dataset.paraId;
                const anchor = document.getElementById('para-anchor-' + paraId);
                let targetTop = minNextTop;
                if (anchor) {{
                    const relTop = anchor.getBoundingClientRect().top + scrollY - rightColTop;
                    targetTop = Math.max(Math.floor(relTop), minNextTop);
                }}
                card.style.top = targetTop + 'px';
                minNextTop = targetTop + card.offsetHeight + 10;
            }});

            rightCol.style.minHeight = minNextTop + 'px';
        }}

        function activatePara(paraId) {{
            document.querySelectorAll('.reading-card').forEach(c => c.classList.remove('active'));
            document.querySelectorAll('.para-badge').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('mark.reading-highlight').forEach(m => m.classList.remove('active'));

            const card = document.getElementById('para-card-' + paraId);
            if (card) card.classList.add('active');

            const badge = document.querySelector('.para-badge[data-para-id="' + paraId + '"]');
            if (badge) badge.classList.add('active');

            document.querySelectorAll('mark.reading-highlight[data-para-id="' + paraId + '"]')
                .forEach(m => m.classList.add('active'));
        }}

        window.addEventListener('load', () => requestAnimationFrame(positionCards));
        window.addEventListener('resize', positionCards);
    </script>
</body>
</html>"""


# ── Public entry point ────────────────────────────────────────────────────────

def render_full_document(paper_text, analysis_result, filename="document", mode="general"):
    if mode == "reading":
        return _render_reading(paper_text, analysis_result, filename)
    elif mode == "rephrase":
        return _render_rephrase(paper_text, analysis_result, filename)
    elif mode == "brainstorm":
        return _render_brainstorm(paper_text, analysis_result, filename)
    else:
        return _render_annotated(paper_text, analysis_result, filename, mode)
