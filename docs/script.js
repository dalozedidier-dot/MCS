// Liens de dépôt adaptés automatiquement après publication sur GitHub Pages.
if (location.hostname.endsWith('github.io')) {
  const owner = location.hostname.split('.')[0];
  const repo = location.pathname.split('/').filter(Boolean)[0];
  if (owner && repo) {
    document.querySelectorAll('[data-repo-link]').forEach(link => {
      link.href = `https://github.com/${owner}/${repo}`;
    });
  }
}

function setMetric(key, value) {
  document.querySelectorAll(`[data-metric="${key}"]`).forEach(el => {
    el.textContent = value;
  });
}

function animateCounter(el, target) {
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (reduced) {
    el.textContent = String(target);
    return;
  }
  let current = 0;
  const tick = () => {
    current += Math.max(1, Math.ceil((target - current) / 8));
    el.textContent = String(Math.min(current, target));
    if (current < target) requestAnimationFrame(tick);
  };
  tick();
}

function prepareCounters() {
  const counters = document.querySelectorAll('[data-count]');
  const observer = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (!entry.isIntersecting) return;
      const target = Number(entry.target.dataset.count || 0);
      animateCounter(entry.target, target);
      observer.unobserve(entry.target);
    });
  }, { threshold: 0.45 });
  counters.forEach(el => observer.observe(el));
}

fetch('data/results.json')
  .then(response => {
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
  })
  .then(data => {
    const counter = document.querySelector('[data-metric="n_tests"]');
    if (counter) counter.dataset.count = String(data.n_tests);
    setMetric('falsification', `${data.falsification_pass} / ${data.falsification_total}`);
    setMetric('python_ci', data.python_ci);
    setMetric('version', `v${data.version}`);
    setMetric('tests_label', `${data.n_tests} tests collectés`);

    const gain = data.benchmark?.headline?.gain_median;
    const distribution = data.benchmark?.headline?.distribution_gain;
    if (typeof gain === 'number') {
      const ci = distribution?.median_ci95;
      const ciText = Array.isArray(ci)
        ? ` · IC95 [${Number(ci[0]).toFixed(1)} ; ${Number(ci[1]).toFixed(1)}]`
        : '';
      setMetric('benchmark_gain', `${gain >= 0 ? '+' : ''}${gain.toFixed(1)} pas${ciText}`);
    }

    const when = new Date(data.generated_at).toLocaleDateString('fr-FR');
    setMetric('provenance', `commit ${String(data.commit).slice(0, 8)}, ${when}`);
    prepareCounters();
  })
  .catch(() => {
    // Prévisualisation locale sans serveur : les valeurs restent explicites.
    setMetric('tests_label', 'Données CI indisponibles');
    prepareCounters();
  });
