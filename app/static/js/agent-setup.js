(() => {
    const button = document.getElementById('copy-agent-setup');
    if (!button) return;
    const status = document.getElementById('setup-copy-status');
    const fallback = document.getElementById('setup-copy-fallback');
    const text = document.getElementById('setup-prompt-text');
    button.addEventListener('click', async () => {
        button.disabled = true;
        try {
            await navigator.clipboard.writeText(button.dataset.prompt);
            status.textContent = 'Copied · paste in your agent';
            fallback.classList.add('hidden');
        } catch {
            text.value = button.dataset.prompt;
            fallback.classList.remove('hidden');
            text.focus();
            text.select();
            status.textContent = 'Select and copy below';
        } finally {
            button.disabled = false;
        }
    });
})();
