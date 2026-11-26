(() => {
  const packageByApp = {
    still: 'com.gol.stillcallblocker',
    buzzpa: 'com.gol.buzzpa.pro'
  };
  const app = document.body.dataset.app;
  const normalizedPath = window.location.pathname.replace(/index\.html$/, '').replace(/\/+$/, '/') || '/';
  const isAppLandingPage = app && normalizedPath === `/${app}/`;
  const isInstagramAndroid = /Instagram/i.test(navigator.userAgent || '') && /Android/i.test(navigator.userAgent || '');
  const playTest = new URLSearchParams(window.location.search).get('play_test') === '1';

  if (!isAppLandingPage || (!isInstagramAndroid && !playTest) || !packageByApp[app]) return;

  const fallback = `https://play.google.com/store/apps/details?id=${packageByApp[app]}`;
  const intent = `intent://details?id=${packageByApp[app]}#Intent;scheme=market;package=com.android.vending;S.browser_fallback_url=${encodeURIComponent(fallback)};end`;
  const openPlayStore = () => window.setTimeout(() => window.location.replace(intent), 800);
  if (document.readyState === 'complete') openPlayStore();
  else window.addEventListener('load', openPlayStore, {once: true});
})();

document.querySelectorAll('[data-copy-email]').forEach(button => {
  button.addEventListener('click', async () => {
    const status = button.closest('.support-contact').querySelector('.email-status');
    try {
      await navigator.clipboard.writeText('getonlabs@gmail.com');
      status.textContent = 'Email address copied.';
    } catch {
      status.textContent = 'Please select and copy getonlabs@gmail.com above.';
    }
  });
});

document.querySelectorAll('[data-carousel]').forEach(carousel => {
  const viewport = carousel.querySelector('[data-carousel-viewport]');
  const slides = [...carousel.querySelectorAll('.carousel-slide')];
  const dots = [...carousel.querySelectorAll('[data-carousel-dot]')];
  const current = carousel.querySelector('[data-carousel-current]');
  const caption = carousel.querySelector('[data-carousel-caption]');
  const previous = carousel.querySelector('[data-carousel-prev]');
  const next = carousel.querySelector('[data-carousel-next]');
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  let index = 0;
  let timer;
  let visible = true;
  let interacting = false;
  let scrollFrame;

  const update = nextIndex => {
    index = (nextIndex + slides.length) % slides.length;
    current.textContent = String(index + 1);
    caption.textContent = slides[index].dataset.title;
    dots.forEach((dot, dotIndex) => {
      if (dotIndex === index) dot.setAttribute('aria-current', 'true');
      else dot.removeAttribute('aria-current');
    });
  };

  const schedule = (delay = 5000) => {
    clearTimeout(timer);
    if (reducedMotion.matches || interacting || !visible || document.hidden) return;
    timer = setTimeout(() => {
      goTo(index + 1);
      schedule();
    }, delay);
  };

  const goTo = (nextIndex, userInitiated = false) => {
    update(nextIndex);
    viewport.scrollTo({left: viewport.clientWidth * index, behavior: reducedMotion.matches ? 'auto' : 'smooth'});
    if (userInitiated) schedule(8000);
  };

  previous.addEventListener('click', () => goTo(index - 1, true));
  next.addEventListener('click', () => goTo(index + 1, true));
  dots.forEach((dot, dotIndex) => dot.addEventListener('click', () => goTo(dotIndex, true)));

  viewport.addEventListener('keydown', event => {
    if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return;
    event.preventDefault();
    goTo(index + (event.key === 'ArrowRight' ? 1 : -1), true);
  });

  viewport.addEventListener('scroll', () => {
    cancelAnimationFrame(scrollFrame);
    scrollFrame = requestAnimationFrame(() => {
      const width = viewport.clientWidth || 1;
      update(Math.round(viewport.scrollLeft / width));
    });
  }, {passive: true});

  carousel.addEventListener('mouseenter', () => { interacting = true; clearTimeout(timer); });
  carousel.addEventListener('mouseleave', () => { interacting = false; schedule(2500); });
  carousel.addEventListener('focusin', () => { interacting = true; clearTimeout(timer); });
  carousel.addEventListener('focusout', () => {
    requestAnimationFrame(() => {
      interacting = carousel.contains(document.activeElement);
      if (!interacting) schedule(2500);
    });
  });
  viewport.addEventListener('pointerdown', () => { interacting = true; clearTimeout(timer); });
  viewport.addEventListener('pointerup', () => { interacting = false; schedule(8000); });
  viewport.addEventListener('pointercancel', () => { interacting = false; schedule(8000); });

  if ('IntersectionObserver' in window) {
    new IntersectionObserver(entries => {
      visible = entries[0].isIntersecting;
      schedule();
    }, {threshold: .35}).observe(carousel);
  }

  reducedMotion.addEventListener('change', () => schedule());
  document.addEventListener('visibilitychange', () => schedule());
  window.addEventListener('resize', () => goTo(index));
  update(0);
  schedule();
});
