# AI Video Production Skills Guide

Source research: [[_system/tools/ai-video-creation/video-creation-process-initial-research-doc|video-creation-process-initial-research-doc]]

Active skills:

- [[_system/agents/skills/ai-video-production/SKILL|ai-video-production]]
- [[_system/agents/skills/elevenlabs-voiceover/SKILL|elevenlabs-voiceover]]
- [[_system/agents/skills/heygen-avatar-render/SKILL|heygen-avatar-render]]
- [[_system/agents/skills/hyperframes-motion-graphics/SKILL|hyperframes-motion-graphics]]
- [[_system/agents/skills/ffmpeg-video-assembly/SKILL|ffmpeg-video-assembly]]
- [[_system/agents/skills/video-qa-review/SKILL|video-qa-review]]

## Quick How To

1. Ask agent for full video output:

```text
Create a 2-4 minute YouTube avatar video about [topic]. Use my source docs in reference/. Generate script, ElevenLabs voice chunks, HeyGen avatar clips, HyperFrames motion graphics, FFmpeg final assembly, and QA report. Do not mark ready until factual, visual, audio, and rights checks pass.
```

2. Put source material in project `reference/`.

3. Add or confirm:

- `reference/source-manifest.md` for sources, claim ledger, and rights notes.
- `reference/style-playbook.md` for presenter voice, brand taste, examples, and banned phrasing.

4. Agent should create/maintain:

```text
reference/
scripts/
raw-media/
style-library/
style-templates/
renders/
qa/
```

5. Expected final files:

- `renders/final.mp4`
- `renders/render-log.md`
- `renders/manifest.json`
- `scripts/timing-map.json`
- `raw-media/voice/manifest.json`
- `raw-media/avatar/manifest.json`
- `qa/report.md`

6. Useful helper commands from vault root or any project with `.agents/skills` available:

```bash
node .agents/skills/ai-video-production/scripts/chunk-script.js script.md --out raw-media/voice/chunks.json
node .agents/skills/ai-video-production/scripts/build-manifest.js --project . --out renders/manifest.json
bash .agents/skills/ai-video-production/scripts/check-video-props.sh renders/final.mp4
bash .agents/skills/ai-video-production/scripts/extract-qa-frames.sh renders/final.mp4 qa/frames
```

## Detailed Overview

`ai-video-production` is the main orchestration skill. It turns a prompt and source folder into a staged production workflow: brief, source proof, script, voice, avatar, motion graphics, assembly, and QA.

It should be the skill triggered by prompts like:

- "make a YouTube video"
- "create an AI avatar video"
- "make a fully edited prompt-to-video asset"
- "produce a publication-ready explainer"

Its main job is not provider API detail. Its job is keeping state clean and enforcing gates: source proof before script, stable manifests before generation, render logs before final, and QA before publication.

## Skill Chain

1. `ai-video-production`
   - Creates project shape.
   - Captures brief, audience, runtime, format, source material, consent/rights, and publish risk.
   - Requires claim ledger before final script.
   - Routes to specialist skills.

2. `elevenlabs-voiceover`
   - Starts only after script is approved/fact-checked.
   - Chunks text into stable IDs under roughly 60 seconds.
   - Writes voice manifest so accepted chunks are not accidentally regenerated.

3. `heygen-avatar-render`
   - Uses HeyGen API first.
   - Falls back to browser/Playwright only for Studio-only avatar or engine settings.
   - Writes avatar manifest with job IDs, settings, output paths, retries, and lip-sync/crop status.

4. `hyperframes-motion-graphics`
   - Builds synced HTML/CSS/GSAP composition from `scripts/timing-map.json`.
   - Keeps avatar visible by default.
   - Uses motion graphics to explain spoken concepts, not decorate.

5. `ffmpeg-video-assembly`
   - Inspects and normalizes inputs.
   - Concats avatar clips, overlays graphics, mixes audio, and exports `renders/final.mp4`.
   - Writes exact commands to `renders/render-log.md`.

6. `video-qa-review`
   - Extracts frames and reviews timing, layout, avatar crop, lip sync, captions, audio, source claims, and rights.
   - Writes `qa/report.md`.
   - Blocks "ready to publish" unless QA passes or user explicitly waives defects.

## Project Contracts

`reference/source-manifest.md` should answer:

- What are the source docs or URLs?
- Which script claims does each source support?
- Which claims are unverified, weak, or excluded?
- What rights/consent covers voice, avatar, music, screenshots, logos, and other assets?

`reference/style-playbook.md` should answer:

- What should presenter sound like?
- What phrases, tone, claims, and visual styles are off-brand?
- What examples represent good pacing and taste?
- What channel/audience expectations matter?

`scripts/timing-map.json` should connect:

- script beat
- voice chunk
- start/end time
- caption text
- visual/motion graphic
- source claim ID where factual

`qa/report.md` should include:

- pass/fail status
- factual issues found/fixed
- visual issues found/fixed
- audio/timing issues found/fixed
- rights/consent status
- unresolved risks
- final publish recommendation

## Problems And Oversights Fixed

- Added rights/consent checks for voice clone, avatar, music, screenshots, logos, and stock assets.
- Added secret-handling reminder: agents should not read plaintext `.env`, key, token, kubeconfig, or secrets paths.
- Added claim ledger expectation, not just loose source manifest.
- Tightened avatar wording: visible by default; full-screen hides need explicit intent.
- Added style-playbook expectation so "presenter voice" is grounded in examples.
- Added lip-sync/crop review to HeyGen and QA steps.
- Added command examples that clarify they run from vault root or a project with `.agents/skills`.

## Remaining Caveats

- Provider APIs change. Check current official docs before real HeyGen, ElevenLabs, HyperFrames, or FFmpeg work.
- `npx skills add heygen-com/hyperframes` depends on current CLI support; if unavailable, use official HyperFrames docs directly.
- Helper scripts are deterministic scaffolding only. They do not call provider APIs.
- `chunk-script.js` estimates duration from WPM. Real duration must come from generated audio or ffprobe.
- `extract-qa-frames.sh` samples frames; it does not replace human/vision review at beat transitions.
- Shared research stays under `_system/tools/ai-video-creation/`.

## Reference URLs

- HyperFrames GitHub: https://github.com/heygen-com/hyperframes
- HyperFrames pipeline: https://hyperframes.heygen.com/guides/pipeline
- ElevenLabs text-to-speech: https://elevenlabs.io/docs/overview/capabilities/text-to-speech
- HeyGen create video: https://developers.heygen.com/reference/create-video
- GSAP Timeline: https://gsap.com/docs/v3/GSAP/Timeline/
- FFmpeg docs: https://ffmpeg.org/ffmpeg.html
