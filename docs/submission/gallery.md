# Hack-Nation submission: media gallery

Ranked list of up to 8 items for the form's media gallery, best first. All paths
are relative to the repo root. Screenshots were verified to exist in
`deck/assets/`. The pitch PDF is being produced in a sibling PR; the videos have
v1 committed with v2 pending (wave 3).

| # | Item | Repo path | Status | Why it earns the slot |
|---|---|---|---|---|
| 1 | War Room screenshot | `deck/assets/warroom.png` | Exists | The signature screen: a live call streaming transcript, tool calls, and escalations. Shows the product actually running. |
| 2 | Report / diagnosis screenshot | `deck/assets/report.png` | Exists | The bill diagnosis with flagged errors and the savings number. Makes the value obvious in one frame. |
| 3 | Home hero screenshot | `deck/assets/home-hero.png` | Exists | Clean landing shot for the gallery thumbnail and first impression. |
| 4 | Intake / upload screenshot | `deck/assets/intake.png` | Exists | Shows the entry point: upload a bill, the loop begins. |
| 5 | Bills / case view screenshot | `deck/assets/bills.png` | Exists | The case file with the parsed bill lines. |
| 6 | Pitch deck (PDF) | `deck/haggl-pitch.pdf` | Pending (sibling PR) | Full pitch. Export from `deck/haggl-pitch.pptx` if the PDF is not landed yet. Also linked as hagglfor.me/pitch-sf-2026. |
| 7 | Tech tour video | `deck/video/tech-video-v1.mp4` | Exists (v1; v2 pending) | Architecture walkthrough. Use v2 when ready. Convert to H.264 MP4 for upload. Also at hagglfor.me/tech-video. |
| 8 | Product / UX walkthrough video | `deck/video/uiux-video-v1.mp4` | Exists (v1; v2 pending) | End-to-end product demo. Use v2 when ready. Convert to H.264 MP4 for upload. |

## Suggested extras (if a slot opens)

- **War Room replay clip**: `deck/video/a-shot5-warroom-replay.webm`. The most
  dynamic single shot of the product in motion. Re-encode to H.264 MP4 before
  upload.
- **Approve-to-War-Room clip**: `deck/video/a-shot4-approve-warroom.webm`. Shows
  a user approving a case and the call going live.

## Notes

- Screenshots (`deck/assets/*.png`) are ready to upload as-is.
- Any video uploaded to the gallery must be **H.264 MP4** (re-encode the `.webm`
  shots and confirm the `.mp4` files are H.264).
- If `deck/haggl-pitch.pdf` has not landed from the sibling PR by submission time,
  export it from `deck/haggl-pitch.pptx` or link the deck at hagglfor.me/pitch-sf-2026.
