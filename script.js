const DESIGN_WIDTH = 1728;
const DESIGN_HEIGHT = 11981;
const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

// Remove any ripple canvas left behind by an older cached preview build.
document.querySelectorAll('.water-canvas').forEach((canvas) => canvas.remove());

document.querySelectorAll('[data-text]').forEach((element) => {
  const x = Number(element.dataset.x);
  const y = Number(element.dataset.y);
  element.style.left = `${(x / DESIGN_WIDTH) * 100}%`;
  element.style.top = `${(y / DESIGN_HEIGHT) * 100}%`;
});

document.querySelectorAll('[data-box]').forEach((element) => {
  const x = Number(element.dataset.x);
  const y = Number(element.dataset.y);
  const width = Number(element.dataset.w);
  const height = Number(element.dataset.h);
  element.style.left = `${(x / DESIGN_WIDTH) * 100}%`;
  element.style.top = `${(y / DESIGN_HEIGHT) * 100}%`;
  element.style.width = `${(width / DESIGN_WIDTH) * 100}%`;
  element.style.height = `${(height / DESIGN_HEIGHT) * 100}%`;
});

// Duplicate each artwork sequence once so both directions wrap without a seam.
document.querySelectorAll('.gallery-segment').forEach((segment) => {
  const track = segment.parentElement;
  if (track.querySelector('.gallery-segment[aria-hidden="true"]')) return;

  const duplicate = segment.cloneNode(true);
  duplicate.setAttribute('aria-hidden', 'true');
  duplicate.querySelectorAll('img').forEach((image) => image.setAttribute('alt', ''));
  track.appendChild(duplicate);
});

const figmaPage = document.querySelector('.figma-page');
const heroGizmo = document.querySelector('[data-hero-bottom="gizmo"]');
const heroMixie = document.querySelector('[data-hero-bottom="mixie"]');
const heroMixieHotspot = document.querySelector('[data-hero-bottom="mixie-hotspot"]');
const heroCookie = document.querySelector('[data-hero-cookie]');

const setDesignTop = (element, designY) => {
  if (element) element.style.top = `${(designY / DESIGN_HEIGHT) * 100}%`;
};

const placeHeroLandingControls = () => {
  if (!figmaPage || !heroGizmo || !heroMixie || !heroCookie) return;

  const pageWidth = figmaPage.getBoundingClientRect().width;
  const scale = pageWidth / DESIGN_WIDTH;
  const useViewportAnchor = window.innerWidth >= 768 && window.innerWidth / window.innerHeight > 1.1;
  const viewportHeightInDesign = useViewportAnchor ? window.innerHeight / scale : 959.31;
  const controlBottom = viewportHeightInDesign - 34;
  const gizmoY = controlBottom - 67.31;
  const mixieY = controlBottom - 48;
  const cookieY = gizmoY - 14 - 38;

  setDesignTop(heroCookie, cookieY);
  setDesignTop(heroGizmo, gizmoY);
  setDesignTop(heroMixie, mixieY);
  setDesignTop(heroMixieHotspot, mixieY);
};

placeHeroLandingControls();
window.addEventListener('resize', placeHeroLandingControls, { passive: true });

const heroParallax = document.querySelector('[data-hero-parallax]');
const heroParallaxArea = heroParallax?.closest('.hero-parallax');

if (heroParallax && heroParallaxArea && !reducedMotion && window.matchMedia('(pointer: fine)').matches) {
  heroParallaxArea.addEventListener('pointermove', (event) => {
    heroParallaxArea.classList.add('is-active');
    const bounds = heroParallaxArea.getBoundingClientRect();
    const normalizedX = (event.clientX - bounds.left) / bounds.width - 0.5;
    const normalizedY = (event.clientY - bounds.top) / bounds.height - 0.5;
    heroParallax.style.setProperty('--hero-x', `${normalizedX * 7}px`);
    heroParallax.style.setProperty('--hero-y', `${normalizedY * 5}px`);
    heroParallax.style.setProperty('--hero-r', `${normalizedX * 0.18}deg`);
  });

  heroParallaxArea.addEventListener('pointerleave', () => {
    heroParallaxArea.classList.remove('is-active');
    heroParallax.style.setProperty('--hero-x', '0px');
    heroParallax.style.setProperty('--hero-y', '0px');
    heroParallax.style.setProperty('--hero-r', '0deg');
  });
}

const scrollTabsPanel = document.querySelector('[data-tabs-panel]');
const scrollTabs = [...document.querySelectorAll('[data-tab-index]')];
const swipe = document.querySelector('[data-swipe]');
const swipeBack = document.querySelector('[data-swipe-back]');
const swipeStrip = document.querySelector('[data-swipe-strip]');
const swipePanels = [...document.querySelectorAll('.section-swipe__panel')];

if (figmaPage && scrollTabsPanel && scrollTabs.length && swipe && swipeBack && swipeStrip) {
  const TAB_COUNT = scrollTabs.length;
  // Design-space y where the modes section ends and the pale section begins.
  const SWIPE_SEAM = 6554;
  const clamp01 = (value) => Math.min(1, Math.max(0, value));
  const setVar = (element, name, value) => {
    if (element.style.getPropertyValue(name) === value) return;
    element.style.setProperty(name, value);
  };

  let activeTabIndex = -1;
  const setActiveTab = (nextIndex) => {
    if (nextIndex === activeTabIndex) return;
    activeTabIndex = nextIndex;
    scrollTabsPanel.dataset.activeIndex = String(nextIndex);
    scrollTabs.forEach((tab, index) => {
      const isActive = index === nextIndex;
      tab.classList.toggle('is-active', isActive);
      tab.setAttribute('aria-pressed', String(isActive));
    });
  };

  // The page is frozen across this range, so scroll position maps straight onto
  // the highlighted tab — and reverses on the way back up. Kept short so a
  // single flick moves the highlight on rather than leaving the page stuck.
  const tabsPin = {
    centre: 4375,
    length: () => Math.round(Math.min(320, Math.max(200, window.innerHeight * 0.3))) * TAB_COUNT,
    start: 0,
    distance: 0,
  };

  // The run has two halves. Across `pinned` the page is held still and the
  // strip travels its three panels off to the left. Across the `settle` half
  // the page is free again and really does scroll the one viewport from the
  // modes section to the pale one — invisibly, because the cover is opaque
  // throughout. It lifts only once the pale face has reached full opacity and
  // full size, at which point it is the page's own pixels, so there is no seam.
  const modesRun = { start: 0, pinned: 0, settle: 0 };
  const FADE_FROM = 0.72; // of the pinned half — the pale face starts arriving
  const FADE_TO = 0.92; //  of the settle half — and has fully landed by here

  const runScroll = () => {
    const scrolled = window.scrollY;

    setActiveTab(
      tabsPin.distance > 0
        ? Math.min(TAB_COUNT - 1, Math.floor(clamp01((scrolled - tabsPin.start) / tabsPin.distance) * TAB_COUNT))
        : 0,
    );

    const travelled = scrolled - modesRun.start;
    const total = modesRun.pinned + modesRun.settle;
    const active = total > 0 && travelled >= 0 && travelled <= total;
    swipe.classList.toggle('is-active', active);
    if (!active) return;

    // Three panels wide, so a full -100% of its own width clears all three.
    setVar(swipeStrip, '--strip-x', `${(clamp01(travelled / modesRun.pinned) * -100).toFixed(3)}%`);

    const fadeStart = modesRun.pinned * FADE_FROM;
    const fadeEnd = modesRun.pinned + modesRun.settle * FADE_TO;
    const arrived = clamp01((travelled - fadeStart) / (fadeEnd - fadeStart));
    setVar(swipeBack, '--back-fade', arrived.toFixed(3));
    setVar(swipeBack, '--back-scale', (0.92 + 0.08 * arrived).toFixed(4));
  };

  const measure = () => {
    const pageWidth = figmaPage.offsetWidth;
    const pageHeight = figmaPage.offsetHeight;
    const viewportHeight = window.innerHeight;
    const armed = window.innerWidth >= 768 && pageHeight > 0;

    tabsPin.distance = armed ? tabsPin.length() : 0;
    tabsPin.start = Math.round((pageHeight * tabsPin.centre) / DESIGN_HEIGHT - viewportHeight / 2);
    setVar(document.body, '--pin-tabs-top', `${-tabsPin.start}px`);
    setVar(document.body, '--pin-tabs-distance', `${tabsPin.distance}px`);

    // Row of the page where the modes section ends. The run begins one viewport
    // above it — the modes section exactly filling the screen — and ends with
    // that row at the top of the screen. The tab pin has already pushed the
    // page down by its own length by this point in the document.
    const seamRow = Math.round((pageHeight * SWIPE_SEAM) / DESIGN_HEIGHT);
    modesRun.start = seamRow + tabsPin.distance - viewportHeight;
    // Roughly four fifths of a screen of scroll per showcased panel.
    modesRun.pinned = armed ? Math.round(viewportHeight * 2.4) : 0;
    modesRun.settle = armed ? viewportHeight : 0;

    setVar(document.body, '--pin-modes-top', `${-modesRun.start}px`);
    setVar(document.body, '--pin-modes-distance', `${modesRun.pinned}px`);
    document.body.classList.toggle('is-pin-armed', armed);

    swipe.style.left = `${Math.round(figmaPage.getBoundingClientRect().left)}px`;
    swipe.style.width = `${pageWidth}px`;
    swipe.style.height = `${viewportHeight}px`;
    for (const layer of [swipeBack, ...swipePanels]) {
      layer.style.backgroundSize = `${pageWidth}px ${pageHeight}px`;
    }
    // Panels are the modes section; the back face is the screen after it.
    for (const panel of swipePanels) panel.style.backgroundPosition = `0px ${-(seamRow - viewportHeight)}px`;
    swipeBack.style.backgroundPosition = `0px ${-seamRow}px`;

    runScroll();
  };

  let frameQueued = false;
  const queueRun = () => {
    if (frameQueued) return;
    frameQueued = true;
    requestAnimationFrame(() => {
      frameQueued = false;
      runScroll();
    });
  };

  window.addEventListener('scroll', queueRun, { passive: true });
  window.addEventListener('resize', measure, { passive: true });
  window.addEventListener('load', measure);
  new ResizeObserver(measure).observe(figmaPage);

  scrollTabs.forEach((tab) => {
    tab.addEventListener('click', () => {
      if (!tabsPin.distance) return;
      const index = Number(tab.dataset.tabIndex);
      window.scrollTo({
        top: tabsPin.start + ((index + 0.5) / TAB_COUNT) * tabsPin.distance,
        behavior: reducedMotion ? 'auto' : 'smooth',
      });
    });
  });

  measure();
}

document.querySelector('.signup-hotspot')?.addEventListener('submit', (event) => {
  event.preventDefault();
  const input = event.currentTarget.querySelector('input');
  input.value = '';
  input.blur();
});
