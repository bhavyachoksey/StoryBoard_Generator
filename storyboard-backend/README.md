# StoryBoard Backend

Pipeline: script (text or PDF) → Gemini 3.1 Pro (characters + prompts) → Nano Banana Pro (character images) → user approval → save to JSON → Gemini (scene prompts) → Nano Banana (scene images with character refs). On page refresh, reset clears the stored JSON.

## Setup

- Python 3.9+
- `pip install -r requirements.txt`
- Create `.env` with `PORT`, `GCP_PROJECT_ID`, `GCP_LOCATION` (same as other backends).

## Embedded models

- **gemini_embedded.py** — Gemini 3.1 Pro: `generate(prompt)` returns text. main.py builds prompts and parses JSON for characters and scenes.
- **nano_banana_embedded.py** — Gemini 3 Pro Image: `generate_character_image(prompt)` and `generate_scene_image(prompt, refs, style)` return base64 PNG.

## Entry point

- **main.py** — Reads JSON from stdin: `{ "action": "<action>", ... }`. Actions:
  - `extract_script` — PDF or text → `scriptText`
  - `get_characters` — script + style → character list with images
  - `regenerate_character` — name, feedback, etc. → single character image
  - `approve` — save approved characters to `characters.json`
  - `generate_scenes` — script + style → scene images (uses saved characters)
  - `reset` — delete `characters.json` (call on page refresh)

The Node server (festival-calendar-backend) mounts these as `/api/storyboard/*` routes and spawns `main.py` with the corresponding payload.
