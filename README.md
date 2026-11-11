# script-to-storyboard

Paste a screenplay, get a shot list and a storyboard panel for every shot. The parsing is deterministic and runs on your own machine — no LLM, no cloud account, no prompt engineering by hand.

## Quick start

```bash
git clone https://github.com/modahlwi/script-to-storyboard
cd script-to-storyboard
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

Check your environment before generating:

```bash
python app.py --check
```

## Downloading the model by hand

The app normally downloads `stable-diffusion-v1-5` (~4.3 GB) into the Hugging Face cache on first run. If you want to fetch it yourself:

```bash
hf download stable-diffusion-v1-5/stable-diffusion-v1-5 \
  model_index.json \
  unet/config.json unet/diffusion_pytorch_model.safetensors \
  vae/config.json vae/diffusion_pytorch_model.safetensors \
  text_encoder/config.json text_encoder/model.safetensors \
  tokenizer/tokenizer_config.json tokenizer/vocab.json tokenizer/merges.txt tokenizer/special_tokens_map.json \
  scheduler/scheduler_config.json \
  feature_extractor/preprocessor_config.json \
  --local-dir models/sd1.5
```

Then point the app at that folder:

```bash
python app.py --model-dir models/sd1.5
# or
set SD_MODEL_DIR=models/sd1.5       # Windows
export SD_MODEL_DIR=models/sd1.5    # macOS/Linux
```

The folder must keep the Hub layout — `model_index.json` at the top with `unet/`, `vae/`, `text_encoder/`, `tokenizer/`, `scheduler/` beside it. Those files are all that diffusers needs; the `.ckpt` files and the safety checker can be skipped.

If you let the app download it instead, it lands in:

- Windows: `C:\Users\<you>\.cache\huggingface\hub\models--stable-diffusion-v1-5--stable-diffusion-v1-5\snapshots\<rev>\`
- macOS/Linux: `~/.cache/huggingface/hub/models--stable-diffusion-v1-5--stable-diffusion-v1-5/snapshots/<rev>/`

You can move the cache anywhere with `set HF_HOME=D:\hf-cache` before running the app.

## How it works

| Stage | What happens |
|---|---|
| **Parse** | Splits the script into scenes using sluglines (`INT./EXT. LOCATION - TIME`), then into action and dialogue beats. Transitions (`CUT TO:`, `FADE OUT.`) are ignored. |
| **Plan shots** | Explicit camera directions in the text are honoured. Everything else is inferred: the first beat of a scene becomes an establishing wide, motion verbs become tracking shots, emotional or object detail becomes a close-up, dialogue becomes an over-the-shoulder. |
| **Build prompts** | Style prefix + shot type + location + time of day + cast. Each character carries the visual description from their first appearance, which is what keeps Mara looking like Mara in panel 3 and panel 17. |
| **Render** | Stable Diffusion locally, the Hugging Face hosted API, or a drawn placeholder board if neither is available. Panels stream into the gallery as they are made and are written to `storyboard/shot_001.png` plus `storyboard.csv`. |

## Backends

| Backend | Needs | Notes |
|---|---|---|
| Local SD 1.5 | torch (CPU ok) | 512px panels, slow but works on a laptop |
| Local SDXL | CUDA GPU | 1024px panels |
| Hosted API | `HF_TOKEN` | nothing installed locally |
| Placeholder | nothing | proves the pipeline works, boards are drawn text panels |

## Output

`storyboard.csv` columns: `shot, scene, shot_type, action, characters, prompt, image, error`.

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
- ComfyUI backend

MIT licensed.
