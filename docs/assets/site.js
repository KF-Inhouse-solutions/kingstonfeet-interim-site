/* kingstonfeet interim site: back-to-top button and testimonial slider (no libraries, no tracking) */
(function () {
  var top = document.getElementById('to-top');
  if (top) {
    var onScroll = function () { top.classList.toggle('show', window.scrollY > 800); };
    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
    top.addEventListener('click', function (e) { e.preventDefault(); window.scrollTo({ top: 0, behavior: 'smooth' }); });
  }
  document.querySelectorAll('.click-col').forEach(function (c) {
    var a = c.querySelector('a[href]');
    if (!a) return;
    c.addEventListener('click', function (e) { if (!e.target.closest('a')) window.location.href = a.href; });
  });
  document.querySelectorAll('.testimonials').forEach(function (t) {
    var n = t.children.length, i = 0;
    if (n < 2) return;
    var go = function (k) { i = (k + n) % n; t.scrollTo({ left: t.children[i].offsetLeft - t.offsetLeft, behavior: 'smooth' }); };
    var nav = document.createElement('div');
    nav.className = 'slider-nav';
    nav.innerHTML = '<button type="button" aria-label="Previous review">&#8249;</button><button type="button" aria-label="Next review">&#8250;</button>';
    t.after(nav);
    nav.children[0].addEventListener('click', function () { go(i - 1); });
    nav.children[1].addEventListener('click', function () { go(i + 1); });
    t.addEventListener('scroll', function () { i = Math.round((t.scrollLeft) / t.clientWidth); }, { passive: true });
    setInterval(function () { if (!t.matches(':hover') && !nav.matches(':hover')) go(i + 1); }, 6000);
  });
})();
