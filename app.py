"""
script-to-storyboard
--------------------
Paste a screenplay (standard slugline format) or plain prose and get:
  1. a machine readable shot list
  2. a storyboard panel for every shot, streamed as they are rendered
  3. a CSV you can hand to a director or import into a shot tracker

Run the UI:      python app.py
Shot list only:  python app.py --dry-run sample_script.txt
Diagnose setup:  python app.py --check
"""
from __future__ import annotations

import argparse
import csv
import os
import re
import sys
from dataclasses import dataclass, field

import gradio as gr


# ---------------------------------------------------------------------- 1. parse
SLUG = re.compile(r"^(INT\.|EXT\.|INT\./EXT\.|EXT/INT\.)\s*(.+?)(?:\s+-\s+(.+))?$", re.I)
TRANSITION = re.compile(
    r"^(CUT TO:|CUT TO BLACK|FADE (OUT|IN)[:.]?|FADE TO BLACK|SMASH CUT TO:|"
    r"DISSOLVE TO:|MATCH CUT TO:|THE END)",
    re.I,
)
CHARACTER_CUE = re.compile(r"^[A-Z][A-Z\s0-9\-']{1,39}(\s*\([^)]*\))?$")
NAME = re.compile(r"\b([A-Z][A-Z]{2,})\b")
CAMERA_PREFIX = re.compile(
    r"^(CLOSE ON|CLOSE UP|INSERT OF|WIDE ON|POV|ON|OVER THE SHOULDERS? OF)\s*[-:,]?\s*", re.I
)
STOP = {
    "THE", "AND", "BUT", "FOR", "INT", "EXT", "HIS", "HER", "OUR", "WITH", "FROM",
    "THAT", "THIS", "NOT", "YOU", "THEY", "WAS", "WERE", "HAVE", "HAD", "WILL",
}


@dataclass
class Scene:
    location: str
    time: str
    interior: str
    beats: list = field(default_factory=list)
    speakers: set = field(default_factory=set)


def parse_screenplay(text: str) -> list[Scene]:
    """Split a script into scenes, then into action and dialogue beats."""
    scenes, current, speaker = [], None, None

    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if TRANSITION.match(line):
            continue

        slug = SLUG.match(line)
        if slug:
            current = Scene(
                location=(slug.group(2) or "unspecified location").strip(),
                time=(slug.group(3) or "").strip(),
                interior=slug.group(1).upper(),
            )
            scenes.append(current)
            speaker = None
            continue

        if current is None:  # plain prose, no sluglines: treat it as one scene
            current = Scene(location="unspecified location", time="", interior="INT.")
            scenes.append(current)

        if CHARACTER_CUE.match(line) and not line.endswith("."):
            speaker = re.sub(r"\s*\([^)]*\)$", "", line)
            current.speakers.add(speaker)
            continue

        if line.startswith("("):  # parenthetical delivery note, e.g. (quietly)
            continue

        current.beats.append(
            {"line": line, "speaker": speaker, "kind": "dialogue" if speaker else "action"}
        )
        speaker = None

    return scenes


# ------------------------------------------------------------------- 2. shot plan
CAMERA_HINTS = [
    (r"close on|close[- ]up|insert of|cu on", "close-up"),
    (r"wide on|establish|long shot|extreme wide", "extreme wide establishing"),
    (r"pov|point of view", "POV"),
    (r"track|follow|steadicam|crane|drone|aerial|push in", "tracking shot"),
    (r"over the shoulder|ots", "over-the-shoulder"),
]

MOTION = r"\b(climbs|runs|walks|drives|crosses|chases|enters|emerges|flees|descends|turns)\b"
DETAIL = r"\b(eyes|face|hands|blood|tears|wound|smile|fear|glance|ring|letter|photograph)\b"


def classify(beat: dict, index: int) -> str:
    line = beat["line"].lower()
    for pattern, shot in CAMERA_HINTS:
        if re.search(pattern, line):
            return shot
    if beat["kind"] == "dialogue":
        return f"over-the-shoulder of {beat['speaker'] or 'the speaker'}"
    if index == 0:
        return "extreme wide establishing"
    if re.search(MOTION, line):
        return "tracking shot"
    if re.search(DETAIL, line):
        return "close-up"
    return "medium wide"


def character_registry(scenes: list[Scene]) -> dict[str, str]:
    """Remember each character and how they were first described, so panels stay consistent."""
    people: dict[str, str] = {}

    for scene in scenes:
        for speaker in scene.speakers:
            people.setdefault(speaker, "")
        for beat in scene["beats"]:
            for name in NAME.findall(beat["line"]):
                if name in STOP:
                    continue
                look = re.search(re.escape(name) + r"\s*[,(-]\s*([^)]+)", beat["line"])
                if look and not people.get(name):
                    people[name] = look.group(1).strip().lower()
                else:
                    people.setdefault(name, "")
    return people


def build_shots(script: str, style: str, negative: str) -> list[dict]:
    scenes = parse_screenplay(script)
    registry = character_registry(scenes)
    shots = []

    for scene_index, scene in enumerate(scenes, 1):
        for beat_index, beat in enumerate(scene["beats"]):
            shot_type = classify(beat, beat_index)
            cast = {n for n in NAME.findall(beat["line"]) if n in registry}
            if beat["speaker"]:
                cast.add(beat["speaker"])
            cast = sorted(cast)

            described = [f"{c} ({registry[c]})" for c in cast if registry.get(c)]
            who = ", ".join(described) if described else (", ".join(cast) or "no characters in frame")

            setting = f"{scene.interior} {scene.location}"
            if scene.time:
                setting += f", {scene.time.lower()}"

            action = CAMERA_PREFIX.sub("", beat["line"]).strip()

            shots.append(
                {
                    "no": len(shots) + 1,
                    "scene": scene_index,
                    "type": shot_type,
                    "action": beat["line"],
                    "characters": who,
                    "prompt": f"{style}, {shot_type}, {setting}, {who}, {action}, cinematic composition",
                    "negative": negative,
                }
            )
    return shots


# ------------------------------------------------------------------ 4. render
MODELS = {
    "Local SD 1.5 (CPU friendly)": "stable-diffusion-v1-5/stable-diffusion-v1-5",
    "Local SDXL (needs a GPU)": "stabilityai/stable-diffusion-xl-base-1.0",
    "Hosted API (no local install)": "stable-diffusion-v1-5/stable-diffusion-v1-5",
    "Placeholder only (no model at all)": None,
}
STYLES = {
    "storyboard sketch": "loose pencil and ink storyboard panel, flat muted color wash, white paper background",
    "photoreal film still": "cinematic film still, 35mm, natural light, shallow depth of field",
    "blueprint line art": "black and white architectural line drawing, technical storyboard board",
    "anime cel": "anime cel shading, clean linework, expressive characters",
}
SIZES = {
    "small": {"16:9": (512, 288), "21:9": (512, 216), "1:1": (512, 512), "9:16": (288, 512)},
    "large": {"16:9": (1024, 576), "21:9": (1024, 440), "1:1": (1024, 1024), "9:16": (576, 1024)},
}

_pipelines: dict[str, object] = {}
_client = None


def device_info() -> str:
    try:
        import torch

        return f"torch {torch.__version__} · device: {'cuda' if torch.cuda.is_available() else 'cpu'}"
    except Exception as exc:
        return f"torch unavailable: {exc}"


def sized(model_key: str, aspect: str) -> tuple[int, int]:
    return SIZES["large" if model_key == "Local SDXL (needs a GPU)" else "small"][aspect]


def local_pipeline(model_id: str):
    if model_id not in _pipelines:
        import torch
        from diffusers import StableDiffusionPipeline

        device = "cuda" if torch.cuda.is_available() else "cpu"
        dtype = torch.float16 if device == "cuda" else torch.float32
        print(f"Loading {model_id} on {device} ... this can take a few minutes the first time")
        _pipelines[model_id] = StableDiffusionPipeline.from_pretrained(model_id, torch_dtype=dtype).to(device)
    return _pipelines[model_id]


def render(prompt: str, negative: str, size: tuple[int, int], steps: int, seed: int, model_key: str):
    model_id = MODELS[model_key]

    if model_key == "Hosted API (no local install)":
        global _client
        if _client is None:
            from huggingface_hub import InferenceClient

            _client = InferenceClient(model=model_id)  # needs HF_TOKEN in the environment
        return _client.image_generation(
            prompt, width=size[0], height=size[1], negative_prompt=negative, num_inference_steps=int(steps)
        )

    pipe = local_pipeline(model_id)
    import torch

    generator = torch.Generator(pipe.device).manual_seed(int(seed))
    return pipe(
        prompt=prompt,
        negative_prompt=negative,
        width=size[0],
        height=size[1],
        num_inference_steps=int(steps),
        guidance=7.5,
        generator=generator,
    ).images[0]


def wrap(text: str, width: int = 60) -> list[str]:
    lines, current = [], ""
    for word in text.split():
        if len(current) + len(word) + 1 > width:
            lines.append(current)
            current = word
        else:
            current = (current + " " + word).strip()
    if current:
        lines.append(current)
    return lines or [""]


def placeholder_panel(shot: dict, size: tuple[int, int]):
    """A drawn storyboard board, so the sequence is complete even with no image model."""
    from PIL import Image, ImageDraw

    try:
        from PIL import ImageFont

        font = ImageFont.truetype("DejaVuSans.ttf", 22)
        small = ImageFont.truetype("DejaVuSans.ttf", 14)
    except Exception:
        font = small = ImageFont.load_default()

    image = Image.new("RGB", size, (248, 246, 240))
    draw = ImageDraw.Draw(image)
    draw.rectangle([0, 0, size[0] - 1, size[1] - 1], outline=(70, 70, 70))
    draw.rectangle([0, 0, size[0] - 1, 46], outline=(70, 70, 70))
    draw.text((12, 14), f"SHOT {shot['no']:03d} - {shot['type']}", fill=(20, 20, 20), font=font)

    y = 60
    for line in wrap(shot["action"], 70)[:8]:
        draw.text((12, y), line, fill=(40, 40, 40), font=small)
        y += 20
    draw.text((12, size[1] - 24), "placeholder panel - image model unavailable", fill=(120, 120, 120), font=small)
    return image


def generate(script: str, style: str, model: str, steps: int, aspect: str, seed: int, out_dir: str = "storyboard"):
    shots = build_shots(script, STYLES[style], "blurry, text, watermark, deformed hands")
    if not shots:
        yield [], [], "No scenes or action lines found in the script. Check the slugline format (INT./EXT. LOCATION - TIME)."
        return

    os.makedirs(out_dir, exist_ok=True)
    size = sized(model, aspect)
    progress = gr.Progress()
    images, rows = [], []
    status = f"Rendering {len(shots)} panels · {device_info()}"

    for shot in shots:
        progress(shot["no"] / len(shots), desc=f"Panel {shot['no']} of {len(shots)}")
        error = ""
        try:
            if model == "Placeholder only (no model at all)":
                image = placeholder_panel(shot, size)
            else:
                image = render(shot["prompt"], shot["negative"], size, steps, int(seed) + shot["no"], model)
        except Exception as exc:
            image = placeholder_panel(shot, size)
            error = f"{type(exc).__name__}: {exc}"
            status = f"Image model failed ({error}). Falling back to drawn placeholder panels."

        path = os.path.join(out_dir, f"shot_{shot['no']:03d}.png")
        image.save(path)
        images.append(image)
        rows.append(
            [shot["no"], shot["scene"], shot["type"], shot["action"], shot["characters"], shot["prompt"], path, error]
        )
        yield images, rows, status

    with open(os.path.join(out_dir, "storyboard.csv"), "w", newline="", encoding="utf-8") as handle:
        csv.writer(handle).writerows(
            [["shot", "scene", "shot_type", "action", "characters", "prompt", "image", "error"]] + rows
        )
    yield images, rows, f"Done: {len(images)} panels written to {out_dir}/ and {out_dir}/storyboard.csv"


def shot_list(script: str, style: str):
    return [[s["no"], s["scene"], s["type"], s["action"]] for s in build_shots(script, STYLES[style], "")]


# ---------------------------------------------------------------- Gradio UI
SAMPLE = open("sample_script.txt", encoding="utf-8").read() if os.path.exists("sample_script.txt") else ""

demo = gr.Blocks(title="Script to Storyboard")

with demo:
    gr.Markdown(
        "Paste a screenplay (standard slugline format) or plain prose. "
        "Preview the shot list first, then generate the panels. "
        "Panels appear one at a time; if the image model cannot load you still get drawn placeholder boards."
    )
    script = gr.Textbox(label="Script", lines=15, value=SAMPLE)
    with gr.Row():
        style = gr.Dropdown(list(STYLES), value="storyboard sketch", label="Style")
        model = gr.Dropdown(list(MODELS), value="Local SD 1.5 (CPU friendly)", label="Backend")
        aspect = gr.Dropdown(list(SIZES["small"]), value="16:9", label="Aspect ratio")
        steps = gr.Slider(10, 40, value=20, label="Steps")
        seed = gr.Number(value=1337, label="Base seed")

    status = gr.Textbox(label="Status", value=device_info())

    gr.Button("Preview shot list", variant="secondary").click(
        lambda s, st: shot_list(s, st),
        [script, style],
        gr.Dataframe(["shot", "scene", "type", "action"]),
    )
    gr.Button("Generate storyboard", variant="primary").click(
        lambda s, st, m, n, a, sd: generate(s, st, m, n, a, sd),
        [script, style, model, steps, aspect, seed],
        [
            gr.Gallery(columns=4),
            gr.Dataframe(["shot", "scene", "type", "action", "characters", "prompt", "image", "error"]),
            status,
        ],
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", metavar="SCRIPT", help="print the shot list and exit without generating images")
    parser.add_argument("--check", action="store_true", help="print device info and try loading the model once")
    parser.add_argument("--style", default="storyboard sketch")
    args = parser.parse_args()

    if args.dry_run:
        with open(args.dry_run, encoding="utf-8") as handle:
            for shot in build_shots(handle.read(), STYLES[args.style], ""):
                print(f"{shot['no']:>3}  scene {shot['scene']}  {shot['type']:<24}  {shot['action']}")
        sys.exit(0)

    if args.check:
        print(device_info())
        try:
            image = render("a lighthouse at night, storyboard sketch", "", (512, 288), 10, 1, "Local SD 1.5 (CPU friendly)")
            print(f"Model loaded OK, produced a {image.size} image.")
        except Exception as exc:
            print(f"Could not load the model: {exc}")
        sys.exit(0)

    demo.launch()
