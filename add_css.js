const fs = require('fs');
const path = 'static/style.css';
const block = `
/* ============================================================
   APPROVAL QUEUE — REVIEW / REJECT
   ============================================================ */

.approval-card {
    max-width: 720px;
}

.approval-list {
    display: flex;
    flex-direction: column;
    gap: 10px;
}

.approval-item {
    display: flex;
    flex-direction: column;
    gap: 10px;
    padding: 14px;
    background: var(--bg-card-hover);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    transition: border-color 0.2s;
}

.approval-item:hover {
    border-color: var(--accent);
}

.approval-head {
    display: flex;
    align-items: center;
    gap: 12px;
}

.approval-badge {
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    padding: 5px 10px;
    border-radius: var(--radius-sm);
}

.approval-badge-idea {
    background: rgba(34, 197, 94, 0.15);
    color: var(--success);
}

.approval-badge-copy {
    background: rgba(52, 152, 219, 0.15);
    color: var(--info);
}

.approval-badge-design {
    background: rgba(245, 158, 11, 0.15);
    color: var(--warning);
}

.approval-topic {
    font-size: 13px;
    font-weight: 600;
    color: var(--text);
    flex: 1;
}

.approval-stage-row {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 8px;
}

.approval-stage {
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: var(--text-muted);
}

.approval-preview {
    display: flex;
    flex-direction: column;
    gap: 6px;
    min-height: 60px;
    padding: 10px;
    background: var(--bg);
    border-radius: var(--radius-sm);
    border: 1px solid var(--border);
}

.preview-stage-row {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 6px 8px;
    background: var(--bg-card);
    border-radius: var(--radius-sm);
    font-size: 12px;
}

.idea-radio {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 18px;
    height: 18px;
    border-radius: 50%;
    border: 2px solid var(--border);
    flex-shrink: 0;
    cursor: pointer;
}

.idea-radio input {
    display: none;
}

.idea-radio input:checked + .idea-title {
    color: var(--text);
    font-weight: 600;
}

.idea-title {
    font-size: 12px;
    color: var(--text-muted);
    font-weight: 500;
}

.idea-format {
    font-size: 10px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: var(--text-dim);
    background: var(--bg);
    padding: 2px 8px;
    border-radius: 20px;
}

.approval-actions {
    display: flex;
    gap: 8px;
}

.reject-btn {
    background: rgba(231, 76, 60, 0.15);
    color: var(--danger);
    border: 1px solid rgba(231, 76, 60, 0.3);
}

.reject-btn:hover {
    background: rgba(231, 76, 60, 0.25);
    color: var(--danger);
}
`;
const s = fs.readFileSync(path, 'utf8');
if (s.includes('APPROVAL QUEUE — REVIEW / REJECT')) {
    console.log('already present');
} else {
    // Insert before the AI AGENT PIPELINE section
    const j = s.indexOf('/* ============================================================\n   AI AGENT PIPELINE');
    if (j === -1) {
        // fallback: append before final comment
        const k = s.lastIndexOf('/* ============================================================\n   AI AGENT PIPELINE');
        fs.writeFileSync(path, s + block, 'utf8');
    } else {
        fs.writeFileSync(path, s.slice(0, j) + block + s.slice(j), 'utf8');
    }
    console.log('CSS appended, length', fs.readFileSync(path, 'utf8').length);
}
