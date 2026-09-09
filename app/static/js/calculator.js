(() => {
    const root = document.getElementById('parallel-calculator');
    if (!root) return;
    const a = document.getElementById('calc-agents'),
        d = document.getElementById('calc-duration'),
        h = document.getElementById('calc-human');

    function draw() {
        document.getElementById('agents-label').textContent = a.value;
        if (!d.checkValidity() || !h.checkValidity() || !d.value || h.value === '') {
            document.getElementById('calc-result').textContent = 'Enter valid durations from 1–1440 agent minutes and 0–1440 human minutes.';
            return;
        }
        const agents = Number(a.value),
            duration = Number(d.value),
            human = Number(h.value),
            elapsed = Math.max(duration, human);
        document.getElementById('calc-result').textContent = `${elapsed} elapsed min · ${agents*duration} agent-min · ${human} human min`;
        document.getElementById('calc-timeline').innerHTML = [
            ['You', human, false], ...Array.from({
                length: agents
            }, (_, i) => ['Agent ' + (i + 1), duration, true])
        ].map(([name, time, agent]) => `<div class="timeline-row"><span>${name}</span><div class="track"><div class="bar ${agent?'agent':''}" style="width:${time/elapsed*100}%"></div></div></div>`).join('');
    }
    root.addEventListener('input', draw);
    draw();
})();
