# Tag these clips

You are tagging video clips for a creator's b-roll library. You never see the clips themselves.
You see key frames: still pictures pulled from each clip where the scene changes, in time order.
Your tags decide which clips can be used in reels, so be careful, and be kind to the person who owns the footage.

## What you are given
- A batch file such as `library/batches/batch-003.json`. It lists up to ten clips. Each has an `id`, a `name`,
  a `duration`, an `orientation` and `frames`, which are paths relative to the library folder.
- `taxonomy.json`, which lists every field and every value you may use, with a plain-words `help` line for each.

## What to do
1. Read `taxonomy.json` once.
2. For each clip, open every frame listed for it and look at them together as one clip.
3. Write ONE JSON object per clip, one per line, into the file named by `tag_file` in the batch
   (for example `library/tags/batch-003.jsonl`). Create the `tags` folder if it is missing.
4. Run the check and fix anything it reports:
   ```sh
   python3 taxonomy.py library/tags/batch-003.jsonl
   ```
   You will see `10 tag lines checked, all clean.`

## The fields
Every line has: `id` (copy it exactly), `kind`, `product`, `place`, `people_present`, `mood`, `motion`,
`reel_role`, `usable`, `quality` and `notes`. Use only the values in `taxonomy.json`.

Example line (one line in the file, shown wrapped here):
```json
{"id": "sunrise-swim-3f9a1c", "kind": "broll", "product": false, "place": "beach_water",
 "people_present": "none", "mood": ["calm", "golden_hour"], "motion": "static", "reel_role": "opener",
 "usable": "yes", "quality": 5, "notes": "Sunrise over flat water, no one in shot."}
```

## Rules that matter most
- **usable is "no" unless every frame is clearly clean.** Say "yes" only when no other person is in shot (even far
  away), no child is in shot, no screen or document is readable, and nothing in the frames is private.
  When you are not sure, write "no" and say why in `notes`. A wrong "no" costs a second look. A wrong "yes" can
  put someone in public who did not agree to it.
- **people_present:** "me_only" means only the owner of the camera roll, and you can only say that when the
  frames make it clear. If you cannot tell, use "others". Any child at all means "children".
- **Screens:** a phone or computer screen means kind "screen_recording" and usable "no". Never copy text, names,
  numbers or messages from a screen into `notes`.
- **Talking to the lens** is kind "talking_head", and it stays apart from b-roll.
- **Do not invent.** Describe only what the frames show. If the place is not clear, use "unknown".
- **mood** is one to three values and is taste, so choose what the footage feels like.
- **quality** judges the footage (sharp, lit, framed), not the taste. 1 is unwatchable, 3 is fine, 5 is sharp and well framed.
- **notes** is one plain line of 200 characters or fewer. No names of people, ever.
- Skip nothing. If a clip's frames will not open, write the line anyway with kind "unusable", usable "no", and say so in `notes`.

Finish by telling the person how many clips you tagged and how many you marked usable "yes".
