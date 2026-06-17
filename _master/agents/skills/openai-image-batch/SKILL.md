---
name: openai-image-batch
description: Generate batches of images with the OpenAI Image API using GPT-Image 2, custom resolutions, and per-image prompts. Use when creating multiple images, website assets, prompt batches, or GPT-Image 2 outputs from a JSON manifest.
---

# OpenAI Image Batch

## Quick Start

Load vault env, then run the bundled generator:

```bash
cd "$(vault root)"
source _master/env/load-env.sh
node _master/agents/skills/openai-image-batch/scripts/generate-images.mjs --manifest prompts.json --out renders/images
```

Use dry run first:

```bash
node _master/agents/skills/openai-image-batch/scripts/generate-images.mjs --manifest prompts.json --out renders/images --dry-run
```

## Manifest

```json
{
  "defaults": {
    "quality": "medium",
    "format": "png"
  },
  "images": [
    {
      "id": "ctx9-cta",
      "size": "2880x1920",
      "prompt": "Engineering command desk..."
    },
    {
      "id": "ctx9-service-strategy",
      "size": "1024x1280",
      "n": 2,
      "prompt": "Abstract business terrain map..."
    }
  ]
}
```

## Rules

- Env key is `OPENAI_API_KEY`; add the real secret to `_master/env/.env`, not `.env.base`.
- Model defaults to `gpt-image-2`.
- Script accepts per-image `id`, `prompt`, `size`, `n`, `quality`, `format`, and `output_compression`.
- Valid `gpt-image-2` sizes need both edges divisible by `16`, max edge `3840`, ratio `<= 3:1`, and total pixels from `655360` to `8294400`.
- For legacy odd sizes, generate nearest valid ratio size, then crop/resize final files separately.
- Use `--force` to overwrite existing files.
- Use `--concurrency N` only when rate limits and cost are understood.

## Commands

```bash
node _master/agents/skills/openai-image-batch/scripts/generate-images.mjs \
  --manifest prompts.json \
  --out renders/images \
  --quality high \
  --format webp \
  --concurrency 1
```

Outputs are named `<id>-01.<format>` and summarized in `generation-results.json`.
