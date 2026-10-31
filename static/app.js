// Gold Pulse — small helpers. The pages work without this file; it adds the
// phone menu, weight chips, chart switches, city search,
// the price calculator (with "copy estimate") and the two tools.
(function () {
  "use strict";
  var root = document.documentElement;
  root.classList.add("js");

  var $ = function (id) { return document.getElementById(id); };
  var money = function (n, dec) {
    return "₹" + n.toLocaleString("en-IN", { minimumFractionDigits: dec || 0, maximumFractionDigits: dec || 0 });
  };
  var num = function (el) {
    var v = parseFloat(el.value);
    return isFinite(v) && v > 0 ? v : 0;
  };
  var live = function (form, update) {
    form.addEventListener("input", update);
    form.addEventListener("change", update);
    form.addEventListener("submit", function (e) { e.preventDefault(); });
    update();
  };

  // Phone menu.
  var menuBtn = $("menu-btn"), nav = $("main-nav");
  if (menuBtn && nav) {
    menuBtn.addEventListener("click", function () {
      var open = nav.classList.toggle("open");
      menuBtn.setAttribute("aria-expanded", open ? "true" : "false");
    });
  }

  // Weight chips: show every price on the page for 1 g, 8 g, 10 g, 1 tola, 100 g or 1 kg.
  document.querySelectorAll(".units").forEach(function (group) {
    group.querySelectorAll("button[data-mult]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        group.querySelectorAll("button").forEach(function (b) {
          b.setAttribute("aria-pressed", b === btn ? "true" : "false");
        });
        var mult = parseFloat(btn.dataset.mult);
        document.querySelectorAll("[data-g]").forEach(function (el) {
          var dec = mult === 1 ? parseInt(el.dataset.dec, 10) || 0 : 0;
          el.textContent = money(parseFloat(el.dataset.g) * mult, dec);
        });
        document.querySelectorAll("[data-per]").forEach(function (el) {
          el.textContent = "/ " + btn.dataset.label;
        });
        document.querySelectorAll("[data-unit]").forEach(function (el) {
          el.textContent = btn.dataset.label;
        });
      });
    });
  });

  // Chart: switch between 22K / 24K and 7 / 30 / 90 days.
  document.querySelectorAll(".trend").forEach(function (trend) {
    var pick = function (attr) {
      var on = trend.querySelector("button[data-" + attr + '][aria-pressed="true"]');
      return on ? on.getAttribute("data-" + attr) : null;
    };
    var show = function () {
      var key = pick("key"), days = pick("days");
      trend.querySelectorAll(".panel").forEach(function (p) {
        p.hidden = !((!key || p.dataset.key === key) && p.dataset.days === days);
      });
    };
    trend.querySelectorAll(".seg button").forEach(function (btn) {
      btn.addEventListener("click", function () {
        btn.parentElement.querySelectorAll("button").forEach(function (b) {
          b.setAttribute("aria-pressed", b === btn ? "true" : "false");
        });
        show();
      });
    });
  });

  // City cards: filter by city, state or market as you type.
  var search = $("city-search");
  if (search) {
    var items = document.querySelectorAll("#city-list [data-name]");
    var none = $("no-city");
    search.addEventListener("input", function () {
      var q = search.value.trim().toLowerCase(), shown = 0;
      items.forEach(function (el) {
        var hit = !q || el.dataset.name.indexOf(q) !== -1;
        el.hidden = !hit;
        if (hit) shown++;
      });
      none.hidden = shown !== 0;
    });
  }

  // Price calculator: metal value + making charge + GST, shown as a bill.
  var calc = $("calc-form");
  if (calc) {
    var gstRate = parseFloat(calc.dataset.gst) || 0;
    var last = null;
    live(calc, function () {
      var picked = calc.querySelector('input[name="c-rate"]:checked');
      var unit = $("c-unit");
      var amount = num($("c-weight"));
      var grams = amount * parseFloat(unit.value);
      var makingPct = parseFloat($("c-making").value) || 0;
      var metal = grams * parseFloat(picked.value);
      var making = metal * makingPct / 100;
      var gst = $("c-gst").checked ? (metal + making) * gstRate / 100 : 0;
      var weightText = amount + " " + unit.options[unit.selectedIndex].text +
        (unit.value !== "1" ? " (" + grams.toLocaleString("en-IN", { maximumFractionDigits: 3 }) + " g)" : "");
      $("c-making-val").textContent = makingPct + "%";
      $("o-type").textContent = picked.dataset.name;
      $("o-weight").textContent = weightText;
      $("o-gold").textContent = money(metal);
      $("o-making").textContent = money(making) + " (" + makingPct + "%)";
      $("o-gst").textContent = money(gst);
      $("o-total").textContent = money(metal + making + gst);
      last = [
        calc.dataset.site + " price estimate",
        picked.dataset.name + ", " + weightText,
        "Metal value: " + money(metal),
        "Making charge (" + makingPct + "%): " + money(making),
        "GST: " + money(gst),
        "Total: " + money(metal + making + gst),
        "Rates for " + calc.dataset.place + " on " + calc.dataset.date + ". A guide only."
      ].join("\n");
    });
    var copyBtn = $("c-copy");
    if (copyBtn) {
      copyBtn.addEventListener("click", function () {
        var done = function (msg) {
          copyBtn.textContent = msg;
          setTimeout(function () { copyBtn.textContent = "Copy this estimate"; }, 1800);
        };
        // Older way, for browsers that block the clipboard API.
        var fallback = function () {
          var ta = document.createElement("textarea");
          ta.value = last;
          ta.setAttribute("readonly", "");
          ta.className = "sr";
          document.body.appendChild(ta);
          ta.select();
          var ok = false;
          try { ok = document.execCommand("copy"); } catch (e) { ok = false; }
          ta.remove();
          done(ok ? "Copied ✓" : "Couldn't copy");
        };
        if (!last) return;
        if (navigator.clipboard) {
          navigator.clipboard.writeText(last).then(function () { done("Copied ✓"); }, fallback);
        } else {
          fallback();
        }
      });
    }
  }

  // Weight converter: any unit -> all units + value at today's rate.
  var wc = $("wc-form");
  if (wc) {
    var outs = wc.querySelectorAll("dd[data-factor]");
    live(wc, function () {
      var grams = num($("wc-amount")) * parseFloat($("wc-unit").value);
      outs.forEach(function (dd) {
        var v = grams / parseFloat(dd.dataset.factor);
        dd.textContent = v.toLocaleString("en-IN", { maximumFractionDigits: 4 });
      });
      $("wc-v22").textContent = money(grams * parseFloat(wc.dataset.k22));
      $("wc-v24").textContent = money(grams * parseFloat(wc.dataset.k24));
    });
  }

  // Purity calculator: weight x carat / 24.
  var pc = $("pc-form");
  if (pc) {
    var fineness = { 24: 999, 23: 958, 22: 916, 20: 833, 18: 750, 14: 585 };
    live(pc, function () {
      var w = num($("pc-weight")), carat = parseInt($("pc-carat").value, 10);
      var pure = w * fineness[carat] / 1000;
      var fmt = function (g) { return g.toLocaleString("en-IN", { maximumFractionDigits: 3 }) + " g"; };
      $("pc-pure").textContent = fmt(pure);
      $("pc-other").textContent = fmt(Math.max(w - pure, 0));
      $("pc-value").textContent = money(w * carat / 24 * parseFloat(pc.dataset.k24));
    });
  }
})();
