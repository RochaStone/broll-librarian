# style.json

One file holds your look. Every Rocha Coded tool reads the same file, so you make it once.

## Where it goes
The tool looks in this order and uses the first one it finds:
1. `style.json` in the folder you are working in (your Cowork folder, or wherever you run Claude Code)
2. `~/.rocha-coded/style.json`, to use one look across every project
3. `examples/style.rocha-coded.json`, the bundled example (Rocha's look)

Start from `style.example.json`: copy it to `style.json` and fill it in. Or ask Claude to make one with you.

## The keys
| Key | What to put there | Used by this tool |
|---|---|---|
| `name` | your brand or studio name | no |
| `owner` | your name, as you sign things | yes, under the title and in the credit line |
| `handle` | your Instagram or main social handle, with the @ | yes, in the credit line |
| `site` | your website address | no |
| `palette.hero` | your ground colour, the deep one everything sits on, as a hex code like `#50163C` | the page behind everything (never a fill) |
| `palette.wine` | a second deep colour for headlines | the title, labels, numbers, the sidebar headings |
| `palette.accent` | your one bright accent | the ok to post pills, the active filter, the tape |
| `palette.paper` | a light paper colour | the contact sheet and the window |
| `palette.paper_pink` | a second paper colour | the polaroid frames, the sidebar |
| `palette.ink` | your text colour | text, outlines, the keep private pills |
| `palette.marker` | the colour of the handwritten scrawl | the scrawl and the date stamp |
| `palette.plum` | a deep shade | the picture frames |
| `palette.gold` | a highlight colour for thin rules | the rule under the title, the pixel icons, the cyberpunk labels |
| `palette.cool` | one cool accent, used rarely | no |
| `fonts.masthead` | a big display font from Google Fonts | the title |
| `fonts.label` | a font for labels and small print | the names, the kinds, the chips |
| `fonts.body` | a reading font | the notes under each clip |
| `fonts.scrawl` | a handwriting or marker font | the scrawl |
| `fonts.script` | a signature script font | no |
| `fonts.mono` | a typewriter font | the numbers and details |
| `fonts.pixel` (optional) | a pixel font from Google Fonts | the cyberpunk and y2k-blog labels (Silkscreen if empty) |
| `motif` | `analog`, `cyberpunk` or `y2k-blog` (older names like `guest-check` or `retro-tv` still work and map to the nearest one) | yes: the contact sheet, the terminal, or the blog window |
| `lines.scrawl` | a short line in your own words | the handwritten line at the foot of the page |
| `lines.masthead`, `headline`, `todo`, `stamp`, `celebrate`, `affirm`, `invite`, `magazine` | more of your own lines | kept for other tools |
| `references` | 3 to 5 images or links that feel like you | Claude looks at these when it makes your style with you |
| `notes` | your look in one or two sentences | Claude reads this too |

## Good to know
- Colours must be hex codes (`#RRGGBB`). Anything else is skipped and the bundled colour is used for that slot.
- Fonts are Google Fonts names, letters, numbers and spaces only. If a font is not on Google Fonts, or you are offline, the page uses a similar font already on your computer.
- Any colour or font you leave empty borrows the bundled example's, so the page always looks finished.
- Your words and your name never borrow. Leave `lines.scrawl`, `owner` or `handle` empty and the page prints nothing there.
