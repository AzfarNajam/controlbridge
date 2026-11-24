"""Self-contained offline dashboard for one immutable assessment run."""

import html
import json
from pathlib import Path


def render_dashboard(report, document=None):
    esc = lambda value: html.escape(str(value), quote=True)
    evidence = {item['id']: item for item in (document or {}).get('evidence', [])}
    cards, panels = [], []
    for index, row in enumerate(report['assessments']):
        item = evidence.get(row['evidence_id'])
        status = esc(row['result'])
        cards.append(f'''<button class="record" data-status="{status}" data-index="{index}" aria-controls="detail-{index}" aria-pressed="{'true' if index == 0 else 'false'}"><span class="record-top"><span>{esc(row['evidence_id'])}</span><span class="badge {status}">{status.upper()}</span></span><strong>{esc(row['resource_id'])}</strong><span>View evidence and explanation</span></button>''')
        raw = esc(json.dumps(item, indent=2)) if item else 'Original evidence unavailable in this view.'
        if item:
            value = item['properties'].get('allowBlobPublicAccess')
            setting = 'Missing / null' if value is None else str(value).lower()
            facts = f'''<dl><dt>Public blob access setting</dt><dd><code>{esc(setting)}</code></dd><dt>Collection status</dt><dd>{esc(item['collection_status'])}</dd><dt>Collected at</dt><dd>{esc(item['collected_at'])}</dd><dt>Source</dt><dd>{esc(item['source'])}</dd></dl>'''
        else:
            facts = '<p>Open the original evidence download for this record.</p>'
        panels.append(f'''<article id="detail-{index}" class="detail" {'hidden' if index else ''}><div class="detail-heading"><div><p class="eyebrow">Selected evidence · {esc(row['evidence_id'])}</p><h2>{esc(row['resource_id'])}</h2></div><span class="badge {status}">{status.upper()}</span></div><div class="comparison"><section><h3>What we observed</h3><p class="muted">The input supplied to the assessment.</p>{facts}</section><section><h3>What it means</h3><p class="reason">{esc(row['reason'])}</p><p><strong>The rule:</strong> <code>allowBlobPublicAccess</code> must be explicitly <code>false</code>.</p><p>Collection must succeed and evidence must be between 0 and 24 hours old at assessment time. Otherwise the result is unknown.</p><p class="muted">{esc(row['control_id'])} · Rule version {esc(row['rule_version'])}</p></section></div><details><summary>Inspect original evidence JSON</summary><pre>{raw}</pre></details></article>''')
    template = Path(__file__).with_name('dashboard.html').read_text(encoding='utf-8')
    replacements = {
        'CARDS': ''.join(cards), 'PANELS': ''.join(panels),
        'AS_OF': esc(report['as_of']), 'HASH': esc(report['input_sha256']),
        'TOTAL': str(len(report['assessments'])),
        **{key.upper(): str(report['summary'][key]) for key in ('pass', 'fail', 'unknown')},
    }
    import re
    return re.sub(r'@@([A-Z_]+)@@', lambda match: replacements[match[1]], template)
