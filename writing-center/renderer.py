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

def find_passage_position(text, quote, threshold=80):
    # Try exact match first
    if quote in text:
        return text.index(quote), len(quote)
    
    # Try case-insensitive exact match
    lower_text = text.lower()
    lower_quote = quote.lower()
    if lower_quote in lower_text:
        pos = lower_text.index(lower_quote)
        return pos, len(quote)

    # Try stripping trailing punctuation from quote and finding in text
    import re
    stripped_quote = quote.rstrip('.,;:!?"\'')
    if stripped_quote in text:
        pos = text.index(stripped_quote)
        # Extend match to include any punctuation that follows
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

    # Fuzzy match fallback at word boundaries
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

    # Walk text to find character positions at word boundaries
    char_pos = 0
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
        # Try to use original quote length if it fits cleanly
        natural_end = start_char + len(quote)
        if natural_end <= len(text) and text[start_char:natural_end].lower() == quote.lower():
            return start_char, len(quote)
        return start_char, end_char - start_char

    return None, None

def build_highlighted_text(paper_text, annotations):
    # Build list of (start, end, annotation_id, severity) sorted by position
    spans = []
    for ann in annotations:
        pos, length = find_passage_position(paper_text, ann['quoted_passage'])
        if pos is not None:
            spans.append((pos, pos + length, ann['id'], ann['severity']))

    # Sort by start position, remove overlaps
    spans.sort(key=lambda x: x[0])
    clean_spans = []
    last_end = 0
    for span in spans:
        if span[0] >= last_end:
            clean_spans.append(span)
            last_end = span[1]

    # Build HTML in a single pass over the original text
    # handling both highlights and newline conversion together
    result = []
    last_pos = 0

    for start, end, ann_id, severity in clean_spans:
        # Add text before highlight, converting newlines to <br>
        before = paper_text[last_pos:start]
        result.append(convert_newlines(before))

        # Add highlighted passage, converting newlines inside highlight too
        color = SEVERITY_COLORS.get(severity, "#fff3cd")
        border = SEVERITY_BORDER.get(severity, "#ffc107")
        highlighted = convert_newlines(html.escape(paper_text[start:end]))
        result.append(
            f'<mark class="annotation-highlight" '
            f'data-id="{ann_id}" '
            f'style="background-color:{color}; '
            f'border-bottom: 2px solid {border}; '
            f'cursor: pointer;" '
            f'onclick="selectAnnotation({ann_id})">'
            f'{highlighted}'
            f'<sup style="color:{border}; font-size:0.7em;">[{ann_id}]</sup>'
            f'</mark>'
        )
        last_pos = end

    # Add remaining text
    result.append(convert_newlines(html.escape(paper_text[last_pos:])))
    
    return ''.join(result)

def convert_newlines(text):
    # Convert double newlines to paragraph breaks, single to <br>
    # This operates on already-escaped text so we don't double-escape
    paragraphs = text.split('\n\n')
    result = []
    for para in paragraphs:
        if para.strip():
            result.append(para.replace('\n', '<br>'))
    return '</p><p>'.join(result)

def render_annotation_card(ann):
    color = SEVERITY_COLORS.get(ann['severity'], "#fff3cd")
    border = SEVERITY_BORDER.get(ann['severity'], "#ffc107")
    icon = CATEGORY_ICONS.get(ann['category'], "📌")
    
    suggested = ""
    if ann.get('suggested_phrasing'):
        suggested = f"""
        <div class="suggested-phrasing">
            <strong>Suggested phrasing:</strong>
            <em>"{html.escape(ann['suggested_phrasing'])}"</em>
        </div>
        """

    return f"""
    <div class="annotation-card" 
         id="card-{ann['id']}" 
         data-id="{ann['id']}"
         style="border-left: 4px solid {border}; background: {color};"
         onclick="selectAnnotation({ann['id']})">
        <div class="card-header">
            <span class="card-icon">{icon}</span>
            <span class="card-category">{html.escape(ann['category'])}</span>
            <span class="card-id">[{ann['id']}]</span>
        </div>
        <div class="card-quote">
            "{html.escape(ann['quoted_passage'][:80])}{'...' if len(ann['quoted_passage']) > 80 else ''}"
        </div>
        <div class="card-feedback">
            {html.escape(ann['feedback'])}
        </div>
        {suggested}
    </div>
    """

def render_full_document(paper_text, analysis_result, filename="document"):
    overview = html.escape(analysis_result.get('overview', ''))
    annotations = analysis_result.get('annotations', [])
    
    highlighted_text = build_highlighted_text(paper_text, annotations)
    
    # Convert newlines to paragraphs
    paragraphs = highlighted_text.split('\n\n')
    highlighted_text = build_highlighted_text(paper_text, annotations)
    
    # Wrap in paragraph tags
    paper_html = f'<p>{highlighted_text}</p>'
    
    annotation_cards = ''.join(render_annotation_card(ann) for ann in annotations)

    legend_items = ''.join(
        f'<span class="legend-item" style="background:{color}; border-left: 3px solid {SEVERITY_BORDER[sev]}">{sev.capitalize()}</span>'
        for sev, color in SEVERITY_COLORS.items()
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Writing Review — {html.escape(filename)}</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        
        body {{
            font-family: Georgia, serif;
            background: #f5f5f5;
            color: #333;
        }}

        .top-bar {{
            background: #2c3e50;
            color: white;
            padding: 12px 24px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            position: sticky;
            top: 0;
            z-index: 100;
        }}

        .top-bar h1 {{
            font-size: 1.1em;
            font-weight: normal;
        }}

        .legend {{
            display: flex;
            gap: 8px;
            align-items: center;
            font-size: 0.8em;
        }}

        .legend-item {{
            padding: 2px 8px;
            border-radius: 3px;
            font-family: Arial, sans-serif;
        }}

        .overview-bar {{
            background: white;
            border-bottom: 1px solid #ddd;
            padding: 16px 24px;
        }}

        .overview-bar h2 {{
            font-size: 0.9em;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: #666;
            margin-bottom: 8px;
            font-family: Arial, sans-serif;
        }}

        .overview-bar p {{
            font-size: 0.95em;
            line-height: 1.6;
            color: #444;
            font-family: Arial, sans-serif;
        }}

        .main-layout {{
            display: grid;
            grid-template-columns: 1fr 340px;
            gap: 0;
            min-height: calc(100vh - 100px);
        }}

        .paper-column {{
            background: white;
            padding: 48px;
            border-right: 1px solid #ddd;
            font-size: 1em;
            line-height: 1.8;
        }}

        .paper-column p {{
            margin-bottom: 1.2em;
        }}

        .annotations-column {{
            background: #f9f9f9;
            padding: 16px;
            overflow-y: auto;
        }}

        .annotations-column h2 {{
            font-size: 0.85em;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: #666;
            margin-bottom: 12px;
            font-family: Arial, sans-serif;
        }}

        .annotation-card {{
            background: white;
            border-radius: 4px;
            padding: 12px;
            margin-bottom: 10px;
            cursor: pointer;
            transition: box-shadow 0.15s;
            font-family: Arial, sans-serif;
            font-size: 0.85em;
        }}

        .annotation-card:hover {{
            box-shadow: 0 2px 8px rgba(0,0,0,0.15);
        }}

        .annotation-card.active {{
            box-shadow: 0 0 0 2px #2c3e50;
        }}

        .card-header {{
            display: flex;
            align-items: center;
            gap: 6px;
            margin-bottom: 6px;
        }}

        .card-category {{
            font-weight: bold;
            font-size: 0.85em;
            flex: 1;
        }}

        .card-id {{
            color: #999;
            font-size: 0.8em;
        }}

        .card-quote {{
            color: #666;
            font-style: italic;
            font-size: 0.82em;
            margin-bottom: 6px;
            border-left: 2px solid #ddd;
            padding-left: 8px;
        }}

        .card-feedback {{
            line-height: 1.5;
            color: #333;
        }}

        .suggested-phrasing {{
            margin-top: 8px;
            padding-top: 8px;
            border-top: 1px solid #eee;
            font-size: 0.9em;
            color: #555;
        }}

        mark.annotation-highlight {{
            border-radius: 2px;
            padding: 1px 0;
        }}

        mark.annotation-highlight.active {{
            outline: 2px solid #2c3e50;
        }}

        @media print {{
            .top-bar {{ position: static; }}
            .annotations-column {{ display: none; }}
            .main-layout {{ grid-template-columns: 1fr; }}
        }}
    </style>
</head>
<body>
    <div class="top-bar">
        <h1>Writing Review — {html.escape(filename)}</h1>
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
        <div class="annotations-column">
            <h2>Annotations ({len(annotations)})</h2>
            {annotation_cards}
        </div>
    </div>

    <script>
        let activeId = null;

        function selectAnnotation(id) {{
            // Deactivate previous
            if (activeId !== null) {{
                const prevMark = document.querySelector(`mark[data-id="${{activeId}}"]`);
                const prevCard = document.getElementById(`card-${{activeId}}`);
                if (prevMark) prevMark.classList.remove('active');
                if (prevCard) prevCard.classList.remove('active');
            }}

            // Activate new
            activeId = id;
            const mark = document.querySelector(`mark[data-id="${{id}}"]`);
            const card = document.getElementById(`card-${{id}}`);
            
            if (mark) {{
                mark.classList.add('active');
                mark.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
            }}
            if (card) {{
                card.classList.add('active');
                card.scrollIntoView({{ behavior: 'smooth', block: 'nearest' }});
            }}
        }}
    </script>
</body>
</html>"""
