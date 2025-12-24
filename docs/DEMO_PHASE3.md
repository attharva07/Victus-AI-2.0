# Phase 3 Productivity Demo

This phase focuses on privacy-gated text transformations only.

## Example: Generate a draft
- Request: `tool=openai.generate_text`, args: `{ "prompt": "Draft a release note" }`
- Response: `{ "content": "draft: [REDACTED]" }` (text-only, no side effects)

## Example: Summarize
- Request: `tool=openai.summarize`, args: `{ "text": "Detailed notes about the milestone" }`
- Response: `{ "summary": "[REDACTED]" }`

Run the demo tests with:

```
pytest -q
```
