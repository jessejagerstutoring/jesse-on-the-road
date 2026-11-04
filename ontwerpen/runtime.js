// Draait de ontwerpen als gewone webpagina's: vult de {{gaten}} in het sjabloon,
// herhaalt <sc-for>, kiest <sc-if> en werkt de pagina bij na een klik.
(function () {
  var HOLE = /\{\{\s*([^}]+?)\s*\}\}/g;
  var WHOLE = /^\s*\{\{\s*([^}]+?)\s*\}\}\s*$/;

  function lookup(path, scope) {
    if (path === 'true') return true;
    if (path === 'false') return false;
    return path.split('.').reduce(function (v, k) {
      return v === null || v === undefined ? undefined : v[k];
    }, scope);
  }
  function fill(text, scope) {
    return text.replace(HOLE, function (_, p) {
      var v = lookup(p, scope);
      return v === null || v === undefined ? '' : String(v);
    });
  }
  function hole(attr, scope) {
    var m = attr && attr.match(WHOLE);
    return m ? lookup(m[1], scope) : undefined;
  }

  function build(node, scope, out) {
    if (node.nodeType === 3) {
      out.appendChild(document.createTextNode(fill(node.nodeValue, scope)));
      return;
    }
    if (node.nodeType !== 1) return;
    var tag = node.localName;
    if (tag === 'sc-for') {
      var name = node.getAttribute('as');
      (hole(node.getAttribute('list'), scope) || []).forEach(function (item, i) {
        var inner = Object.assign({}, scope, { $index: i });
        inner[name] = item;
        node.childNodes.forEach(function (c) { build(c, inner, out); });
      });
      return;
    }
    if (tag === 'sc-if') {
      if (hole(node.getAttribute('value'), scope)) {
        node.childNodes.forEach(function (c) { build(c, scope, out); });
      }
      return;
    }
    var el = document.createElementNS(node.namespaceURI, tag);
    Array.prototype.forEach.call(node.attributes, function (a) {
      if (a.name.indexOf('hint-') === 0) return;
      if (a.name.indexOf('on') === 0) { el[a.name] = hole(a.value, scope) || null; return; }
      el.setAttribute(a.name, fill(a.value, scope));
    });
    node.childNodes.forEach(function (c) { build(c, scope, el); });
    out.appendChild(el);
  }

  // Past alleen aan wat veranderde, zodat scrollpositie, focus en animaties blijven werken.
  function morph(oldP, newP) {
    var o = Array.prototype.slice.call(oldP.childNodes);
    var n = Array.prototype.slice.call(newP.childNodes);
    n.forEach(function (nc, i) {
      var oc = o[i];
      if (!oc) { oldP.appendChild(nc); return; }
      if (oc.nodeType !== nc.nodeType || oc.nodeName !== nc.nodeName) { oldP.replaceChild(nc, oc); return; }
      if (nc.nodeType === 3) {
        if (oc.nodeValue !== nc.nodeValue) oc.nodeValue = nc.nodeValue;
        return;
      }
      Array.prototype.slice.call(oc.attributes).forEach(function (a) {
        if (!nc.hasAttribute(a.name)) oc.removeAttribute(a.name);
      });
      Array.prototype.forEach.call(nc.attributes, function (a) {
        if (oc.getAttribute(a.name) !== a.value) oc.setAttribute(a.name, a.value);
      });
      oc.onclick = nc.onclick;
      morph(oc, nc);
    });
    o.slice(n.length).forEach(function (c) { oldP.removeChild(c); });
  }

  var root = document.getElementById('dc-root');
  var tpl = document.getElementById('dc-template');

  function DCLogic() { this.props = {}; this.state = {}; }
  DCLogic.prototype.renderVals = function () { return {}; };
  DCLogic.prototype.setState = function (s) {
    this.state = Object.assign({}, this.state, s);
    draw();
  };
  DCLogic.prototype.forceUpdate = function () { draw(); };

  var Component = new Function(
    'DCLogic',
    document.getElementById('dc-logic').textContent + '\nreturn Component;'
  )(DCLogic);
  var instance = new Component();

  function draw() {
    var frag = document.createElement('div');
    var scope = instance.renderVals();
    tpl.content.childNodes.forEach(function (c) { build(c, scope, frag); });
    morph(root, frag);
  }

  draw();
  if (instance.componentDidMount) instance.componentDidMount();
})();
