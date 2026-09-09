(() => {
    const root = document.getElementById('work-app');
    const csrf = root.dataset.csrf;
    const message = document.getElementById('work-message');
    const $ = id => document.getElementById(id);
    const escape = text => String(text ?? '').replace(/[&<>"']/g, c => ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;'
    } [c]));
    const duration = seconds => {
        const s = Math.floor(seconds);
        return `${Math.floor(s / 3600)}:${String(Math.floor(s % 3600 / 60)).padStart(2,'0')}:${String(s % 60).padStart(2,'0')}`;
    };
    let workItems = [],
        nextBefore = null;
    async function request(path, data, method = 'POST') {
        const response = await fetch(path, {
            method,
            headers: {
                'Content-Type': 'application/json',
                'X-CSRF-Token': csrf
            },
            ...(method !== 'GET' ? {
                body: JSON.stringify(data)
            } : {})
        });
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || 'Request failed.');
        return result;
    }
    const api = (action, data = {}) => request('/api/agent/' + action, data);
    const pendingMutations = new Map();
    async function mutate(action, data = {}) {
        const fingerprint = JSON.stringify([action, data]);
        const request_id = pendingMutations.get(fingerprint) || crypto.randomUUID();
        pendingMutations.set(fingerprint, request_id);
        const result = await api(action, {
            request_id,
            ...data
        });
        pendingMutations.delete(fingerprint);
        return result;
    }

    function notify(text, error = false) {
        message.textContent = text;
        message.classList.toggle('error', error);
    }
    async function perform(button, operation) {
        if (button) button.disabled = true;
        try {
            await operation();
        } catch (e) {
            notify(e.message, true);
        } finally {
            if (button) button.disabled = false;
        }
    }
    const metric = (label, value) => `<div class="metric"><dt>${label}</dt><dd>${duration(value)}</dd></div>`;

    function renderWork() {
        const open = new Set([...document.querySelectorAll('#work-list details[open]')].map(x => x.dataset.receipt));
        $('work-list').innerHTML = workItems.length ? workItems.map(w => {
            const human = w.spans.some(s => s.actor_id === 'me' && !s.ended_at);
            const waiting = w.spans.some(s => s.actor_id === 'my-wait' && !s.ended_at);
            return `<article class="panel work-card" id="work-${w.id}"><div class="panel-head"><div><span class="eyebrow">${escape(w.client_name)} / #${w.id}</span><h3>${escape(w.title)}</h3></div><span class="badge ${w.finished_at?'':'active'}">${w.approved_at?'Reviewed':w.finished_at?'Finished':'Open'}</span></div>
            <dl class="metrics">${metric('Elapsed',w.elapsed_seconds)}${metric('Human effort',w.human_seconds)}${metric('Agent total',w.agent_seconds)}${metric('Waiting',w.waiting_seconds)}</dl>
            <p class="quiet mono">Agent budget ${w.finished_at?'unused':'remaining'} ${duration(w.budget_remaining_seconds)} · ${w.spans.filter(s=>!s.ended_at&&s.actor_kind==='agent').length} agents active</p>
            ${w.warnings.map(t=>`<p class="notice">${escape(t)}</p>`).join('')}
            ${!w.finished_at?`<div class="action-row"><button class="btn" data-work="${w.id}" data-action="human" data-active="${human}">${human?'Pause my work':'Resume my work'}</button><button class="btn" data-work="${w.id}" data-action="waiting" data-active="${waiting}">${waiting?'Stop waiting':'Track waiting'}</button><button class="btn" data-work="${w.id}" data-action="evidence">Add evidence</button><button class="btn btn-primary" data-work="${w.id}" data-action="finish">Finish session</button></div>`:''}
            <details data-receipt="${w.id}" ${open.has(String(w.id))?'open':''}><summary>Receipt · actors, events, and evidence</summary><ul class="receipt-events">${w.spans.map(s=>`<li><span class="badge">${escape(s.actor_kind)}</span> ${escape(s.actor_id)} · <span class="mono">${duration(s.seconds)}</span> <span class="quiet">${escape(s.stop_reason||'active')}</span></li>`).join('')}</ul><ol class="receipt-events">${w.events.map(e=>`<li><time>${escape(new Date(e.at).toLocaleString())}</time> · ${escape(e.kind.replaceAll('_',' '))}<div class="quiet">${escape(e.actor_id||'')} · ${escape(e.source)}</div><div>${escape(e.data.text||e.data.summary||'')}</div>${e.data.url?`<a href="${escape(e.data.url)}" target="_blank" rel="noopener noreferrer">${escape(e.data.url)}</a>`:''}</li>`).join('')}</ol><button class="btn" data-action="download" data-work="${w.id}">Download receipt JSON</button></details></article>`;
        }).join('') : '<div class="panel empty-state">No work sessions yet. Start your first session above or connect an agent.</div>';
        $('more-work').classList.toggle('hidden', !nextBefore);
    }
    async function loadWork(older = false) {
        const result = await api('list_work', older ? {
            before_id: nextBefore
        } : {});
        workItems = older ? [...workItems, ...result.work] : result.work;
        nextBefore = result.next_before_id;
        renderWork();
    }
    $('refresh-work').onclick = e => perform(e.currentTarget, () => loadWork());
    $('more-work').onclick = e => perform(e.currentTarget, () => loadWork(true));
    $('start-work')?.addEventListener('submit', e => {
        e.preventDefault();
        const f = e.target;
        perform(f.querySelector('button'), async () => {
            const data = new FormData(f);
            await mutate('start_work', {
                title: data.get('title'),
                client_id: Number(data.get('client_id')),
                budget_seconds: Number(data.get('budget')) * 60,
                actor_id: 'me',
                actor_kind: 'human'
            });
            f.elements.title.value = '';
            notify('Session started.');
            await loadWork();
        });
    });
    $('work-list').onclick = e => {
        const button = e.target.closest('button[data-action]');
        if (!button) return;
        const work_id = Number(button.dataset.work),
            action = button.dataset.action;
        perform(button, async () => {
            if (action === 'download') {
                const w = (await api('get_work', {
                    work_id
                })).work;
                const url = URL.createObjectURL(new Blob([JSON.stringify(w, null, 2)], {
                    type: 'application/json'
                }));
                const a = document.createElement('a');
                a.href = url;
                a.download = `timerrr-receipt-${work_id}.json`;
                a.click();
                setTimeout(() => URL.revokeObjectURL(url), 1000);
                return;
            }
            if (action === 'evidence') {
                openEvidence(work_id);
                return;
            }
            if (action === 'finish') await mutate('finish_work', {
                work_id,
                summary: 'Session finished from the workspace.'
            });
            else {
                const actor_id = action === 'human' ? 'me' : 'my-wait',
                    actor_kind = action === 'human' ? 'human' : 'waiting';
                if (button.dataset.active !== 'true') {
                    const otherActor = action === 'human' ? 'my-wait' : 'me';
                    const latest = (await api('get_work', {
                        work_id
                    })).work;
                    if (latest.spans.some(s => s.actor_id === otherActor && !s.ended_at)) await mutate('record_work_event', {
                        work_id,
                        kind: 'actor_stopped',
                        actor_id: otherActor
                    });
                }
                await mutate('record_work_event', {
                    work_id,
                    kind: button.dataset.active === 'true' ? 'actor_stopped' : 'actor_started',
                    actor_id,
                    actor_kind
                });
            }
            notify('Work updated.');
            await loadWork();
        });
    };

    function openEvidence(work_id) {
        document.querySelector('#evidence-dialog')?.remove();
        const dialog = document.createElement('dialog');
        dialog.id = 'evidence-dialog';
        dialog.className = 'panel';
        dialog.style.maxWidth = '500px';
        dialog.innerHTML = '<form class="form-grid"><h2 class="form-wide">Add evidence</h2><label class="form-wide">Note<textarea name="text" required maxlength="4000" rows="3"></textarea></label><label class="form-wide">Artifact URL · optional<input name="url" type="url" maxlength="2000" placeholder="https://…"></label><div class="action-row form-wide"><button class="btn btn-primary">Save evidence</button><button class="btn" type="button" id="cancel-evidence">Cancel</button></div><p class="quiet form-wide" role="alert" id="evidence-error"></p></form>';
        document.body.append(dialog);
        dialog.showModal();
        dialog.querySelector('#cancel-evidence').onclick = () => dialog.close();
        dialog.querySelector('form').onsubmit = async e => {
            e.preventDefault();
            const f = e.target;
            const button = f.querySelector('button');
            button.disabled = true;
            try {
                await mutate('record_work_event', {
                    work_id,
                    kind: f.elements.url.value ? 'artifact' : 'note',
                    text: f.elements.text.value,
                    ...(f.elements.url.value ? {
                        url: f.elements.url.value
                    } : {})
                });
                dialog.close();
                await loadWork();
            } catch (error) {
                dialog.querySelector('#evidence-error').textContent = error.message;
            } finally {
                button.disabled = false;
            }
        };
    }
    async function loadTokens() {
        const r = await request('/api/agent-tokens', null, 'GET');
        $('token-list').innerHTML = r.tokens.map(t => `<div class="token-row"><div><strong>${escape(t.name)}</strong><div class="quiet">${t.revoked_at?'Revoked':`Expires ${escape(new Date(t.expires_at).toLocaleDateString())}`}</div><div class="quiet">${escape(t.scopes.join(', '))}</div></div>${!t.revoked_at?`<button class="btn btn-danger" data-token="${t.id}">Revoke</button>`:''}</div>`).join('');
    }
    $('token-form').onsubmit = e => {
        e.preventDefault();
        const f = e.target;
        perform(f.querySelector('button'), async () => {
            const r = await request('/api/agent-tokens', {
                name: f.elements.name.value,
                scopes: [...f.querySelectorAll('input:checked')].map(x => x.value)
            });
            $('token-value').textContent = r.token;
            $('new-token').hidden = false;
            await loadTokens();
        });
    };
    $('hide-token').onclick = () => {
        $('token-value').textContent = '';
        $('new-token').hidden = true;
    };
    $('token-list').onclick = e => {
        const b = e.target.closest('[data-token]');
        if (b) perform(b, async () => {
            await request('/api/agent-tokens/' + b.dataset.token, {}, 'DELETE');
            await loadTokens();
            notify('Token revoked.');
        });
    };

    function localValue(iso) {
        const d = new Date(iso);
        return new Date(d - d.getTimezoneOffset() * 60000).toISOString().slice(0, 23);
    }
    async function loadDrafts() {
        const r = await api('list_drafts');
        $('draft-list').innerHTML = r.drafts.map(d => `<button class="btn" data-draft="${d.id}">#${d.id} · ${d.approved_at?'Reviewed':'Draft'}</button>`).join('');
    }

    function reviewedTime(row, field, draft) {
        const input = row.querySelector(`[name=${field}]`);
        const original = draft.rows.find(item => item.row_id === Number(row.dataset.row));
        // datetime-local truncates server microseconds. Preserve untouched evidence exactly.
        return input.value === input.dataset.initialValue ? original[field + '_time'] : new Date(input.value).toISOString();
    }

    function renderDraft(d) {
        const section = $('draft-review');
        section.innerHTML = `<hr class="section-divider"><h2>Draft #${d.id}${d.approved_at?' · reviewed':''}</h2>${d.limitations.map(x=>`<p class="quiet">${escape(x)}</p>`).join('')}<p class="quiet">${d.receipts.length} sessions · ${d.rows.length} proposed human intervals. Times below use your local timezone.</p>${d.receipts.map(r=>`<p class="quiet"><a href="#work-${r.id}">Receipt #${r.id}</a> · ${escape(r.title)}${r.warnings.length?' — '+escape(r.warnings.join(' ')):''}</p>`).join('')}
        ${d.approved_at?`<p class="notice">${d.approval.rows.length} time entries created. <a href="/entries">View entries →</a></p>`:`<form id="approve-form">${d.rows.map(r=>`<div class="draft-row" data-row="${r.row_id}"><input type="checkbox" name="include" checked aria-label="Include interval for ${escape(r.notes)}"><div><span class="quiet">Receipt #${r.work_id}</span><div class="form-grid"><label>Start<input name="start" type="datetime-local" step="0.001" required value="${localValue(r.start_time)}"></label><label>End<input name="end" type="datetime-local" step="0.001" required value="${localValue(r.end_time)}"></label><label class="form-wide">Entry notes<input name="notes" maxlength="4000" value="${escape(r.notes)}"></label></div></div></div>`).join('')}<p class="quiet">Unchecked intervals are excluded. Reviewing closes all sessions in this draft to further conversion.</p><div class="action-row"><button class="btn btn-primary" ${d.receipts.length?'':'disabled'}>Approve reviewed intervals</button></div></form>`}`;
        section.querySelectorAll('input[type=datetime-local]').forEach(input => input.dataset.initialValue = input.value);
        $('approve-form')?.addEventListener('submit', e => {
            e.preventDefault();
            perform(e.target.querySelector('button'), async () => {
                const rows = [...e.target.querySelectorAll('[data-row]')].filter(r => r.querySelector('[name=include]').checked).map(r => ({
                    row_id: Number(r.dataset.row),
                    start_time: reviewedTime(r, 'start', d),
                    end_time: reviewedTime(r, 'end', d),
                    notes: r.querySelector('[name=notes]').value
                }));
                const result = await mutate('approve_draft', {
                    draft_id: d.id,
                    rows
                });
                renderDraft(result.draft);
                await loadDrafts();
                await loadWork();
                notify('Reviewed time added to Entries.');
            });
        });
    }
    const draftForm = $('draft-form');
    const today = new Date();
    const first = new Date(today);
    first.setDate(first.getDate() - 6);
    draftForm.elements.start.value = localValue(first).slice(0, 10);
    draftForm.elements.end.value = localValue(today).slice(0, 10);
    draftForm.onsubmit = e => {
        e.preventDefault();
        perform(draftForm.querySelector('button'), async () => {
            const start = new Date(draftForm.elements.start.value + 'T00:00:00');
            const end = new Date(draftForm.elements.end.value + 'T00:00:00');
            end.setDate(end.getDate() + 1);
            const r = await mutate('draft_timesheet', {
                start_time: start.toISOString(),
                end_time: end.toISOString()
            });
            renderDraft(r.draft);
            await loadDrafts();
            notify('Draft ready for review.');
        });
    };
    $('draft-list').onclick = e => {
        const b = e.target.closest('[data-draft]');
        if (b) perform(b, async () => renderDraft((await api('get_draft', {
            draft_id: Number(b.dataset.draft)
        })).draft));
    };
    perform(null, async () => {
        await Promise.all([loadWork(), loadTokens(), loadDrafts()]);
        if (location.hash.startsWith('#work-')) {
            const id = Number(location.hash.slice(6));
            if (id && !workItems.some(w => w.id === id)) {
                workItems.push((await api('get_work', {
                    work_id: id
                })).work);
                renderWork();
            }
            document.querySelector(location.hash)?.scrollIntoView();
        }
    });
    // Refresh shared sessions while preserving expanded receipts and button focus.
    let polling = false;

    function structure(items) {
        return JSON.stringify(items.map(w => [w.id, w.finished_at, w.approved_at,
            w.spans.map(s => [s.id, s.ended_at, s.stop_reason]),
            w.events.filter(e => e.kind !== 'heartbeat').map(e => e.id)
        ]));
    }
    setInterval(async () => {
        if (document.hidden || polling) return;
        polling = true;
        try {
            const before = structure(workItems);
            const result = await api('list_work');
            const merged = new Map(workItems.map(w => [w.id, w]));
            result.work.forEach(w => merged.set(w.id, w));
            workItems = [...merged.values()].sort((a, b) => b.id - a.id);
            if (before !== structure(workItems)) {
                const focused = document.activeElement?.closest('button[data-work]');
                const focusWork = focused?.dataset.work,
                    focusAction = focused?.dataset.action;
                renderWork();
                if (focusWork) document.querySelector(`button[data-work="${focusWork}"][data-action="${focusAction}"]`)?.focus();
            } else {
                for (const w of workItems) {
                    const card = $('work-' + w.id);
                    if (!card) continue;
                    const values = card.querySelectorAll('.metric dd');
                    [w.elapsed_seconds, w.human_seconds, w.agent_seconds, w.waiting_seconds].forEach((s, i) => values[i].textContent = duration(s));
                    card.querySelector('.quiet.mono').textContent = `Agent budget ${w.finished_at?'unused':'remaining'} ${duration(w.budget_remaining_seconds)} · ${w.spans.filter(s=>!s.ended_at&&s.actor_kind==='agent').length} agents active`;
                }
            }
        } catch (e) {
            notify('Live updates paused: ' + e.message, true);
        } finally {
            polling = false;
        }
    }, 5000);
})();
