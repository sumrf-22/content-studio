const fs = require('fs');
const path = 'static/style.css';
let s = fs.readFileSync(path, 'utf8');

const repl = [
  ['    --accent: #6c5ce7;', '    --accent: #22c55e;'],
  ['    --accent-glow: rgba(108, 92, 231, 0.35);', '    --accent-glow: rgba(34, 197, 94, 0.25);'],
  ['    --accent-2: #00cec9;', '    --accent-2: #0d9488;'],
  ['    --accent-3: #fd79a8;', '    --accent-3: #be123c;'],
  ['    --success: #2ecc71;', '    --success: #22c55e;'],
  ['    --info: #3498db;', '    --info: #2563eb;'],
  [/font-size: 10px;\s*color: var\(--text-dim\);\s*text-transform: capitalize;/, '    font-size: 11px;\n    color: var(--text-dim);\n    text-transform: capitalize;'],
  [/font-size: 10px;\s*color: var\(--text-dim\);\s*font-weight: 500;\s*min-width: 65px;/, '    font-size: 11px;\n    color: var(--text-dim);\n    font-weight: 500;\n    min-width: 65px;'],
  [/font-size: 10px;\s*color: var\(--text-dim\);\s*font-weight: 500;\s*line-height: 1.4;/, '    font-size: 11px;\n    color: var(--text-dim);\n    font-weight: 500;\n    line-height: 1.4;'],
  [/font-size: 11px;\s*color: var\(--text-muted\);\s*font-weight: 600;\s*line-height: 1.3;/, '    font-size: 12px;\n    color: var(--text-muted);\n    font-weight: 600;\n    line-height: 1.3;'],
  [/font-size: 11px;\s*color: var\(--text-muted\);\s*font-weight: 500;/, '    font-size: 12px;\n    color: var(--text-muted);\n    font-weight: 500;'],
];

let count = 0;
for (const entry of repl) {
  let re;
  if (typeof entry[0] === 'string') {
    re = new RegExp(entry[0].replace(/[.*+/?^${}()|[\]\\]/g, '\\$&'), 's');
  } else {
    re = entry[0];
  }
  const idx = s.search(re);
  if (idx !== -1) {
    s = s.slice(0, idx) + entry[1] + s.slice(idx + re.source.length);
    count++;
  } else {
    console.log('NOT FOUND:', (typeof entry[0] === 'string' ? entry[0] : re.source).slice(0, 60));
  }
}
fs.writeFileSync(path, s, 'utf8');
console.log('Applied:', count, 'of', repl.length);
