#!/bin/bash
# capture5.sh <opId> -> last line: JSON {file, markers, payload, open, error, status, extra, errKind}
OP="$1"
timeout 500 claude --chrome -p "Load claude-in-chrome tool schemas via ToolSearch (select: mcp__claude-in-chrome__tabs_create_mcp, mcp__claude-in-chrome__navigate, mcp__claude-in-chrome__javascript_tool, mcp__claude-in-chrome__computer, mcp__claude-in-chrome__browser_batch). Be literal, max 9 tool calls, never click a page link, never scroll.

1. tabs_create_mcp - open a NEW tab and work in it.
2. navigate it to https://gamesandmore.admin.kademiplay.com/dev-tools/sessions/yq4k90u?debugSession=yq4k90u&opId=$OP
3. computer action 'screenshot' (not saved).
4. ONE browser_batch, steps in order:
 (a) javascript_tool (synchronous):
(() => {
 document.querySelector('#operation-details-tabs a[href=\"#logs\"]').click();
 const logs = document.querySelector('#logs');
 const m = s => [...logs.querySelectorAll('*')].filter(e => e.textContent.includes(s) && ![...e.children].some(c => c.textContent.includes(s)))[0];
 const tr = s => { const e = m(s); return e ? e.closest('tr') : null; };
 const pay = tr('Sending bundled raffle order to Scorecard'), open = tr('open: method=POST url=https://i3services-uat.hinda.com/catalog/orders');
 const errEl = m('TimeoutException Request timeout') || m('Scorecard raffle bundle response status'); const err = errEl.closest('tr');
 const kind = errEl.textContent.includes('TimeoutException') ? 'timeout' : 'response';
 const status = tr('Scorecard raffle bundle response status');
 const rows = [...pay.parentElement.children]; const i = rows.indexOf(pay); let j = rows.indexOf(status); if (kind === 'response') j = j + 1;
 const extra = kind === 'response' ? rows[j] : null;
 rows.forEach((r, k) => { if (k < i || k > j) r.style.display = 'none'; });
 const wrap = document.createElement('div'); wrap.style.cssText = 'width:790px;margin:84px 0 0 4px;background:#fff';
 wrap.appendChild(logs); logs.style.display = 'block'; logs.classList.add('active', 'in'); document.body.prepend(wrap);
 const dot = (x, y) => { const d = document.createElement('div'); d.style.cssText = 'position:fixed;left:' + x + 'px;top:' + y + 'px;width:6px;height:6px;background:#ff00ff;z-index:2147483647;pointer-events:none'; document.body.appendChild(d); return [x, y, 6, 6]; };
 const markers = [dot(30, 30), dot(770, 600)];
 window.scrollTo(0, 0);
 const R = e => { if (!e) return null; const b = e.getBoundingClientRect(); return [Math.round(b.x), Math.round(b.y), Math.round(b.width), Math.round(b.height)]; };
 return JSON.stringify({dpr: devicePixelRatio, innerWidth: innerWidth, innerHeight: innerHeight, scrollY: Math.round(scrollY), markers: markers, payload: R(pay), open: R(open), error: R(err), status: R(status), extra: R(extra), errKind: kind, shown: j - i + 1});
})()
 (b) computer action 'wait' 2 seconds (if 'wait' is not valid, take one unsaved screenshot as the pause).
 (c) computer action 'screenshot' with save_to_disk: true
 If (c) fails with a capture timeout, retry (c) up to two more times, each after another 2 second wait.
5. Reply with ONLY one line: the (a) JSON with a \"file\" key added holding the saved path (or \"file\":null if no screenshot could be saved)." --allowedTools "mcp__claude-in-chrome__tabs_create_mcp,mcp__claude-in-chrome__navigate,mcp__claude-in-chrome__javascript_tool,mcp__claude-in-chrome__computer,mcp__claude-in-chrome__browser_batch,mcp__claude-in-chrome__tabs_context_mcp,mcp__claude-in-chrome__list_connected_browsers,mcp__claude-in-chrome__select_browser,ToolSearch" 2>&1 < /dev/null | grep -v "^Permission allow rule" | tail -1
