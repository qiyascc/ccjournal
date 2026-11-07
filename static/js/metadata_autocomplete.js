/* ROR + Crossref Funder autocomplete — CSP-uyumlu (kendi proxy'lerimiz).
   Kurum alanları:  input[name*="affiliation"]:not([name*="ror"])  → /api/suggest/ror
   Fon alanları:    input[name*="funder_name"]                     → /api/suggest/funder
   Seçim tam eşleşirse komşu ror/funder-id alanı otomatik dolar. */
(function () {
  "use strict";
  var cache = {};
  function debounce(fn, ms) {
    var t; return function () { var a = arguments, c = this;
      clearTimeout(t); t = setTimeout(function () { fn.apply(c, a); }, ms); };
  }
  function ensureList(input, kind) {
    var id = "ccdl-" + kind + "-" + Math.random().toString(36).slice(2, 8);
    var dl = document.createElement("datalist");
    dl.id = id; document.body.appendChild(dl);
    input.setAttribute("list", id);
    return dl;
  }
  function bind(input, kind, endpoint, idField) {
    if (input.dataset.ccAuto) return;
    input.dataset.ccAuto = "1";
    var dl = ensureList(input, kind);
    var map = {};
    var run = debounce(function () {
      var q = input.value.trim();
      if (q.length < 3) return;
      var key = kind + ":" + q.toLowerCase();
      if (cache[key]) { fill(cache[key]); return; }
      fetch(endpoint + "?q=" + encodeURIComponent(q), { credentials: "same-origin" })
        .then(function (r) { return r.ok ? r.json() : { results: [] }; })
        .then(function (d) { cache[key] = d.results || []; fill(cache[key]); })
        .catch(function () {});
    }, 350);
    function fill(items) {
      dl.innerHTML = ""; map = {};
      items.forEach(function (it) {
        var opt = document.createElement("option");
        opt.value = it.name;
        if (it.country) opt.label = it.country;
        dl.appendChild(opt);
        map[it.name] = it;
      });
    }
    input.addEventListener("input", run);
    input.addEventListener("change", function () {
      var hit = map[input.value.trim()];
      if (!hit) return;
      var target = idField(input);
      if (target && (hit.ror || hit.id)) target.value = hit.ror || hit.id;
    });
  }
  function rorTarget(input) {
    var name = input.getAttribute("name") || "";
    var rorName = name.replace("affiliation", "affiliation_ror");
    if (rorName === name) return null;
    var form = input.closest("form") || document;
    var cands = form.querySelectorAll('[name="' + rorName + '"]');
    if (cands.length === 1) return cands[0];
    var row = input.closest("tr, .form-row, fieldset, .grid, div");
    return row ? row.querySelector('[name="' + rorName + '"]') : null;
  }
  function funderTarget(input) {
    var row = input.closest("tr, .form-row, fieldset, div");
    return row ? row.querySelector('[name*="funder_id"]') : null;
  }
  function scan() {
    document.querySelectorAll('input[name*="affiliation"]').forEach(function (el) {
      var n = el.getAttribute("name") || "";
      if (n.indexOf("ror") !== -1) return;
      bind(el, "ror", "/api/suggest/ror", rorTarget);
    });
    document.querySelectorAll('input[name*="funder_name"]').forEach(function (el) {
      bind(el, "funder", "/api/suggest/funder", funderTarget);
    });
  }
  if (document.readyState === "loading")
    document.addEventListener("DOMContentLoaded", scan);
  else scan();
  document.body && document.body.addEventListener("click", debounce(scan, 500));
})();
