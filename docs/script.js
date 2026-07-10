const counters = document.querySelectorAll('[data-count]');
const observer = new IntersectionObserver(entries => {
  entries.forEach(entry => {
    if (!entry.isIntersecting) return;
    const el = entry.target;
    const target = Number(el.dataset.count);
    let start = 0;
    const tick = () => {
      start += Math.max(1, Math.ceil((target - start) / 8));
      el.textContent = Math.min(start, target);
      if (start < target) requestAnimationFrame(tick);
    };
    tick(); observer.unobserve(el);
  });
}, {threshold:.6});
counters.forEach(el => observer.observe(el));

// GitHub Pages exposes the repository path in the URL. The links are adapted
// automatically after publication, while remaining harmless in local preview.
if (location.hostname.endsWith('github.io')) {
  const owner = location.hostname.split('.')[0];
  const repo = location.pathname.split('/').filter(Boolean)[0];
  if (owner && repo) document.querySelectorAll('[data-repo-link]').forEach(a => {
    a.href = `https://github.com/${owner}/${repo}`;
  });
}
