#!/usr/bin/env python3
"""annotate3.py <cap.json> <out.png>
Finds the two magenta calibration dots in the capture, derives the exact logical->picture mapping,
converts the page's rectangles, and draws outlines/labels/arrow with programmers-screenshot (--input, no --scale)."""
import json, subprocess, sys
from PIL import Image

def find_dots(im):
    """Return centres of magenta blobs, sorted by x."""
    px = im.convert("RGB").load(); w, h = im.size; pts = []
    for y in range(h):
        for x in range(w):
            r, g, b = px[x, y]
            if r > 180 and b > 180 and g < 90: pts.append((x, y))
    if not pts: return []
    # cluster by proximity (dots are far apart)
    clusters = []
    for p in pts:
        for c in clusters:
            if abs(c[0][0] - p[0]) < 30 and abs(c[0][1] - p[1]) < 30: c.append(p); break
        else: clusters.append([p])
    return sorted([(sum(x for x, _ in c) / len(c), sum(y for _, y in c) / len(c)) for c in clusters])

def mapping(cap, im):
    (lx1, ly1, s, _), (lx2, ly2, _, _) = cap["markers"]
    dots = find_dots(im)
    assert len(dots) == 2, f"expected 2 calibration dots, found {len(dots)}"
    (ix1, iy1), (ix2, iy2) = dots
    lc1, lc2 = (lx1 + s / 2, ly1 + s / 2), (lx2 + s / 2, ly2 + s / 2)
    sx = (ix2 - ix1) / (lc2[0] - lc1[0]); sy = (iy2 - iy1) / (lc2[1] - lc1[1])
    ox = ix1 - lc1[0] * sx; oy = iy1 - lc1[1] * sy
    return sx, sy, ox, oy

def to_pic(rect, m):
    sx, sy, ox, oy = m; x, y, w, h = rect
    return [round(x * sx + ox), round(y * sy + oy), round(w * sx), round(h * sy)]

def build(cap, im):
    m = mapping(cap, im); sx, sy, ox, oy = m
    pay = to_pic(cap["payload"], m); err = to_pic(cap["error"], m)
    last = to_pic(cap["extra"] or cap["status"], m)
    timeout = cap["errKind"] == "timeout"
    pad = 3
    box = lambda r, c: {"box": [r[0] - pad, r[1] - pad, r[2] + 2 * pad, r[3] + 2 * pad], "colour": c, "width": 3}
    ann = [box(pay, "blue"),
           {"label": [pay[0] + pay[2] - 230, pay[1] + pay[3] - 27], "text": "JSON sent to Scorecard", "colour": "blue", "background": True, "size": 17},  # on the row's subtext line
           box(err, "red" if timeout else "amber"),
           {"label": [err[0] + err[2] - (240 if timeout else 280), err[1] + err[3] - (27 if timeout else 34)],  # on the row's subtext line
            "text": "Scorecard never replied" if timeout else "Scorecard replied: HTTP 400", "colour": "red" if timeout else "amber", "background": True, "size": 17},
           {"arrow": [[pay[0] + pay[2] - 60, pay[1] + pay[3] + 4], [err[0] + err[2] - 120, err[1] - 2]], "colour": "red" if timeout else "amber", "width": 3}]
    if not timeout and cap["extra"]: ann.append(box(last, "red"))
    # crop: from just under the page header to just under the last row; markers fall outside
    top = pay[1] - 12; bottom = last[1] + last[3] + 12
    region = [0, top, round(800 * sx + ox), bottom - top]
    return {"input": cap["file"], "region": region, "annotate": ann}, m

if __name__ == "__main__":
    if sys.argv[1] == "--selftest":
        im = Image.new("RGB", (420, 340), "white")
        for cx, cy in [(30 * .5 + 3 * .5, 30 * .5 + 3 * .5), (770 * .5 + 1.5, 600 * .5 + 1.5)]:
            for dx in range(3):
                for dy in range(3): im.putpixel((int(cx) + dx - 1, int(cy) + dy - 1), (255, 0, 255))
        cap = {"markers": [[30, 30, 6, 6], [770, 600, 6, 6]]}
        sx, sy, ox, oy = mapping(cap, im)
        assert abs(sx - .5) < .02 and abs(sy - .5) < .02 and abs(ox) < 2 and abs(oy) < 2, (sx, sy, ox, oy)
        print("selftest ok: scale", round(sx, 3), round(sy, 3), "offset", round(ox, 1), round(oy, 1)); sys.exit(0)
    cap = json.load(open(sys.argv[1])); im = Image.open(cap["file"])
    recipe, (sx, sy, ox, oy) = build(cap, im)
    print(f"mapping: scale {sx:.4f} x {sy:.4f}, offset {ox:.1f},{oy:.1f}; region {recipe['region']}")
    p = subprocess.run(["programmers-screenshot", "--recipe", "-", "-o", sys.argv[2], "--no-clipboard"], input=json.dumps(recipe), text=True, capture_output=True)
    print(p.stdout.strip() or p.stderr.strip()); sys.exit(p.returncode)
