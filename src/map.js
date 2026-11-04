// The typed map: every country is drawn with the letters of its own name.
(function () {
  var ASPECT = 2.535;
  var mask = null;

  function loadMask() {
    if (mask) return;
    var L = window.LAND;
    mask = new Uint8Array(L.w * L.h);
    L.rle.split(';').forEach(function (row, r) {
      var c = 0;
      row.split('.').forEach(function (run) {
        var parts = run.split(':');
        var id = parseInt(parts[0], 16), n = parseInt(parts[1], 16);
        if (id) mask.fill(id, r * L.w + c, r * L.w + c + n);
        c += n;
      });
    });
  }

  function countryAt(lon, lat) {
    var L = window.LAND;
    var r = Math.floor((L.top - lat) / L.res);
    if (r < 0 || r >= L.h) return 0;
    var c = Math.floor((((lon + 180) % 360 + 360) % 360) / L.res);
    return mask[r * L.w + c];
  }

  // 1 in daylight, fading to 0 after dark, from the sun's real position right now.
  function sunlight(lon, lat, sun) {
    var rad = Math.PI / 180;
    var cosZenith = Math.sin(lat * rad) * Math.sin(sun.lat * rad) +
      Math.cos(lat * rad) * Math.cos(sun.lat * rad) * Math.cos((lon - sun.lon) * rad);
    return Math.max(0, Math.min(1, (cosZenith + 0.1) / 0.2));
  }

  function sunNow() {
    var now = new Date();
    var start = Date.UTC(now.getUTCFullYear(), 0, 0);
    var day = (now - start) / 86400000;
    var hours = now.getUTCHours() + now.getUTCMinutes() / 60;
    return {
      lat: -23.44 * Math.cos(2 * Math.PI / 365 * (day + 10)),
      lon: (12 - hours) * 15
    };
  }

  function ease(t) { return t < .5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2; }

  function TypedMap(canvas, options) {
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d');
    this.o = options || {};
    this.view = this.o.view || { lon: 0, lat: 13, w: 360 };
    // A row of a country reads as THAILAND·THAILAND· in the language of the page.
    this.names = window.LAND[this.o.lang] || window.LAND.names;
    this.labels = this.names.map(function (name) {
      return name.toUpperCase().replace(/ /g, '·') + '·';
    });
    this.pins = [];
    this.cells = [];
    this.visited = {};
    (this.o.visited || []).forEach(function (name) { this.visited[name] = true; }, this);
    this.pointer = null;
    this.calm = this.o.still || window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    this.visible = true;
    this.typing = null;
    this.base = document.createElement('canvas');
    loadMask();
    var self = this;
    var ready = document.fonts && document.fonts.load
      ? Promise.all([document.fonts.load('700 14px "Courier Prime"'), document.fonts.load('400 14px "Courier Prime"')])
      : Promise.resolve();
    ready.catch(function () {}).then(function () { self.start(); });
    if (window.ResizeObserver) {
      var lastWidth = 0;
      new ResizeObserver(function () {
        var width = canvas.parentNode.clientWidth;
        if (self.started && width !== lastWidth) self.layout(true);
        lastWidth = width;
      }).observe(canvas.parentNode);
    }
    window.addEventListener('themechange', function () { if (self.started) self.layout(true); });
  }

  TypedMap.prototype.start = function () {
    this.started = true;
    this.sun = sunNow();
    this.layout(this.calm);
    var self = this;
    if (!this.o.mini) this.listen();
    if (this.calm) { this.renderPins(true); return; }
    this.intro();
    if (window.IntersectionObserver) {
      new IntersectionObserver(function (entries) {
        self.visible = entries[0].isIntersecting;
      }).observe(this.canvas);
    }
    setInterval(function () { self.sun = sunNow(); if (!self.flying) self.buildCells(); }, 60000);
  };

  TypedMap.prototype.listen = function () {
    var self = this, host = this.canvas.parentNode, clear = null;
    function report(e) {
      var r = self.canvas.getBoundingClientRect();
      self.pointer = { x: e.clientX - r.left, y: e.clientY - r.top };
      var v = self.view;
      var lon = v.lon + (self.pointer.x / self.W - .5) * v.w;
      var lat = v.lat - (self.pointer.y / self.H - .5) * self.latSpan(v);
      self.hoverId = countryAt(lon, lat);
      if (self.o.onHover) {
        self.o.onHover(self.hoverId ? self.names[self.hoverId - 1] : null, self.pointer.x, self.pointer.y);
      }
      if (self.calm || self.introducing) self.drawOverlay();
    }
    function leave() {
      self.pointer = null;
      self.hoverId = 0;
      if (self.o.onHover) self.o.onHover(null);
      if (self.calm) self.drawOverlay();
    }
    host.addEventListener('pointermove', function (e) { if (e.pointerType === 'mouse') report(e); });
    host.addEventListener('pointerleave', function (e) { if (e.pointerType === 'mouse') leave(); });
    // On a phone or tablet, tapping a country shows its name for a moment.
    host.addEventListener('pointerdown', function (e) {
      if (e.pointerType === 'mouse') return;
      report(e);
      clearTimeout(clear);
      clear = setTimeout(leave, 2200);
    });
  };

  TypedMap.prototype.latSpan = function (view) {
    return this.o.mini ? view.w * .72 : view.w / ASPECT;
  };

  TypedMap.prototype.layout = function (paint) {
    var width = this.canvas.parentNode.clientWidth;
    if (!width) return;
    var phone = width < 560 && !this.o.mini;
    this.W = width;
    this.H = this.o.mini ? width * .72 : Math.round(width / ASPECT * (phone ? 1.55 : 1));
    this.cellW = this.o.mini ? 7.2 : phone ? 5 : width < 900 ? 6.6 : 8.2;
    this.font = this.cellW / .6;
    this.cols = Math.floor(this.W / this.cellW);
    this.rows = Math.floor(this.H / this.font);
    var dpr = Math.min(window.devicePixelRatio || 1, 2);
    [this.canvas, this.base].forEach(function (c) {
      c.width = Math.round(width * dpr);
      c.height = Math.round(this.H * dpr);
    }, this);
    this.canvas.style.height = this.H + 'px';
    var styles = getComputedStyle(this.canvas);
    this.ink = styles.getPropertyValue('--ink').trim() || '#000';
    this.paper = styles.getPropertyValue('--paper').trim() || '#fff';
    this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    this.base.getContext('2d').setTransform(dpr, 0, 0, dpr, 0, 0);
    this.buildCells();
    if (paint) { this.compose(); this.renderPins(); }
  };

  TypedMap.prototype.fontOf = function (bold) {
    return (bold ? '700 ' : '400 ') + this.font + 'px "Courier Prime","Courier New",monospace';
  };

  TypedMap.prototype.buildCells = function () {
    var v = this.view, cells = [], span = this.latSpan(v), L = window.LAND;
    var groups = {};
    for (var r = 0; r < this.rows; r++) {
      var lat = v.lat + span / 2 - (r + .5) / this.rows * span;
      var previous = 0, run = 0;
      for (var c = 0; c < this.cols; c++) {
        var lon = v.lon - v.w / 2 + (c + .5) / this.cols * v.w;
        var id = countryAt(lon, lat);
        if (id !== previous) { run = 0; previous = id; }
        if (!id) continue;
        var text = this.labels[id - 1];
        var strong = !!this.visited[L.names[id - 1]];
        var cell = {
          x: c * this.cellW, y: (r + 1) * this.font - this.font * .2,
          ch: text[run % text.length], id: id, strong: strong,
          a: strong ? 1 : .34 + .5 * sunlight(lon, lat, this.sun)
        };
        cells.push(cell);
        (groups[id] || (groups[id] = [])).push(cell);
        run++;
      }
    }
    this.cells = cells;
    this.groups = groups;
    var ctx = this.base.getContext('2d');
    ctx.clearRect(0, 0, this.W, this.H);
    ctx.fillStyle = this.ink;
    [false, true].forEach(function (bold) {
      ctx.font = this.fontOf(bold);
      for (var i = 0; i < cells.length; i++) {
        if (cells[i].strong !== bold) continue;
        ctx.globalAlpha = Math.round(cells[i].a * 8) / 8;
        ctx.fillText(cells[i].ch, cells[i].x, cells[i].y);
      }
    }, this);
    ctx.globalAlpha = 1;
  };

  TypedMap.prototype.compose = function () {
    var ctx = this.ctx;
    ctx.clearRect(0, 0, this.W, this.H);
    ctx.drawImage(this.base, 0, 0, this.W, this.H);
  };

  // The map types itself onto the page, line by line, like a carriage moving across paper.
  TypedMap.prototype.intro = function () {
    var self = this, ctx = this.ctx, done = 0, begin = null;
    var length = this.o.mini ? 500 : 1500;
    this.introducing = true;
    ctx.clearRect(0, 0, this.W, this.H);
    ctx.fillStyle = this.ink;
    function frame(time) {
      if (begin === null) begin = time;
      var t = Math.min(1, (time - begin) / length);
      var upto = Math.floor(t * self.cells.length);
      for (; done < upto; done++) {
        var c = self.cells[done];
        ctx.font = self.fontOf(c.strong);
        ctx.globalAlpha = c.a;
        ctx.fillText(c.ch, c.x, c.y);
      }
      ctx.globalAlpha = 1;
      if (t < 1) { requestAnimationFrame(frame); return; }
      self.introducing = false;
      self.compose();
      self.renderPins(true);
      if (!self.o.mini) self.loop();
    }
    requestAnimationFrame(frame);
  };

  // After the intro, one country at a time is quietly retyped, so you can see what the letters say.
  TypedMap.prototype.nextCountry = function () {
    var ids = Object.keys(this.groups || {}).filter(function (id) {
      return this.groups[id].length >= 8;
    }, this);
    if (!ids.length) { this.typing = null; return; }
    var id = ids[Math.floor(Math.random() * ids.length)];
    var count = this.groups[id].length;
    this.typing = { id: Number(id), head: 0, step: Math.max(1, Math.ceil(count / 48)), hold: 0 };
    if (this.o.onTyping) this.o.onTyping(this.names[id - 1]);
  };

  TypedMap.prototype.loop = function () {
    var self = this, last = 0;
    function frame(time) {
      requestAnimationFrame(frame);
      if (!self.visible || document.hidden || self.flying) return;
      if (time - last < 70) return;
      last = time;
      self.advance();
      self.drawOverlay();
    }
    requestAnimationFrame(frame);
  };

  TypedMap.prototype.advance = function () {
    var t = this.typing;
    if (!t || !this.groups[t.id]) { this.nextCountry(); return; }
    if (t.head < this.groups[t.id].length) { t.head += t.step; return; }
    t.hold++;
    if (t.hold > 22) this.nextCountry();
  };

  TypedMap.prototype.stamp = function (cell, inverted) {
    var ctx = this.ctx;
    ctx.fillStyle = inverted ? this.ink : this.paper;
    ctx.fillRect(cell.x, cell.y - this.font * .8, this.cellW, this.font);
    ctx.fillStyle = inverted ? this.paper : this.ink;
    ctx.fillText(cell.ch, cell.x, cell.y);
  };

  TypedMap.prototype.drawOverlay = function () {
    this.compose();
    var ctx = this.ctx;
    ctx.font = this.fontOf(true);
    ctx.globalAlpha = 1;
    var t = this.typing, list = t && this.groups[t.id];
    if (list) {
      var upto = Math.min(t.head, list.length);
      for (var i = 0; i < upto; i++) this.stamp(list[i], false);
      if (upto < list.length) this.stamp(list[upto], true);
    }
    var hovered = this.hoverId && this.groups[this.hoverId];
    if (hovered) {
      for (var j = 0; j < hovered.length; j++) this.stamp(hovered[j], false);
    }
  };

  TypedMap.prototype.project = function (lon, lat) {
    var v = this.view;
    return {
      x: (lon - v.lon) / v.w * this.W + this.W / 2,
      y: (v.lat - lat) / this.latSpan(v) * this.H + this.H / 2
    };
  };

  TypedMap.prototype.setPins = function (pins) {
    this.pins = pins;
    if (this.started && !this.introducing) this.renderPins(true);
  };

  TypedMap.prototype.renderPins = function (arrive) {
    var self = this;
    this.pins.forEach(function (pin) {
      var p = self.project(pin.lon, pin.lat);
      pin.el.style.transform = 'translate(' + p.x + 'px,' + p.y + 'px)';
      pin.el.classList.toggle('flip', p.x > self.W * .68);
      if (arrive) pin.el.classList.add('in');
    });
  };

  // Fly to a new part of the world. The letters retype themselves as the land moves past.
  TypedMap.prototype.flyTo = function (target) {
    var self = this, from = { lon: this.view.lon, lat: this.view.lat, w: this.view.w };
    this.typing = null;
    if (this.calm || !this.started) {
      this.view = target;
      if (this.started) { this.buildCells(); this.compose(); this.renderPins(); }
      return;
    }
    this.flying = true;
    var begin = null, length = 1100;
    function frame(time) {
      if (begin === null) begin = time;
      var t = Math.min(1, (time - begin) / length), e = ease(t);
      self.view = {
        lon: from.lon + (target.lon - from.lon) * e,
        lat: from.lat + (target.lat - from.lat) * e,
        w: from.w * Math.pow(target.w / from.w, e)
      };
      self.buildCells();
      self.compose();
      self.renderPins();
      if (t < 1) { requestAnimationFrame(frame); return; }
      self.flying = false;
    }
    requestAnimationFrame(frame);
  };

  window.TypedMap = TypedMap;
})();
