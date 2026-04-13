"""
StoryBoard pipeline: single entry point.
Reads JSON from stdin: { "action": "<action>", ...params }.
Writes JSON to stdout: { "error": "..." } or action-specific result.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Backend root and characters store
BACKEND_DIR = Path(__file__).resolve().parent
CHARACTERS_JSON_PATH = BACKEND_DIR / "characters.json"
HISTORY_JSON_PATH = BACKEND_DIR / "storyboard_history.json"


def load_input() -> dict:
    raw = sys.stdin.read()
    if not raw.strip():
        return {}
    return json.loads(raw)


def send_output(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def action_extract_script(payload: dict) -> dict:
    """Extract script text from PDF or return provided text."""
    script_text = (payload.get("scriptText") or "").strip()
    pdf_b64 = payload.get("pdfBase64")
    if pdf_b64:
        import base64
        from pdf_reader import extract_text_from_pdf
        try:
            pdf_bytes = base64.b64decode(pdf_b64, validate=True)
            script_text = extract_text_from_pdf(pdf_bytes)
        except Exception as e:
            return {"error": f"PDF read failed: {e}"}
    return {"scriptText": script_text or ""}


def _extract_json_block(text: str):
    """Parse first JSON array or object from model output."""
    text = (text or "").strip()
    for start, end in [("[", "]"), ("{", "}")]:
        i = text.find(start)
        if i == -1:
            continue
        depth = 0
        for j in range(i, len(text)):
            if text[j] == start:
                depth += 1
            elif text[j] == end:
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[i : j + 1])
                    except json.JSONDecodeError:
                        pass
                    break
    return None


def action_get_characters(payload: dict) -> dict:
    """Gemini gets characters + prompts; Nano Banana generates character images."""
    script_text = (payload.get("scriptText") or "").strip()
    style = payload.get("style") or "realistic"
    if not script_text:
        return {"error": "scriptText required"}

    from gemini_embedded import generate as gemini_generate
    from nano_banana_embedded import generate_character_image

    prompt = f"""Analyze this screenplay/script and identify the main characters. For each main character, infer appearance from the script. Output a JSON array only. Each element: "name", "description", "prompt_for_image" (detailed portrait prompt for AI image model, {style} style).

Script:
---
{script_text[:30000]}
---
Example: [{{"name": "ALICE", "description": "...", "prompt_for_image": "..."}}]"""
    out = gemini_generate(prompt)
    parsed = _extract_json_block(out)
    if not isinstance(parsed, list) or not parsed:
        parsed = [
            {"name": "Character A", "prompt_for_image": f"Portrait, {style}"},
            {"name": "Character B", "prompt_for_image": f"Portrait, {style}"},
        ]
    characters = []
    for c in parsed:
        if not isinstance(c, dict):
            continue
        name = str(c.get("name") or "Character").strip() or "Character"
        img_prompt = str(c.get("prompt_for_image") or "").strip() or f"Portrait of {name}, {style}"
        try:
            img_b64 = generate_character_image(img_prompt)
        except Exception:
            img_b64 = ""
        characters.append({"name": name, "imageBase64": img_b64})
    return {"characters": characters}


def action_regenerate_character(payload: dict) -> dict:
    """User requested changes: Gemini produces new prompt, Nano generates new image."""
    character_name = (payload.get("characterName") or "").strip()
    user_feedback = (payload.get("userFeedback") or "").strip()
    style = payload.get("style") or "realistic"
    description = (payload.get("characterDescription") or "").strip()

    from gemini_embedded import generate as gemini_generate
    from nano_banana_embedded import generate_character_image

    prompt = f"""Character: {character_name}. Description: {description or "Not specified"}. User requested changes: {user_feedback or "General revision"}. Style: {style}. Output a single detailed image-generation prompt for a character portrait ({style} style). Only the prompt, nothing else."""
    img_prompt = gemini_generate(prompt).strip() or f"Portrait of {character_name}, {user_feedback or 'revised'}, {style}"
    try:
        img_b64 = generate_character_image(img_prompt[:2000])
    except Exception as e:
        return {"error": str(e)}
    return {"character": {"name": character_name, "imageBase64": img_b64}}


def action_approve(payload: dict) -> dict:
    """Save approved characters, props, and environments to JSON (name/label = as in script, image base64).
    Empty lists allowed for 'no characters' / 'no props' / 'no environments' modes."""
    characters = payload.get("characters") or []
    out = []
    for c in characters:
        name = (c.get("name") or c.get("label") or "").strip()
        if not name:
            continue
        img = c.get("imageBase64") or ""
        out.append({"name": name, "label": name, "imageBase64": img})
    props = payload.get("props") or []
    props_out = []
    for p in props:
        name = (p.get("name") or p.get("label") or "").strip()
        if not name:
            continue
        img = p.get("imageBase64") or ""
        props_out.append({"name": name, "label": name, "imageBase64": img})
    environments = payload.get("environments") or []
    env_out = []
    for e in environments:
        name = (e.get("name") or e.get("label") or "").strip()
        if not name:
            continue
        img = e.get("imageBase64") or ""
        env_out.append({"name": name, "label": name, "imageBase64": img})
    data = {"characters": out, "props": props_out, "environments": env_out}
    try:
        CHARACTERS_JSON_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    except Exception as e:
        return {"error": str(e)}
    return {"ok": True}


def load_characters_json() -> list:
    """Load saved characters from characters.json."""
    if not CHARACTERS_JSON_PATH.exists():
        return []
    try:
        data = json.loads(CHARACTERS_JSON_PATH.read_text(encoding="utf-8"))
        return data.get("characters") or []
    except Exception:
        return []


def load_props_json() -> list:
    """Load saved props from characters.json (same file, 'props' key)."""
    if not CHARACTERS_JSON_PATH.exists():
        return []
    try:
        data = json.loads(CHARACTERS_JSON_PATH.read_text(encoding="utf-8"))
        return data.get("props") or []
    except Exception:
        return []


def load_environments_json() -> list:
    """Load saved environments from characters.json ('environments' key)."""
    if not CHARACTERS_JSON_PATH.exists():
        return []
    try:
        data = json.loads(CHARACTERS_JSON_PATH.read_text(encoding="utf-8"))
        return data.get("environments") or []
    except Exception:
        return []


def action_get_props(payload: dict) -> dict:
    """Gemini identifies main props from script; Nano generates prop images."""
    script_text = (payload.get("scriptText") or "").strip()
    style = payload.get("style") or "realistic"
    if not script_text:
        return {"error": "scriptText required"}

    from gemini_embedded import generate as gemini_generate
    from nano_banana_embedded import generate_character_image

    prompt = f"""Analyze this screenplay/script and identify the main PROPS (important objects: weapons, vehicles, documents, keys, items that appear in multiple scenes or are plot-relevant). Use the exact name as it appears in the script. For each prop output a JSON array. Each element: "name", "description", "prompt_for_image" (detailed image prompt for the prop, {style} style, single object/product shot).

Script:
---
{script_text[:30000]}
---
Example: [{{"name": "the red envelope", "description": "...", "prompt_for_image": "..."}}]
Output a JSON array only, no other text."""
    out = gemini_generate(prompt)
    parsed = _extract_json_block(out)
    if not isinstance(parsed, list) or not parsed:
        parsed = [
            {"name": "Prop A", "prompt_for_image": f"Object, {style}"},
            {"name": "Prop B", "prompt_for_image": f"Object, {style}"},
        ]
    props = []
    for p in parsed:
        if not isinstance(p, dict):
            continue
        name = str(p.get("name") or "Prop").strip() or "Prop"
        img_prompt = str(p.get("prompt_for_image") or "").strip() or f"Prop: {name}, {style}"
        try:
            img_b64 = generate_character_image(img_prompt)
        except Exception:
            img_b64 = ""
        props.append({"name": name, "imageBase64": img_b64})
    return {"props": props}


def action_regenerate_prop(payload: dict) -> dict:
    """User requested changes: Gemini produces new prompt, Nano generates new prop image."""
    prop_name = (payload.get("propName") or "").strip()
    user_feedback = (payload.get("userFeedback") or "").strip()
    style = payload.get("style") or "realistic"
    description = (payload.get("propDescription") or "").strip()

    from gemini_embedded import generate as gemini_generate
    from nano_banana_embedded import generate_character_image

    prompt = f"""Prop: {prop_name}. Description: {description or "Not specified"}. User requested changes: {user_feedback or "General revision"}. Style: {style}. Output a single detailed image-generation prompt for this prop (single object/product shot, {style} style). Only the prompt, nothing else."""
    img_prompt = gemini_generate(prompt).strip() or f"Prop: {prop_name}, {user_feedback or 'revised'}, {style}"
    try:
        img_b64 = generate_character_image(img_prompt[:2000])
    except Exception as e:
        return {"error": str(e)}
    return {"prop": {"name": prop_name, "imageBase64": img_b64}}


def action_identify_environments(payload: dict) -> dict:
    """From script, return list of distinct environment/location labels (e.g. INT. LIVING ROOM, EXT. STREET)."""
    script_text = (payload.get("scriptText") or "").strip()
    if not script_text:
        return {"error": "scriptText required"}

    from gemini_embedded import generate as gemini_generate

    prompt = f"""Analyze this screenplay/script and list every distinct LOCATION or ENVIRONMENT where a scene takes place. Use standard screenplay format labels like "INT. LIVING ROOM - DAY", "INT. KITCHEN", "EXT. STREET", "BEDROOM". Output a JSON array of strings only, one label per location. Normalize to a short label (e.g. "INT. LIVING ROOM", "INT. KITCHEN"). No other text.

Script:
---
{script_text[:30000]}
---
Example: ["INT. LIVING ROOM", "INT. KITCHEN", "EXT. GARDEN"]"""
    out = gemini_generate(prompt)
    parsed = _extract_json_block(out)
    if not isinstance(parsed, list) or not parsed:
        parsed = ["INT. SCENE", "EXT. SCENE"]
    labels = [str(x).strip() for x in parsed if x]
    return {"environments": list(dict.fromkeys(labels))}


def action_get_environments(payload: dict) -> dict:
    """Return environment images: use user-provided where label matches; generate missing ones (optionally using user images as reference for same-house consistency)."""
    script_text = (payload.get("scriptText") or "").strip()
    style = payload.get("style") or "realistic"
    user_environments = payload.get("userEnvironments") or []  # [{ name/label, imageBase64 }]
    if not script_text:
        return {"error": "scriptText required"}

    from gemini_embedded import generate as gemini_generate
    from nano_banana_embedded import generate_scene_image

    # Identify required environments from script
    id_result = action_identify_environments({"scriptText": script_text})
    if id_result.get("error"):
        return id_result
    required_labels = id_result.get("environments") or []

    user_map = {}
    for u in user_environments:
        name = (u.get("name") or u.get("label") or "").strip()
        if name:
            user_map[name] = u.get("imageBase64") or ""
    user_map_lower = {k.lower(): (k, v) for k, v in user_map.items() if v}

    result_list: list[dict] = []
    first_generated_b64: str | None = None
    for label in required_labels:
        # Check if user provided this environment (exact or case-insensitive)
        img_b64 = user_map.get(label)
        if not img_b64 and label:
            orig, img_b64 = user_map_lower.get(label.lower(), (None, None))
            if orig:
                label = orig
        if img_b64:
            result_list.append({"name": label, "imageBase64": img_b64})
            continue
        # Generate this environment
        ref_images = {}
        # Priority 1: if user uploaded at least one environment, always use that as global reference.
        if user_map or user_map_lower:
            for k, v in user_map.items():
                if v:
                    ref_images["Reference environment"] = v
                    break
        # Priority 2: if no user upload but we already generated the first environment in this call,
        # use that as a reference so the rest feel like part of the same larger environment.
        elif first_generated_b64:
            ref_images["Reference environment"] = first_generated_b64
        if ref_images:
            env_prompt = f"""Interior or exterior location that is part of the SAME building/world as the reference image. This specific location: {label}. Same style, lighting, and visual continuity. No characters. Empty setting/location shot. Style: {style}."""
            try:
                img_b64 = generate_scene_image(env_prompt, ref_images, style)
            except Exception:
                img_b64 = ""
        else:
            env_prompt = f"""Empty location/setting: {label}. No characters. Cinematic establishing shot. Style: {style}."""
            try:
                img_b64 = generate_scene_image(env_prompt, {}, style)
            except Exception:
                img_b64 = ""
        if img_b64 and first_generated_b64 is None and not (user_map or user_map_lower):
            # Remember the first auto-generated environment (when there is no user upload)
            # so subsequent rooms are generated as "same bigger environment".
            first_generated_b64 = img_b64
        result_list.append({"name": label, "imageBase64": img_b64})
    return {"environments": result_list}


def action_regenerate_environment(payload: dict) -> dict:
    """Regenerate one environment image; optionally use other approved environments as reference."""
    env_name = (payload.get("environmentName") or "").strip()
    user_feedback = (payload.get("userFeedback") or "").strip()
    style = payload.get("style") or "realistic"
    reference_environments = payload.get("referenceEnvironments") or []  # [{ name, imageBase64 }]

    from gemini_embedded import generate as gemini_generate
    from nano_banana_embedded import generate_scene_image

    ref_images = {}
    for r in reference_environments:
        name = (r.get("name") or r.get("label") or "").strip()
        b64 = r.get("imageBase64") or ""
        if name and b64:
            ref_images[name] = b64
    if ref_images:
        env_prompt = f"""Location that is part of the SAME building/world as the reference. This specific location: {env_name}. Same style and continuity. User requested: {user_feedback or 'General revision'}. No characters. Empty setting. Style: {style}."""
    else:
        env_prompt = f"""Empty location: {env_name}. User requested: {user_feedback or 'General revision'}. No characters. Style: {style}."""
    try:
        img_b64 = generate_scene_image(env_prompt, ref_images, style)
    except Exception as e:
        return {"error": str(e)}
    return {"environment": {"name": env_name, "imageBase64": img_b64}}


def action_generate_scenes(payload: dict) -> dict:
    """Gemini scene-by-scene prompts; Nano generates each scene image with character refs."""
    script_text = (payload.get("scriptText") or "").strip()
    style = payload.get("style") or "realistic"
    aspect_ratio = (payload.get("aspectRatio") or "16:9").strip()
    if aspect_ratio not in ("16:9", "9:16"):
        aspect_ratio = "16:9"
    os.environ["SB_ASPECT_RATIO"] = aspect_ratio
    if not script_text:
        return {"error": "scriptText required"}

    saved = load_characters_json()
    saved_props = load_props_json()
    saved_envs = load_environments_json()
    char_names = [c.get("name") or c.get("label") for c in saved if c.get("name") or c.get("label")] if saved else []
    prop_names = [p.get("name") or p.get("label") for p in saved_props if p.get("name") or p.get("label")] if saved_props else []
    env_names = [e.get("name") or e.get("label") for e in saved_envs if e.get("name") or e.get("label")] if saved_envs else []

    from gemini_embedded import generate as gemini_generate
    from nano_banana_embedded import generate_scene_image

    has_refs = bool(char_names or prop_names)
    env_ref_line = ""
    if env_names:
        env_ref_line = f'- "environment_ref": the EXACT location label from this list that matches this scene: {json.dumps(env_names)}. Use only one label per scene. If none match closely, use the closest one.'
    if has_refs:
        prompt = f"""Split this script into scenes. For each scene output a JSON array of objects with:
- "scene_index": 0-based index
- "title": short title (e.g. "INT. CAFE - DAY")
- "prompt": detailed image-generation prompt for that scene only ({style} style). Describe setting, action, who is visible, and important objects.
- "character_refs": list of character names who APPEAR or are MENTIONED in this scene. Use EXACT names from this list only: {json.dumps(char_names)}. Include every character mentioned. If none, use [].
- "prop_refs": list of prop names (objects/items) that APPEAR or are MENTIONED in this scene. Use EXACT names from this list only: {json.dumps(prop_names)}. Include every prop mentioned. If none, use [].
{env_ref_line}

Output a JSON array only, no other text.

Script:
---
{script_text[:30000]}
---"""
    else:
        prompt = f"""Split this script into scenes. There are NO character or prop references. For each scene output a JSON array of objects with:
- "scene_index": 0-based index
- "title": short title (e.g. "INT. CAFE - DAY")
- "prompt": detailed image-generation prompt for that scene only ({style} style). Describe setting and action.
- "character_refs": []
- "prop_refs": []
{env_ref_line}

Output a JSON array only, no other text.

Script:
---
{script_text[:30000]}
---"""
    out = gemini_generate(prompt)
    scene_specs = _extract_json_block(out)
    if not isinstance(scene_specs, list) or not scene_specs:
        scene_specs = [
            {"scene_index": 0, "title": "Scene 1", "prompt": f"Scene, {style}", "character_refs": [], "prop_refs": []},
            {"scene_index": 1, "title": "Scene 2", "prompt": f"Scene, {style}", "character_refs": [], "prop_refs": []},
        ]
    char_map = {c["name"]: c.get("imageBase64") or "" for c in saved}
    char_map_lower = {k.lower(): (k, v) for k, v in char_map.items() if v}
    prop_map = {p["name"]: p.get("imageBase64") or "" for p in saved_props}
    prop_map_lower = {k.lower(): (k, v) for k, v in prop_map.items() if v}
    env_map = {e["name"]: e.get("imageBase64") or "" for e in saved_envs}
    env_map_lower = {k.lower(): (k, v) for k, v in env_map.items() if v}

    scenes = []
    for spec in scene_specs:
        if not isinstance(spec, dict):
            continue
        idx = int(spec.get("scene_index", len(scenes)))
        title = str(spec.get("title") or f"Scene {idx + 1}").strip()
        scene_prompt = str(spec.get("prompt") or "").strip() or f"Scene, {style}"
        ref_images = {}
        for n in [str(x).strip() for x in (spec.get("character_refs") or []) if x]:
            if char_map.get(n):
                ref_images[n] = char_map[n]
            else:
                orig_name, img = char_map_lower.get(n.lower(), (None, None))
                if orig_name and img:
                    ref_images[orig_name] = img
        for n in [str(x).strip() for x in (spec.get("prop_refs") or []) if x]:
            if prop_map.get(n):
                ref_images[n] = prop_map[n]
            else:
                orig_name, img = prop_map_lower.get(n.lower(), (None, None))
                if orig_name and img:
                    ref_images[orig_name] = img
        env_ref = (spec.get("environment_ref") or "").strip()
        if env_ref and (env_names or saved_envs):
            env_img = env_map.get(env_ref)
            if not env_img and env_ref:
                orig_name, env_img = env_map_lower.get(env_ref.lower(), (None, None))
            if env_img:
                ref_images["Environment"] = env_img
        if ref_images:
            scene_prompt = f"Keep characters, props, and the setting/environment visually consistent with their reference images. Scene: {scene_prompt}"
        img_b64 = ""
        for _ in range(2):
            try:
                img_b64 = generate_scene_image(scene_prompt, ref_images, style)
                if img_b64:
                    break
            except Exception:
                pass
        scenes.append({"sceneIndex": idx, "title": title, "imageBase64": img_b64, "prompt": scene_prompt})
    return {"scenes": scenes}


def action_reset(_payload: dict) -> dict:
    """Clear characters.json so next run is fresh (e.g. on page refresh)."""
    try:
        if CHARACTERS_JSON_PATH.exists():
            CHARACTERS_JSON_PATH.unlink()
    except Exception as e:
        return {"error": str(e)}
    return {"ok": True}


def _load_history() -> dict:
    """Load storyboard history JSON: { "entries": [ { name, createdAt, scenes: [...] }, ... ] }."""
    if not HISTORY_JSON_PATH.exists():
        return {"entries": []}
    try:
        data = json.loads(HISTORY_JSON_PATH.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {"entries": []}
        entries = data.get("entries")
        if not isinstance(entries, list):
            entries = []
        return {"entries": entries}
    except Exception:
        return {"entries": []}


def _save_history(data: dict) -> None:
    HISTORY_JSON_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2))


def action_save_history(payload: dict) -> dict:
    """Append a storyboard run (its scenes) to history under a given name."""
    name = (payload.get("storyboardName") or payload.get("name") or "").strip()
    scenes = payload.get("scenes") or []
    if not name:
        return {"error": "storyboardName required"}
    if not isinstance(scenes, list) or not scenes:
        return {"error": "scenes must be a non-empty list"}

    safe_scenes = []
    for s in scenes:
        if not isinstance(s, dict):
            continue
        safe_scenes.append(
            {
                "sceneIndex": s.get("sceneIndex"),
                "title": s.get("title") or "",
                "imageBase64": s.get("imageBase64") or "",
                "prompt": s.get("prompt") or "",
            }
        )
    if not safe_scenes:
        return {"error": "no valid scenes to save"}

    history = _load_history()
    entries = history.get("entries", [])
    entry = {
        "name": name,
        "createdAt": os.environ.get("SB_NOW_ISO") or "",
        "scenes": safe_scenes,
    }
    entries.append(entry)
    try:
        _save_history({"entries": entries})
    except Exception as e:
        return {"error": str(e)}
    return {"ok": True}


def action_get_history(_payload: dict) -> dict:
    """Return full storyboard history JSON."""
    return _load_history()


def main() -> None:
    try:
        os.chdir(BACKEND_DIR)
        inp = load_input()
    except Exception as e:
        send_output({"error": f"Invalid input: {e}"})
        sys.exit(1)

    action = (inp.get("action") or "").strip()
    payload = inp

    handlers = {
        "extract_script": action_extract_script,
        "get_characters": action_get_characters,
        "regenerate_character": action_regenerate_character,
        "get_props": action_get_props,
        "regenerate_prop": action_regenerate_prop,
        "identify_environments": action_identify_environments,
        "get_environments": action_get_environments,
        "regenerate_environment": action_regenerate_environment,
        "approve": action_approve,
        "generate_scenes": action_generate_scenes,
        "reset": action_reset,
        "save_history": action_save_history,
        "get_history": action_get_history,
    }
    handler = handlers.get(action)
    if not handler:
        send_output({"error": f"Unknown action: {action}"})
        sys.exit(1)
    try:
        out = handler(payload)
        if out.get("error"):
            send_output(out)
            sys.exit(1)
        send_output(out)
    except Exception as e:
        send_output({"error": str(e)})
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        send_output({"error": str(e)})
        sys.exit(1)
