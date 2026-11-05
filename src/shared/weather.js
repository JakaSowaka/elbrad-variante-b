  /* ================= Wetter: Open-Meteo =================
     Der Abruf passiert in loadWeather(). Er läuft bei jedem Seitenaufruf
     und bei "Erneut versuchen". Es gibt keine Beispiel- oder Ersatzwerte. */
  var WEATHER_URL = "https://api.open-meteo.com/v1/forecast?latitude=53.55&longitude=9.99&current=temperature_2m,wind_speed_10m&hourly=precipitation_probability&forecast_days=1&timezone=Europe%2FBerlin";
  var TIMEOUT_MS = 10000;
  var NA = "Nicht verfügbar";

  var el = {
    status: document.getElementById("weather-status"),
    error: document.getElementById("weather-error"),
    retry: document.getElementById("weather-retry"),
    stats: document.getElementById("weather-stats"),
    heading: document.getElementById("weather-title"),
    temp: document.getElementById("w-temp"),
    precip: document.getElementById("w-precip"),
    precipHour: document.getElementById("w-precip-hour"),
    wind: document.getElementById("w-wind"),
    time: document.getElementById("w-time")
  };

  var fmtOneDecimal = new Intl.NumberFormat("de-DE", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  var fmtInteger = new Intl.NumberFormat("de-DE", { maximumFractionDigits: 0 });
  var NBSP = "\u00A0";

  function isNumber(v) { return typeof v === "number" && Number.isFinite(v); }

  // Rundet und verhindert "-0,0" bei Werten knapp unter null.
  function formatOneDecimal(v) {
    var r = Math.round(v * 10) / 10;
    if (r === 0) r = 0;
    return fmtOneDecimal.format(r);
  }

  // "2026-11-05T15:45" -> {date:"05.11.2026", hm:"15:45", hourKey:"2026-11-05T15"}
  // Open-Meteo liefert die Zeit mit timezone=Europe/Berlin bereits in Berliner Ortszeit.
  function parseLocalTime(s) {
    if (typeof s !== "string") return null;
    var m = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::\d{2})?$/.exec(s);
    if (!m) return null;
    return { date: m[3] + "." + m[2] + "." + m[1], hm: m[4] + ":" + m[5], hour: m[4], hourKey: m[1] + "-" + m[2] + "-" + m[3] + "T" + m[4] };
  }

  function unitOk(units, key, expected) {
    // Fehlt die Einheitenangabe, gilt die Standardeinheit der API (°C, km/h, %).
    if (!units || typeof units !== "object" || !(key in units)) return true;
    return units[key] === expected;
  }

  function setValue(node, text) {
    node.textContent = text;
    node.classList.toggle("is-na", text === NA);
  }

  function setState(state) {
    var loading = state === "loading", error = state === "error", ok = state === "ok";
    el.stats.hidden = !ok;
    el.error.hidden = !error;
    el.status.classList.toggle("sr-only", ok);
    el.status.classList.toggle("is-error", error);
    el.status.parentNode.setAttribute("aria-busy", loading ? "true" : "false");
    if (loading) el.status.textContent = "Wetterdaten werden geladen …";
    if (error) el.status.textContent = "Wetterdaten gerade nicht erreichbar.";
    if (!ok) el.time.textContent = loading ? "–" : NA;
  }

  function render(data) {
    var current = data && typeof data === "object" ? data.current : null;
    var units = data && data.current_units;
    var hourly = data && data.hourly;
    var hourlyUnits = data && data.hourly_units;
    var used = {};

    // Temperatur
    var t = current && current.temperature_2m;
    var tempText = isNumber(t) && unitOk(units, "temperature_2m", "°C") ? formatOneDecimal(t) + NBSP + "°C" : NA;
    setValue(el.temp, tempText);
    used.temperature_2m = tempText === NA ? null : t;

    // Wind
    var w = current && current.wind_speed_10m;
    var windText = isNumber(w) && w >= 0 && unitOk(units, "wind_speed_10m", "km/h") ? formatOneDecimal(w) + NBSP + "km/h" : NA;
    setValue(el.wind, windText);
    used.wind_speed_10m = windText === NA ? null : w;

    // Stand
    var ct = parseLocalTime(current && current.time);
    var tzOk = !data || data.timezone === undefined || data.timezone === "Europe/Berlin";
    el.time.textContent = ct && tzOk ? ct.date + ", " + ct.hm + NBSP + "Uhr" : NA;
    used.time = ct && tzOk ? current.time : null;

    // Niederschlag: Eintrag in hourly.time mit gleichem Datum und gleicher Stunde wie current.time
    var precipText = NA, hourText = "";
    var times = hourly && hourly.time, probs = hourly && hourly.precipitation_probability;
    if (ct && Array.isArray(times) && Array.isArray(probs) && times.length === probs.length && unitOk(hourlyUnits, "precipitation_probability", "%")) {
      var idx = -1;
      for (var i = 0; i < times.length; i++) {
        var ht = parseLocalTime(times[i]);
        if (ht && ht.hourKey === ct.hourKey) { idx = i; break; }
      }
      if (idx !== -1) {
        var p = probs[idx];
        hourText = "Stundenwert " + ct.hour + ":00" + NBSP + "Uhr";
        if (isNumber(p) && p >= 0 && p <= 100) {
          precipText = fmtInteger.format(p) + NBSP + "%";
          used.precipitation_probability = { index: idx, time: times[idx], value: p };
        }
      }
    }
    setValue(el.precip, precipText);
    el.precipHour.textContent = hourText;
    if (!used.precipitation_probability) used.precipitation_probability = null;

    setState("ok");
    el.status.textContent = "Wetterdaten geladen. Temperatur " + tempText + ", Niederschlagswahrscheinlichkeit " + precipText +
      (hourText ? " (" + hourText + ")" : "") + ", Wind " + windText + ". Stand " + el.time.textContent + ".";

    // Für das Protokoll: welche Werte aus der Antwort angezeigt werden.
    if (window.console && console.info) console.info("[ELBRAD] Open-Meteo-Werte angezeigt:", used);
  }

  var requestId = 0;
  function loadWeather() {
    var id = ++requestId;
    setState("loading");
    var controller = typeof AbortController === "function" ? new AbortController() : null;
    var timer = setTimeout(function () { if (controller) controller.abort(); }, TIMEOUT_MS);

    fetch(WEATHER_URL, { cache: "no-store", signal: controller ? controller.signal : undefined })
      .then(function (res) {
        if (!res.ok) throw new Error("HTTP " + res.status);
        return res.json().catch(function () { throw new Error("Antwort ist kein gültiges JSON"); });
      })
      .then(function (data) {
        if (id !== requestId) return;
        render(data);
      })
      .catch(function (err) {
        if (id !== requestId) return;
        var reason = err && err.name === "AbortError" ? "Zeitüberschreitung nach " + TIMEOUT_MS / 1000 + " s" : (err && err.message) || String(err);
        if (window.console && console.warn) console.warn("[ELBRAD] Wetterdaten nicht geladen:", reason);
        setState("error");
      })
      .finally(function () { clearTimeout(timer); });
  }

  el.retry.addEventListener("click", function () {
    el.heading.focus();
    loadWeather();
  });

  loadWeather();

