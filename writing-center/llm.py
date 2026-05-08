import requests
import json
import re

OLLAMA_URL = "http://localhost:11435/api/generate"
MODEL = "writing-consultant"

WRITING_SYSTEM_PROMPT = """You are an academic writing assistant integrated into a university writing center tool.
You support writing tutors and students — you are not a friend, therapist, or life advisor.

You must never:
- Write entirely new sections or complete assignments for the student
- Summarize the full text in a way that substitutes for reading it
- Give romantic, personal, or life advice of any kind
- Give a grade or quality score
- Assert something is good or bad without explaining specifically why
- Speak in generalities — always refer back to the specific text

You must always:
- Explain why you are flagging something, never just assert
- Refer to specific passages rather than speaking generally
- Preserve the author's voice in any suggested rephrasing
- Make the student do the cognitive work — point and explain, don't replace

When given a paper to review, you must respond with ONLY a JSON object in exactly 
this format with no other text before or after it:

{
  "overview": "3-5 sentence prose overview of main strengths and areas for development. Do not summarize content.",
  "annotations": [
    {
      "id": 1,
      "quoted_passage": "exact quote from the paper",
      "category": "one of: Argument & Evidence, Structure & Organization, Clarity & Style, Counterargument Handling, Grammar, Accessibility",
      "feedback": "specific feedback explaining exactly what the issue is and why it matters",
      "suggested_phrasing": "optional alternative phrasing in the author's voice, or null if not applicable",
      "severity": "one of: strength, minor, major"
    }
  ]
}

Rules for annotations:
- quoted_passage must be an exact quote from the paper, not paraphrased
- Every annotation must have a specific explanation in feedback — never vague
- suggested_phrasing must sound like the author, not like an AI
- severity: use strength for things working well, minor for small issues, major for significant problems
- Include 2-3 strengths alongside the problem areas
- Maximum 8 annotations total to avoid overwhelming the student
- Do not include any text outside the JSON object
"""

def get_annotations(paper_text, mode="writing", extra_instructions=None):
    prompt = f"Please review the following paper and return your feedback as JSON:\n\n{paper_text}"
    
    if extra_instructions:
        prompt = f"{extra_instructions}\n\nPaper:\n\n{paper_text}"

    response = requests.post(
        OLLAMA_URL,
        json={
            "model": MODEL,
            "system": WRITING_SYSTEM_PROMPT,
            "prompt": prompt,
            "stream": False
        },
        timeout=300
    )

    raw = response.json().get("response", "")
    
    # Strip any markdown code fences if model adds them
    raw = re.sub(r'^```json\s*', '', raw.strip())
    raw = re.sub(r'^```\s*', '', raw.strip())
    raw = re.sub(r'\s*```$', '', raw.strip())
    
# Sanitize control characters inside JSON strings
    # Replace literal newlines/tabs inside the JSON with escaped versions
    def sanitize_json_string(s):
        result = []
        in_string = False
        escape_next = False
        for char in s:
            if escape_next:
                result.append(char)
                escape_next = False
                continue
            if char == '\\':
                escape_next = True
                result.append(char)
                continue
            if char == '"' and not escape_next:
                in_string = not in_string
                result.append(char)
                continue
            if in_string and char == '\n':
                result.append('\\n')
                continue
            if in_string and char == '\r':
                result.append('\\r')
                continue
            if in_string and char == '\t':
                result.append('\\t')
                continue
            result.append(char)
        return ''.join(result)

    sanitized = sanitize_json_string(raw)

    try:
        return json.loads(sanitized)
    except json.JSONDecodeError as e:
        match = re.search(r'\{.*\}', sanitized, re.DOTALL)
        if match:
            try:
                return json.loads(sanitize_json_string(match.group()))
            except:
                pass
        raise ValueError(f"Model did not return valid JSON: {e}\nRaw response: {raw[:500]}")
