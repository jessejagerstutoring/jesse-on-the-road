// Everything on the site that moves or responds to a click, apart from the map itself.
(function () {
  var SITE = window.SITE || {};

  function store(key, value) {
    try {
      if (value === undefined) return localStorage.getItem(key);
      localStorage.setItem(key, value);
    } catch (e) { return null; }
  }

  function clock(tz) {
    try {
      return new Date().toLocaleTimeString('en-GB', { timeZone: tz, hour: '2-digit', minute: '2-digit' });
    } catch (e) { return ''; }
  }

  // Larger text, remembered for the next visit.
  var sizeButton = document.getElementById('text-size');
  if (sizeButton) {
    var applySize = function (large) {
      document.documentElement.toggleAttribute('data-large-text', large);
      sizeButton.setAttribute('aria-pressed', large ? 'true' : 'false');
      sizeButton.textContent = large ? 'Smaller text' : 'Larger text';
    };
    applySize(store('large-text') === '1');
    sizeButton.addEventListener('click', function () {
      var large = !document.documentElement.hasAttribute('data-large-text');
      store('large-text', large ? '1' : '0');
      applySize(large);
    });
  }

  // Light is the default. Dark is a choice, remembered for the next visit.
  var themeButton = document.getElementById('theme');
  if (themeButton) {
    var applyTheme = function (dark) {
      if (dark) document.documentElement.setAttribute('data-theme', 'dark');
      else document.documentElement.removeAttribute('data-theme');
      themeButton.textContent = dark ? 'Light mode' : 'Dark mode';
      var meta = document.querySelector('meta[name="theme-color"]');
      if (meta) meta.setAttribute('content', dark ? '#0d0d0d' : '#ffffff');
    };
    applyTheme(store('theme') === 'dark');
    themeButton.addEventListener('click', function () {
      var dark = document.documentElement.getAttribute('data-theme') !== 'dark';
      store('theme', dark ? 'dark' : 'light');
      applyTheme(dark);
      window.dispatchEvent(new Event('themechange'));
    });
  }

  /* ---------- Home page ---------- */
  var mapCanvas = document.getElementById('typed-map');
  if (mapCanvas && window.TypedMap && !mapCanvas.dataset.mini) home();

  function slug(s) { return s.toLowerCase().replace(/[^a-z0-9]+/g, '-'); }

  function home() {
    var stories = SITE.stories;
    var upcoming = SITE.upcoming || [];
    var hoverLabel = document.getElementById('map-hover');
    var typingLabel = document.getElementById('map-typing');
    var map = new window.TypedMap(mapCanvas, {
      visited: stories.map(function (s) { return s.country; }),
      onHover: function (name, x, y) {
        hoverLabel.hidden = !name;
        if (!name) return;
        hoverLabel.textContent = name;
        hoverLabel.style.transform = 'translate(' + x + 'px,' + y + 'px)';
        hoverLabel.classList.toggle('flip', x > mapCanvas.clientWidth * .72);
      },
      onTyping: function (name) { typingLabel.textContent = 'Now typing: ' + name; }
    });
    var host = document.getElementById('map-pins');
    var world = { lon: 0, lat: 13, w: 360 };

    var places = {};
    stories.forEach(function (s) {
      var key = slug(s.place);
      if (!places[key]) places[key] = { key: key, name: s.place, country: s.country, lat: s.lat, lon: s.lon, tz: s.tz, count: 0 };
      places[key].count++;
    });
    upcoming.forEach(function (u) {
      places[slug(u.place)] = { key: slug(u.place), name: u.place, country: u.country, lat: u.lat, lon: u.lon, tz: u.tz, count: 0, next: true };
    });

    var countries = {};
    Object.keys(places).forEach(function (k) {
      var p = places[k], key = slug(p.country);
      var c = countries[key] || (countries[key] = { key: key, name: p.country, places: [], count: 0 });
      c.places.push(p);
      c.count += p.count;
    });
    Object.keys(countries).forEach(function (k) {
      var c = countries[k];
      var lats = c.places.map(function (p) { return p.lat; });
      var lons = c.places.map(function (p) { return p.lon; });
      var told = c.places.filter(function (p) { return p.count; });
      c.lat = (told[0] || c.places[0]).lat;
      c.lon = (told[0] || c.places[0]).lon;
      c.view = {
        lon: (Math.min.apply(null, lons) + Math.max.apply(null, lons)) / 2,
        lat: (Math.min.apply(null, lats) + Math.max.apply(null, lats)) / 2,
        w: Math.max(34, (Math.max.apply(null, lons) - Math.min.apply(null, lons)) * 5)
      };
    });

    function makePin(label, count, lon, lat, hash, kind) {
      var a = document.createElement(hash ? 'a' : 'span');
      a.className = 'pin ' + kind;
      if (hash) a.href = '#' + hash;
      a.innerHTML = '<span class="pin-dot">' + (count || '') + '</span><span class="pin-label"></span>';
      a.querySelector('.pin-label').textContent = label;
      if (hash) a.setAttribute('aria-label', label + ', ' + count + (count === 1 ? ' story' : ' stories'));
      host.appendChild(a);
      return { el: a, lon: lon, lat: lat };
    }

    var pins = [];
    Object.keys(countries).forEach(function (k) {
      var c = countries[k];
      var pin = makePin(c.name, c.count, c.lon, c.lat, c.key, 'country');
      pin.country = c.key;
      pins.push(pin);
    });
    Object.keys(places).forEach(function (k) {
      var p = places[k];
      var pin = makePin(p.next ? p.name + ', story coming' : p.name, p.count, p.lon, p.lat, p.next ? null : p.key, p.next ? 'place next' : 'place');
      pin.placeOf = slug(p.country);
      pin.place = p.key;
      pins.push(pin);
    });
    map.setPins(pins);

    var chips = document.getElementById('chips');
    function addChip(label, hash) {
      var a = document.createElement('a');
      a.className = 'chip';
      a.href = '#' + hash;
      a.textContent = label;
      a.dataset.hash = hash;
      chips.appendChild(a);
    }
    addChip('All stories', 'all');
    Object.keys(countries).forEach(function (k) { addChip(countries[k].name, k); });
    Object.keys(places).forEach(function (k) { if (!places[k].next) addChip(places[k].name, k); });

    var rows = Array.prototype.slice.call(document.querySelectorAll('.story-row'));
    var status = document.getElementById('list-status');
    var backButton = document.getElementById('map-back');

    function select(hash) {
      var country = countries[hash], place = places[hash] && !places[hash].next ? places[hash] : null;
      var scope = country || (place && countries[slug(place.country)]);
      map.flyTo(scope ? scope.view : world);
      pins.forEach(function (pin) {
        var show = scope ? pin.placeOf === scope.key : !!pin.country;
        pin.el.hidden = !show;
        pin.el.classList.toggle('active', !!place && pin.place === place.key);
      });
      var shown = 0;
      rows.forEach(function (row) {
        var match = country ? row.dataset.country === hash : place ? row.dataset.place === hash : true;
        row.hidden = !match;
        if (match) shown++;
      });
      backButton.hidden = !scope;
      Array.prototype.forEach.call(chips.children, function (chip) {
        var on = chip.dataset.hash === hash || (!scope && chip.dataset.hash === 'all');
        if (on) chip.setAttribute('aria-current', 'true'); else chip.removeAttribute('aria-current');
      });
      var where = place ? place.name : country ? country.name : 'the world';
      status.textContent = shown + (shown === 1 ? ' story' : ' stories') + ' from ' + where;
    }

    function fromHash() {
      var hash = location.hash.replace('#', '');
      select(countries[hash] || places[hash] ? hash : 'all');
    }
    window.addEventListener('hashchange', fromHash);
    fromHash();

    rows.forEach(function (row) {
      var light = function (on) {
        pins.forEach(function (pin) {
          if (pin.country === row.dataset.country || pin.place === row.dataset.place) pin.el.classList.toggle('ping', on);
        });
      };
      row.addEventListener('pointerenter', function () { light(true); });
      row.addEventListener('pointerleave', function () { light(false); });
    });

    var surprise = document.getElementById('surprise');
    if (surprise) surprise.addEventListener('click', function () {
      var pick = stories[Math.floor(Math.random() * stories.length)];
      location.href = pick.url;
    });

    var local = document.getElementById('local-time');
    if (local && stories.length) {
      var latest = stories[stories.length - 1];
      var tick = function () {
        var time = clock(latest.tz);
        local.textContent = time ? 'It is ' + time + ' in ' + latest.place + ' right now.' : '';
      };
      tick();
      setInterval(tick, 30000);
    }
  }

  /* ---------- Story page ---------- */
  var mini = document.querySelector('canvas[data-mini]');
  if (mini && window.TypedMap) {
    new window.TypedMap(mini, {
      mini: true,
      visited: [mini.dataset.country],
      view: { lon: Number(mini.dataset.lon), lat: Number(mini.dataset.lat), w: 44 }
    });
  }

  var bar = document.getElementById('progress');
  var article = document.querySelector('.story-body');
  if (bar && article) {
    var measure = function () {
      var r = article.getBoundingClientRect();
      var total = r.height - window.innerHeight * .5;
      var t = Math.max(0, Math.min(1, (window.innerHeight * .5 - r.top) / total));
      bar.style.transform = 'scaleX(' + t + ')';
    };
    window.addEventListener('scroll', measure, { passive: true });
    window.addEventListener('resize', measure);
    measure();
  }

  var share = document.getElementById('share');
  if (share) {
    share.addEventListener('click', function () {
      var data = { title: document.title, url: location.href };
      var said = function (text) {
        share.textContent = text;
        setTimeout(function () { share.textContent = 'Send this story to someone'; }, 2500);
      };
      if (navigator.share) {
        navigator.share(data).catch(function () {});
      } else if (navigator.clipboard) {
        navigator.clipboard.writeText(location.href).then(function () { said('Link copied'); }, function () { said(location.href); });
      } else {
        said(location.href);
      }
    });
  }

  /* ---------- Looking at photos full screen ---------- */
  var dialog = document.getElementById('viewer');
  var links = Array.prototype.slice.call(document.querySelectorAll('a.photo-link'));
  if (dialog && links.length && dialog.showModal) {
    var big = dialog.querySelector('img');
    var note = dialog.querySelector('.viewer-caption');
    var index = 0;
    var show = function (i) {
      index = (i + links.length) % links.length;
      var link = links[index];
      big.src = link.href;
      big.alt = link.querySelector('img').alt;
      note.textContent = (index + 1) + ' of ' + links.length + '. ' + link.dataset.caption;
    };
    links.forEach(function (link, i) {
      link.addEventListener('click', function (e) {
        e.preventDefault();
        show(i);
        dialog.showModal();
      });
    });
    dialog.querySelector('.viewer-close').addEventListener('click', function () { dialog.close(); });
    dialog.querySelector('.viewer-prev').addEventListener('click', function () { show(index - 1); });
    dialog.querySelector('.viewer-next').addEventListener('click', function () { show(index + 1); });
    dialog.addEventListener('click', function (e) { if (e.target === dialog) dialog.close(); });
    dialog.addEventListener('keydown', function (e) {
      if (e.key === 'ArrowLeft') show(index - 1);
      if (e.key === 'ArrowRight') show(index + 1);
    });
    var startX = null;
    dialog.addEventListener('touchstart', function (e) { startX = e.touches[0].clientX; }, { passive: true });
    dialog.addEventListener('touchend', function (e) {
      if (startX === null) return;
      var dx = e.changedTouches[0].clientX - startX;
      if (Math.abs(dx) > 50) show(index + (dx < 0 ? 1 : -1));
      startX = null;
    });
  }
})();
