/* mm.tafil.app — terminal replay player.
 *
 * Replays the frames in demo-data.js, which are real captures from the CLI
 * (see site/tools/capture.py). It types the command, prints the recorded
 * output, then moves on. No dependencies.
 *
 * Rules this file follows:
 *   - output is never synthesised here; it is printed verbatim from the capture
 *   - autoplaying content is pausable (WCAG 2.2.2), and the step counter makes
 *     the manual controls discoverable rather than decorative
 *   - reduced motion drops the typing animation, not the content: frames still
 *     advance if the visitor presses play, but nothing starts moving unbidden
 *   - nothing plays off-screen or while the tab is hidden
 */
(function () {
  "use strict";

  var demo = window.MM_DEMO;
  if (!demo || !demo.scenarios || !demo.scenarios.length) return;

  var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  var TYPE_MS = 34;       // per character of the command
  var AFTER_CMD_MS = 300; // beat between hitting enter and output landing
  var HOLD_MS = 2700;     // how long a finished frame stays before advancing
  var HOLD_REDUCED_MS = 4200;

  var els = {
    tabs: document.getElementById("demo-tabs"),
    blurb: document.getElementById("demo-blurb"),
    body: document.getElementById("term-body"),
    note: document.getElementById("term-note"),
    title: document.getElementById("term-title"),
    count: document.getElementById("term-count"),
    prev: document.getElementById("term-prev"),
    next: document.getElementById("term-next"),
    toggle: document.getElementById("term-toggle"),
  };
  if (!els.body || !els.tabs) return;

  var state = { scenario: 0, frame: 0, timers: [], playing: false, autostarted: false };

  function clearTimers() {
    state.timers.forEach(clearTimeout);
    state.timers = [];
  }
  function later(fn, ms) {
    state.timers.push(setTimeout(fn, ms));
  }

  function scenario() { return demo.scenarios[state.scenario]; }
  function frames() { return scenario().frames; }

  function escapeHtml(s) {
    return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  function lineFor(frame, typed, caret) {
    var isComment = frame.cmd.charAt(0) === "#";
    var prompt = isComment ? "" : '<span class="prompt">$ </span>';
    var cls = isComment ? "prompt" : "cmd";
    return prompt + '<span class="' + cls + '">' + escapeHtml(typed) + "</span>" +
      (caret ? '<span class="caret"></span>' : "");
  }

  /* Everything before the current frame, already settled. */
  function history() {
    var out = "";
    for (var i = 0; i < state.frame; i++) {
      var f = frames()[i];
      out += lineFor(f, f.cmd, false) + "\n" + f.out + "\n\n";
    }
    return out;
  }

  function paint(currentHtml) {
    els.body.innerHTML = history() + currentHtml;
    els.body.scrollTop = els.body.scrollHeight;
  }

  function syncChrome() {
    var f = frames()[state.frame];
    els.note.textContent = f.note || "";
    if (els.count) els.count.textContent = (state.frame + 1) + " / " + frames().length;
    if (els.prev) els.prev.disabled = state.frame === 0;
    if (els.next) els.next.disabled = state.frame >= frames().length - 1;
    if (els.toggle) {
      var atEnd = !state.playing && state.frame >= frames().length - 1;
      els.toggle.textContent = state.playing ? "\u23F8" : (atEnd ? "\u21BB" : "\u25B6");
      els.toggle.setAttribute("aria-label",
        state.playing ? "Pause demo" : (atEnd ? "Replay demo" : "Play demo"));
      els.toggle.title = els.toggle.getAttribute("aria-label");
    }
  }

  function showFrame() {
    var f = frames()[state.frame];
    paint(lineFor(f, f.cmd, false) + "\n" + f.out);
    syncChrome();
  }

  /* Type the command, land the output, then queue the next frame. */
  function runFrame() {
    clearTimers();
    var f = frames()[state.frame];
    syncChrome();

    if (reduce) {
      showFrame();
      if (state.playing) later(advance, HOLD_REDUCED_MS);
      return;
    }

    var i = 0;
    (function typeNext() {
      paint(lineFor(f, f.cmd.slice(0, i), true));
      if (i < f.cmd.length) {
        i++;
        later(typeNext, TYPE_MS);
        return;
      }
      later(function () {
        paint(lineFor(f, f.cmd, false) + "\n" + f.out);
        if (state.playing) later(advance, HOLD_MS);
      }, AFTER_CMD_MS);
    })();
  }

  function advance() {
    if (state.frame < frames().length - 1) {
      state.frame++;
      runFrame();
    } else {
      pause();
    }
  }

  function play() {
    if (state.playing) return;
    state.playing = true;
    if (state.frame >= frames().length - 1) state.frame = 0;
    runFrame();
  }

  function pause() {
    state.playing = false;
    clearTimers();
    showFrame();
  }

  function step(delta) {
    pause();
    state.frame = Math.max(0, Math.min(state.frame + delta, frames().length - 1));
    showFrame();
  }

  function selectScenario(index, autoplay) {
    pause();
    state.scenario = index;
    state.frame = 0;
    var sc = scenario();
    els.blurb.textContent = sc.blurb;
    if (els.title) els.title.textContent = "mm — " + sc.label.toLowerCase();
    Array.prototype.forEach.call(els.tabs.children, function (btn, i) {
      btn.setAttribute("aria-selected", i === index ? "true" : "false");
      btn.tabIndex = i === index ? 0 : -1;
    });
    if (autoplay && !reduce) play();
    else showFrame();
  }

  /* ---------- controls ---------- */

  demo.scenarios.forEach(function (sc, i) {
    var b = document.createElement("button");
    b.type = "button";
    b.id = "demo-tab-" + sc.key;
    b.setAttribute("role", "tab");
    b.setAttribute("aria-controls", "demo-panel");
    b.setAttribute("aria-selected", i === 0 ? "true" : "false");
    b.tabIndex = i === 0 ? 0 : -1;
    b.textContent = sc.label;
    b.addEventListener("click", function () { selectScenario(i, true); });
    els.tabs.appendChild(b);
  });

  els.tabs.addEventListener("keydown", function (e) {
    var delta = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
    if (!delta) return;
    e.preventDefault();
    var next = (state.scenario + delta + demo.scenarios.length) % demo.scenarios.length;
    selectScenario(next, true);
    els.tabs.children[next].focus();
  });

  if (els.prev) els.prev.addEventListener("click", function () { step(-1); });
  if (els.next) els.next.addEventListener("click", function () { step(1); });
  if (els.toggle) els.toggle.addEventListener("click", function () {
    if (state.playing) pause(); else play();
  });

  document.addEventListener("visibilitychange", function () {
    if (document.hidden) pause();
  });

  /* ---------- boot: render immediately, play once seen ---------- */

  selectScenario(0, false);

  if (reduce || !("IntersectionObserver" in window)) return;

  var io = new IntersectionObserver(function (entries) {
    entries.forEach(function (entry) {
      if (entry.isIntersecting && !state.autostarted) {
        state.autostarted = true;
        io.disconnect();
        play();
      }
    });
  }, { threshold: 0.35 });
  io.observe(els.body);
})();

/* ---------- copy-to-clipboard for the install commands ---------- */
(function () {
  "use strict";
  document.querySelectorAll("[data-copy]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var text = btn.getAttribute("data-copy");
      var done = function () {
        var old = btn.textContent;
        btn.textContent = "copied";
        btn.setAttribute("data-done", "1");
        setTimeout(function () {
          btn.textContent = old;
          btn.removeAttribute("data-done");
        }, 1600);
      };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(done, fallback);
      } else {
        fallback();
      }
      function fallback() {
        var ta = document.createElement("textarea");
        ta.value = text;
        ta.setAttribute("readonly", "");
        ta.style.position = "fixed";
        ta.style.opacity = "0";
        document.body.appendChild(ta);
        ta.select();
        try { document.execCommand("copy"); done(); } catch (e) { /* nothing to do */ }
        document.body.removeChild(ta);
      }
    });
  });
})();
