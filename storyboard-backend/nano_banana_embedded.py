from google import genai
from google.genai import types
import base64
import os

from dotenv import load_dotenv
load_dotenv()

GCP_PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "")
GCP_LOCATION = os.environ.get("GCP_LOCATION", "global")


def _generate_content_config():
    return types.GenerateContentConfig(
        temperature=1,
        top_p=0.95,
        max_output_tokens=32768,
        response_modalities=["TEXT", "IMAGE"],
        safety_settings=[
            types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="OFF"),
            types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="OFF"),
            types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="OFF"),
            types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="OFF"),
        ],
        image_config=types.ImageConfig(
            aspect_ratio=os.environ.get("SB_ASPECT_RATIO", "16:9"),
            image_size="2K",
            output_mime_type="image/png",
        ),
    )


def _stream_image_response(client, model, contents):
    response = None
    config = _generate_content_config()
    for chunk in client.models.generate_content_stream(
        model=model,
        contents=contents,
        config=config,
    ):
        if not chunk.candidates or not chunk.candidates[0].content or not chunk.candidates[0].content.parts:
            continue
        for part in chunk.candidates[0].content.parts:
            if hasattr(part, "inline_data") and part.inline_data:
                data = part.inline_data.data
                if isinstance(data, str):
                    return data
                return base64.b64encode(bytes(data)).decode("utf-8")
        response = chunk
    if not response:
        raise RuntimeError("No image returned from model")
    for part in response.candidates[0].content.parts:
        if hasattr(part, "inline_data") and part.inline_data:
            data = part.inline_data.data
            if isinstance(data, str):
                return data
            return base64.b64encode(bytes(data)).decode("utf-8")
    raise RuntimeError("No image data in response")


def generate(prompt: str):
    client = genai.Client(
        vertexai=True,
        project=GCP_PROJECT_ID,
        location=GCP_LOCATION,
    )
    model = "gemini-3-pro-image-preview"
    contents = [
        types.Content(
            role="user",
            parts=[types.Part.from_text(text=prompt)] if prompt else [],
        )
    ]
    return _stream_image_response(client, model, contents)


def _generate_with_parts(parts: list):
    """Generate image from multimodal parts (text + reference images)."""
    client = genai.Client(
        vertexai=True,
        project=GCP_PROJECT_ID,
        location=GCP_LOCATION,
    )
    model = "gemini-3-pro-image-preview"
    contents = [types.Content(role="user", parts=parts)]
    return _stream_image_response(client, model, contents)


def generate_character_image(prompt: str) -> str:
    return generate(prompt)


def generate_scene_image(prompt: str, character_ref_images: dict, style: str) -> str:
    """Generate scene image with character, prop, and environment reference images for consistency."""
    if not character_ref_images:
        return generate(prompt)

    ref_names = list(character_ref_images.keys())
    instruction = (
        "You are given reference images for the following (characters, props, and/or environment/setting, in order): " + ", ".join(ref_names) + ". "
        "Generate ONE scene image that matches the scene description below. "
        "CRITICAL: Keep characters STRICTLY consistent with their reference images (same face, hair, build, clothing). "
        "CRITICAL: Keep props/objects STRICTLY consistent with their reference images (same look, shape, style). "
        "CRITICAL: If an Environment/setting reference is provided, keep the location, lighting, and style of the setting STRICTLY consistent with that reference. "
        f"Style: {style}. Scene to generate: {prompt}"
    )
    parts = [types.Part.from_text(text=instruction)]
    for name, b64 in character_ref_images.items():
        if not b64:
            continue
        try:
            img_bytes = base64.b64decode(b64, validate=True)
        except Exception:
            continue
        parts.append(types.Part.from_bytes(data=img_bytes, mime_type="image/png"))
    if len(parts) <= 1:
        return generate(prompt)
    return _generate_with_parts(parts)
