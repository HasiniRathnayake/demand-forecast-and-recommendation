/* ── Sunrise Super — Theme Toggle ── */
(function () {
    const KEY = 'ss-theme';

    function setTheme(theme) {
        document.body.setAttribute('data-theme', theme);
        localStorage.setItem(KEY, theme);
    }

    /* Apply saved preference immediately to avoid flash */
    var saved = localStorage.getItem(KEY) || 'dark';
    if (document.body) document.body.setAttribute('data-theme', saved);

    document.addEventListener('DOMContentLoaded', function () {
        /* Re-apply in case body wasn't ready at script-load time */
        document.body.setAttribute('data-theme', saved);

        var btn = document.getElementById('theme-toggle');
        if (!btn) return;

        btn.addEventListener('click', function () {
            var current = document.body.getAttribute('data-theme') || 'dark';
            setTheme(current === 'dark' ? 'light' : 'dark');
        });
    });
})();
