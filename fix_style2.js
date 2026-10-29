const fs = require('fs');
const path = 'static/style.css';
let s = fs.readFileSync(path, 'utf8');

// Build regexes: {pattern, replacement}
const cases = [
  {
    re: /font-size: 10px;\s*font-weight: 600;\s*text-transform: uppercase;\s*letter-spacing: 0\.5px;\s*padding: 3px 8px;/g,
    rep: 'font-size: 11px;\n    font-weight: 600;\n    text-transform: uppercase;\n    letter-spacing: 0.5px;\n    padding: 3px 8px;'
  },
  {
    re: /font-size: 10px;\s*color: var\(--text-dim\);\s*text-transform: capitalize;/g,
    rep: 'font-size: 11px;\n    color: var(--text-dim);\n    text-transform: capitalize;'
  },
  {
    re: /font-size: 11px;\s*color: var\(--text-muted\);\s*font-weight: 600;\s*line-height: 1\.3;/g,
    rep: 'font-size: 12px;\n    color: var(--text-muted);\n    font-weight: 600;\n    line-height: 1.3;'
  },
  {
    re: /font-size: 11px;\s*color: var\(--text-dim\);\s*font-weight: 500;\s*min-width: 65px;/g,
    rep: 'font-size: 12px;\n    color: var(--text-dim);\n    font-weight: 500;\n    min-width: 65px;'
  },
  {
    re: /font-size: 11px;\s*color: var\(--text-muted\);\s*font-weight: 500;/g,
    rep: 'font-size: 12px;\n    color: var(--text-muted);\n    font-weight: 500;'
  }
];

let count = 0;
for (const c of cases) {
  let m;
  while ((m = c.re.exec(s)) !== null) {
    s = s.slice(0, m.index) + c.rep + s.slice(m.index + m[0].length);
    count++;
  }
}

fs.writeFileSync(path, s, 'utf8');
console.log('Applied:', count, 'of', cases.length);
