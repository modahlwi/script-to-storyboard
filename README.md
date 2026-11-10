# script-to-storyboard

Paste a screenplay, get a shot list and a generated storyboard panel for every shot. The parsing is deterministic and runs on your own machine — no LLM, no cloud account, no prompt engineering by hand.

## Quick start

```bash
python -m venv .venv
.venv\Scripts\activate              # Windows
# source .venv/bin/activate         # macOS / Linux
pip install -r requirements.txt
python app.py                     # open http://127.0.0.1:7860
```

Inspect the shot list without generating any images:

```bash
python app.py --dry-run sample_script.txt
```

## How it works

| Stage | What happens |
|---|---|
| **Parse** | Splits the script into scenes using sluglines (`INT./EXT. LOCATION - TIME`), then into action and dialogue beats. Transitions (`CUT TO:`, `FADE OUT.`) are ignored. |
| **Plan shots** | Explicit camera directions in the text are honoured. Everything else is inferred: the first beat of a scene becomes an establishing wide, motion verbs become tracking shots, emotional or object detail becomes a close-up, dialogue becomes an over-the-shoulder. |
| **Build prompts** | Style prefix + shot type + location + time of day + cast. Each character carries the visual description from their first appearance, which is what keeps Mara looking like Mara in panel 3 and panel 17. |
| **Render** | Stable Diffusion locally: SD 1.5 works on a laptop CPU, SDXL wants a GPU. Panels are written to `storyboard/shot_001.png` plus a `storyboard.csv` shot list. |

## Output

`storyboard.csv` columns: `shot, scene, shot_type, action, characters, prompt, image`.

## Tuning

- **Style** is a shared prefix for every panel. Add your own in the `STYLES` dict.
- **Base seed** makes the whole sequence reproducible — each shot uses `base_seed + shot_number`.
- Aspect ratio per panel: 16:9, 21:9, 1:1, or 9:16 for vertical.

## Known limitations

- Character cue detection assumes uppercase cue lines. An action line written in capitals without punctuation can be mistaken for a cue.
- Shot inference is heuristic. A script with no camera directions produces a competent, not directorial, shot list.
- Character consistency is prompt-level only. For real continuity across many panels you need a character LoRA or reference images.

## Roadmap

- LoRA or IP-Adapter reference images per character
- Optional local LLM pass to rewrite action lines into visual descriptions
- Contact-sheet PDF export
- ComfyUI and Hugging Face Inference API backends for machines without a GPU

MIT licensed.
