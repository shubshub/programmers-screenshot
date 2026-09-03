# Post-mortem: annotating a Claude-in-Chrome tab capture (2026-09-03)

**Audience.** A session improving the `programmers-screenshot` skill text (written by
`--install-skill` from `src/programmers_screenshot/cli.py`) and possibly the tool itself.
Everything below was measured on Chris's desktop the same day; nothing is inferred from docs.

**Task that exposed this.** Produce a PDF with annotated screenshots of five operations in a
Kademi debug-session page (`gamesandmore.admin.kademiplay.com/dev-tools/sessions/yq4k90u`),
each showing the JSON payload sent to Scorecard and the timeout/response that followed. The
skill was at 0.25.0 for the first two hours and 0.26.0 for the last one. Wall clock: ~3.5 h
for something that ends up taking ~8 minutes with the recipe at the end of this document.

## TL;DR — five findings the skill does not currently state

1. **The saved picture is a crop, not the viewport.** `computer` → `screenshot` with
   `save_to_disk: true` always wrote a **994×762 JPEG**. Calibration dots showed content at
   **0.9027 × 0.9031 picture px per logical px, offset ≈ 0**. The numbers fit one model
   exactly: the extension renders the 1376-logical (1720-physical) viewport at 1242 px wide —
   the skill's own "`--scale 0.7221` of 1720 physical" example — then saves only the
   **top-left 80 %** of it (1242×953 → 994×762). Consequence: `--viewport innerWidth`
   computes 994/1376 = 0.722 and every mark lands ~20 % short. The skill's central
   instruction for browser tabs is wrong for this output.
2. **A scroll right before capture gives a stale frame.** Scrolling ~2800 px and capturing
   returned frames with a huge blank area and the page header pinned near the bottom (twice
   byte-identical), or a 30 s `Page.captureScreenshot` timeout ("renderer unresponsive").
   The page's `getBoundingClientRect()` numbers were correct for the *final* state; the
   picture was of an *earlier* one. "Ask for the rectangles in the same breath" is not
   enough — the breath has to contain no scroll.
3. **`javascript_tool` does not await.** An `async` IIFE serialised as `{}`. Waits have to
   be a separate `computer` step; the JS must be synchronous.
4. **Background tabs are not free.** On this heavy page (~66 log rows with full stack
   traces) a background tab produced 3.4 KB blank JPEGs and capture timeouts. A fresh
   `tabs_create_mcp` tab (active by default) plus a 2 s wait fixed it; ~1 in 3 captures still
   timed out once and needed a retry. "A background tab works" needs qualifying.
5. **The `-p` shell-out is not the problem; the reasoning loop is.** Fully scripted
   `claude --chrome -p` (fixed JS, no page clicks, reply = one JSON line) took ~75 s per
   operation and was reliable. What burned two hours was (a) letting the sub-agent
   scroll-and-look, (b) a typo'd allowlist (`mcp__claude-in-chrome__javascript` instead of
   `…__javascript_tool`) which the sub-agent reported as "blocked by extension permissions",
   and (c) eyeballing scale factors from pictures. The skill's "never shell out" should say
   what actually fails.

## Environment

| | |
|---|---|
| Desktop | Ubuntu, X11, GNOME, `devicePixelRatio` 1.25 |
| Chrome viewport after the extension's resize | `innerWidth` 1376, `innerHeight` 1055 (`outerWidth` 1720 × 1319) |
| Extension | Claude in Chrome, driven via `claude --chrome -p` sub-sessions |
| Tool | programmers-screenshot 0.25.0 → 0.26.0 (deb from `dist/`) |
| Page | Kademi admin debug-session detail view, Bootstrap 3 tabs, log table in `#logs` |

## Timeline, compressed

| When | What happened | Why it cost time |
|---|---|---|
| 10:50–11:15 | Sub-agent told to "scroll until both lines are visible, verify with screenshots" | Unbounded visual loop on a page where the target rows are ~85 % down; killed after 20 min |
| 11:00 | First sub-agent said `javascript_tool` was "blocked by extension permissions" | It wasn't. The `--allowedTools` entry was `mcp__claude-in-chrome__javascript`. Every later run was designed around "no JS available" |
| 11:20–11:35 | `computer` screenshots came back with a large white area and the header near the bottom | Deep scroll + immediate capture (finding 2); mis-diagnosed as a foreground-tab problem |
| 11:40 | `programmers-screenshot --window "…Google Chrome"` worked perfectly | Then rejected because the front tab kept changing and the 0.26.0 skill says `--window` is wrong for tabs |
| 11:45 | Blank 3.4 KB saves while scrolling blind in a background tab | Finding 4; killed |
| 11:50 | Chris took the four screenshots by hand; annotation + PDF took ~2 min | The tool and the recipe were never the problem |
| 12:40 | 0.26.0 installed, skill reinstalled; asked to redo from scratch | — |
| 12:45 | First scripted `-p` capture: JS rects came back clean in ~60 s | Annotated at `--viewport 1376`: boxes ~20 % off the content (finding 1) |
| 12:55 | Probe: `dpr` 1.25; `--scale 1.25` *appeared* to land on the right rows | Coincidence on a stale frame — rows are ~54 px apart, the stale offset was ~66 px. Believed for 20 minutes |
| 13:00 | `body.style.zoom = 0.8` to fit the row in the crop | The full-width column just grew to fill the viewport again; two captures byte-identical stale frames |
| 13:05 | No-scroll recipe: hide other rows, move `#logs` to top, fixed-width wrapper | First fresh frame; rows visibly at ~0.91×, header at ~0.72× *by eye* — the eye was wrong |
| 13:10 | Two fixed magenta dots in the page, detected with PIL | Exact mapping per shot. Everything after this was routine |
| 13:15–13:30 | Five captures (two needed a retry), annotate, PDF | ~15 min including retries |

## Measured facts

Each row of the debug-session log table is a `<tr>`. Numbers are logical CSS px from
`getBoundingClientRect()` unless stated.

**Saved-picture geometry (from the two calibration dots, five shots, identical to 4 d.p.):**

| | |
|---|---|
| Picture size, every time | 994 × 762 |
| Scale x, y | 0.9027, 0.9031 |
| Offset x, y | −0.3, −0.6 |
| Implied visible area | ≈ 1101 × 844 logical px, anchored top-left |
| `994 / 0.9027` | 1101 — and `1242 × 0.8 = 994`, `1376 × 0.9027 = 1242` |

The 1242 is not a coincidence: Chris's hand-taken screenshots of the same tab were 1242 px
wide, and the skill's own example is a 1242-px picture of a 1720-physical viewport. So the
extension's full frame is 1242 wide; `save_to_disk` writes 80 % of it. Treat this as a model
that fits every number, not as confirmed against the extension's source.

**Stale frames.** With `payTr.scrollIntoView({block:'start'})` (both default and
`behavior:'instant'`) followed immediately by `computer` screenshot — with or without a 1 s
`computer` wait — two consecutive saves were byte-identical (35 792 B) and showed a
half-rasterised page. The measure step in the same `browser_batch` returned the correct
post-scroll rectangles. With no scroll at all (`scrollTo(0,0)` on a page rearranged so the
targets are at the top) every frame was fresh.

**Capture timeouts.** `Page.captureScreenshot timed out after 30000ms … renderer unresponsive`
occurred on 3 of 9 no-scroll captures immediately after the DOM rewrite, and on the scrolled
probe. One retry after a 2 s wait succeeded each time.

**Async.** `javascript_tool` returned `{}` for `(async () => {…})()`. Synchronous IIFEs
returning a `JSON.stringify` string were fine every time.

## What finally worked

Per operation, one sub-session, ~75 s, no page clicks, no scrolling, no reasoning:

```bash
claude --chrome -p "<script below>" --allowedTools \
  mcp__claude-in-chrome__tabs_create_mcp,mcp__claude-in-chrome__navigate,\
mcp__claude-in-chrome__javascript_tool,mcp__claude-in-chrome__computer,\
mcp__claude-in-chrome__browser_batch,mcp__claude-in-chrome__tabs_context_mcp,\
mcp__claude-in-chrome__list_connected_browsers,mcp__claude-in-chrome__select_browser,ToolSearch
```

Steps the sub-session is told to run, literally:

1. `tabs_create_mcp` — a fresh tab, active by default.
2. `navigate` to the operation's URL.
3. One unsaved `computer` screenshot, so the extension's window resize happens *before* measuring.
4. One `browser_batch`:
   - `javascript_tool`, synchronous: click the Logs tab; hide the sidebar; make the detail
     column full-width; **hide every `<tr>` outside the wanted range**; move `#logs` into a
     `width:790px` wrapper prepended to `<body>`; add two `position:fixed` 6-px `#ff00ff`
     dots at (30,30) and (770,600) — both outside the final crop; `scrollTo(0,0)`; return one
     JSON string with `getBoundingClientRect()` of each wanted row and the dot positions.
   - `computer` wait 2 s.
   - `computer` screenshot, `save_to_disk: true`; retry up to twice after another 2 s on a
     capture timeout.
5. Reply with exactly one line: that JSON plus `"file"`.

Then, locally, `annotate3.py` finds the two magenta blobs in the JPEG, solves
`scale = Δpicture / Δlogical` and `offset` per axis, converts the rectangles, and calls:

```bash
programmers-screenshot --recipe - -o out.png --no-clipboard <<'EOF'
{"input": "<file>", "region": [0, top, right, height], "annotate": [ …boxes/labels/arrow in picture px… ]}
EOF
```

No `--scale`, no `--viewport`: the coordinates are already in the picture's frame, and the
`region` excludes the dots. Files: `~/NetBeansProjects/kademi-dev/docs/gnm-raffle-timeouts-v2/`
(`capture5.sh`, `annotate3.py` with a `--selftest`, `cap5-*.json`, `shot-*.png`).

## Recommended changes to the skill text

Quoting the 0.26.0 "A browser tab, with Claude in Chrome" section and what to change.

1. **Replace the `--viewport innerWidth` instruction for `save_to_disk` output.** State the
   measured fact: the saved JPEG is 994×762 and is the top-left 80 % of a 1242-wide render
   of the viewport, so the right scale is `(picture_width / 0.8) / innerWidth`, not
   `picture_width / innerWidth`. Better: tell the agent to **calibrate instead of compute** —
   two fixed dots at known coordinates, detected in the picture. Better still, see the tool
   proposal below. Also say plainly: *never estimate a scale by eye from the picture* — two
   different wrong factors (0.72, 1.25) each "looked right" on the wrong frame.
2. **"Ask the page for its rectangles in the same batch as the screenshot" is necessary but
   not sufficient.** Add: *do not scroll in that batch*. If the target is off-screen,
   rearrange the DOM so it is on-screen at `scrollTo(0,0)` (hide rows, move the container to
   the top) rather than scrolling to it. Put a `computer` wait of ~2 s between the DOM change
   and the capture, and expect to retry a capture timeout once.
3. **`javascript_tool` is synchronous.** Say it: no `await`, no promises; return a
   `JSON.stringify` string.
4. **Qualify "a background tab works; nothing has to be brought to the front".** True for a
   light page that is not scrolled. On a heavy page it gave blank saves and capture
   timeouts. Recommend `tabs_create_mcp` for a fresh active tab and say why.
5. **Rewrite the "never shell out to `claude --chrome -p`" paragraph.** The failure mode is a
   sub-agent *deciding* things (scrolling, looking, retrying). A fully scripted `-p` with fixed
   JS and a one-line JSON reply is fine and is currently the only route when the session was
   not started with `--chrome` (there is no `/chrome` command in this CLI build). Give the
   exact `--allowedTools` names; the `javascript_tool` name in particular.
6. **Keep the `--window` warning but make it honest.** `--window "… - Google Chrome"` gave a
   perfect full-window capture on the first try; its real weakness is that the front tab can
   change, and it needs the recipes switch. It is a legitimate fallback when the tab can be
   kept in front for two seconds.
7. **The `--input` example should show a `region`** that trims browser/page chrome, since the
   saved frame includes the page's sticky header.

## Proposal for the tool (optional, small)

- **`--calibrate X1,Y1,X2,Y2`** for `--input`: the page drew two dots at those logical
  coordinates; the tool finds the two most saturated magenta blobs, solves scale and offset
  per axis, and uses them in place of `--scale`/`--viewport`. Print the solved values. This is
  ~40 lines (it exists as `annotate3.py::mapping`) and removes the whole class of "which
  factor is it" errors for any browser, DPR or crop.
- **Sanity warning on `--viewport`** when the input is exactly 994×762: "this looks like a
  cropped Claude-in-Chrome save; `--viewport` will under-scale by 20 %".
- `--input` currently prints a path and nothing else — keep that; it made scripting easy.

## Open questions

- Why 80 %? The extension's `computer` canvas was 994×762 in an earlier run; the saved file may
  simply be the canvas-sized crop of the full render. Not verified against the extension.
- Whether `computer` has a real `wait` action. The sub-agents were told "wait 2 s, or take an
  unsaved screenshot as the pause if `wait` is not valid" and did not report which they used.
- The ~1-in-3 capture timeout right after a large DOM rewrite. A lighter selector than
  `querySelectorAll('#logs *')` might help; not tested.

## Appendix — the synchronous setup JS that worked

```js
(() => {
 document.querySelector('#operation-details-tabs a[href="#logs"]').click();
 const logs = document.querySelector('#logs');
 const m = s => [...logs.querySelectorAll('*')].filter(e => e.textContent.includes(s) && ![...e.children].some(c => c.textContent.includes(s)))[0];
 const tr = s => { const e = m(s); return e ? e.closest('tr') : null; };
 const pay = tr('Sending bundled raffle order to Scorecard'), open = tr('open: method=POST url=https://i3services-uat.hinda.com/catalog/orders');
 const errEl = m('TimeoutException Request timeout') || m('Scorecard raffle bundle response status'); const err = errEl.closest('tr');
 const kind = errEl.textContent.includes('TimeoutException') ? 'timeout' : 'response';
 const status = tr('Scorecard raffle bundle response status');
 const rows = [...pay.parentElement.children]; const i = rows.indexOf(pay); let j = rows.indexOf(status); if (kind === 'response') j = j + 1;
 rows.forEach((r, k) => { if (k < i || k > j) r.style.display = 'none'; });
 const wrap = document.createElement('div'); wrap.style.cssText = 'width:790px;margin:84px 0 0 4px;background:#fff';
 wrap.appendChild(logs); logs.style.display = 'block'; logs.classList.add('active', 'in'); document.body.prepend(wrap);
 const dot = (x, y) => { const d = document.createElement('div'); d.style.cssText = 'position:fixed;left:' + x + 'px;top:' + y + 'px;width:6px;height:6px;background:#ff00ff;z-index:2147483647;pointer-events:none'; document.body.appendChild(d); return [x, y, 6, 6]; };
 const markers = [dot(30, 30), dot(770, 600)];
 window.scrollTo(0, 0);
 const R = e => { if (!e) return null; const b = e.getBoundingClientRect(); return [Math.round(b.x), Math.round(b.y), Math.round(b.width), Math.round(b.height)]; };
 return JSON.stringify({dpr: devicePixelRatio, innerWidth, innerHeight, scrollY: Math.round(scrollY), markers, payload: R(pay), open: R(open), error: R(err), status: R(status), extra: R(kind === 'response' ? rows[j] : null), errKind: kind});
})()
```

## Files alongside this document

`docs/postmortem-2026-09-03-files/`:

- `capture5.sh` — the scripted `claude --chrome -p` driver (one operation per run, one JSON line out).
- `annotate3.py` — dot detection, mapping, recipe build; `python3 annotate3.py --selftest` exercises the mapping.
- `cap5-hcsitx8.json` — a real reply: rectangles in logical px plus the saved file path.
- `sample-save_to_disk-994x762.jpg` — a **synthetic stand-in** for the saved picture: the same 994×762, the two dots where
  they measured in the real one, the rows as grey blocks. The real capture showed a customer's name, address, email,
  phone and a signature token, so it stays out of the repository.

## Follow-up (same day, issue #58, shipped in 0.27.0)

Re-checked before acting on the above:

- **The geometry fits one number, not a crop model.** Re-finding the dots in the sample gave
  0.9024 × 0.9027 with offset −0.1, −0.3. That is `picture width × devicePixelRatio /
  innerWidth` = 994 × 1.25 / 1376 = 0.9030, and at DPR 1 the same formula is this morning's
  pixel-exact 1242 / 1720. The "top-left 80 %" is 1 / 1.25. So `--dpr` was added and
  `--viewport` stays; `--calibrate` was not built, since no measured number needs it.
- **`javascript_tool` does await, at the top level.** `(async () => 42)()` comes back as `{}`
  because a returned Promise serialises to nothing; `await (async () => 42)()` comes back as
  `42`, and awaiting a 300 ms timer resolves. Synchronous code stays the safest advice.
- **`computer` has a real `wait` action**, 1–10 s. That was one of the open questions.
- **`/chrome` exists** in Claude Code 2.1.259 — it opens the Claude in Chrome settings — so the
  skill's mention of it stands.
- The render width is not a constant 1242: another window here gave 1288 × 946 for a
  1720 × 1263 viewport. Nothing should hard-code it; the `computer` result text reports the
  saved picture's size anyway.
- Stale frames after a scroll, blank saves from a background tab on a heavy page, and the
  capture timeouts were taken as reported; they need the heavy page to reproduce.
