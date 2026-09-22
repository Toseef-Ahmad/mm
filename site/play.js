/* Transcript captured from mm 3.0.0 on 2026-09-22, NO_COLOR=1. */
(function () {
  var steps = [
    {
      cmd: 'mm add "CS302"',
      say: "The work leaves your head and sits in the queue.",
      out: [{ k: "good", t: "  + queued  1  CS302" }],
      trays: {
        interrupt: [],
        queue: [{ id: "1", text: "CS302" }],
        quick: []
      }
    },
    {
      cmd: "mm",
      say: "mm shows that one thing. You do not pick.",
      out: [
        { k: "", t: "" },
        { k: "arrow", t: "  →  1  CS302   0m00s active" },
        { k: "", t: "" }
      ],
      trays: {
        interrupt: [],
        queue: [{ id: "1", text: "CS302", active: true }],
        quick: []
      }
    },
    {
      cmd: 'mm add -p "prod is down"',
      say: "Something more important just came up. It goes on the stack, above the queue.",
      out: [{ k: "hot", t: "  ! interrupt  2  prod is down" }],
      trays: {
        interrupt: [{ id: "2", text: "prod is down", hot: true }],
        queue: [{ id: "1", text: "CS302", active: true }],
        quick: []
      }
    },
    {
      cmd: "mm",
      say: "The stack goes first. CS302 is still underneath.",
      out: [
        { k: "", t: "" },
        { k: "arrow", t: "  →  2  prod is down   interrupt" },
        { k: "", t: "" }
      ],
      trays: {
        interrupt: [{ id: "2", text: "prod is down", hot: true, active: true }],
        queue: [{ id: "1", text: "CS302" }],
        quick: []
      }
    },
    {
      cmd: "mm done",
      say: "The interruption is finished. You are back on CS302.",
      out: [
        { k: "", t: "" },
        { k: "good", t: "  ✓ done  2  prod is down" },
        { k: "", t: "" },
        { k: "arrow", t: "  →  1  CS302   0m00s active" },
        { k: "", t: "" }
      ],
      trays: {
        interrupt: [],
        queue: [{ id: "1", text: "CS302", active: true }],
        quick: []
      }
    },
    {
      cmd: 'mm add -q "email Sam"',
      say: "A small nag goes in quick. It does not jump the line, and you can stop rehearsing it.",
      out: [{ k: "dim", t: "  + quick  3  email Sam" }],
      trays: {
        interrupt: [],
        queue: [{ id: "1", text: "CS302", active: true }],
        quick: [{ id: "3", text: "email Sam", quiet: true }]
      }
    }
  ];

  var empty = { interrupt: [], queue: [], quick: [] };
  var screen = document.getElementById("screen");
  var replay = document.getElementById("replay");
  var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var timer = null;
  var runId = 0;
  var HOLD = 1900;

  function line(parent, cls, text) {
    var span = document.createElement("span");
    if (cls) span.className = cls;
    span.textContent = text + "\n";
    parent.appendChild(span);
  }

  function renderTrays(trays) {
    ["interrupt", "queue", "quick"].forEach(function (name) {
      var slot = document.getElementById("tray-" + name);
      slot.replaceChildren();
      var items = trays[name];
      if (!items.length) {
        var p = document.createElement("p");
        p.className = "empty";
        p.textContent = "empty";
        slot.appendChild(p);
        return;
      }
      items.forEach(function (item) {
        var row = document.createElement("p");
        row.className = "slip" + (item.hot ? " hot" : "") + (item.quiet ? " quiet" : "") + (item.active ? " active" : "");
        var id = document.createElement("i");
        id.textContent = item.id;
        row.appendChild(id);
        row.appendChild(document.createTextNode(item.text));
        slot.appendChild(row);
      });
    });
  }

  function stop() {
    if (timer) clearTimeout(timer);
    timer = null;
  }

  function wait(ms, mine) {
    return new Promise(function (resolve) {
      timer = setTimeout(function () { resolve(mine === runId); }, ms);
    });
  }

  function typeCmd(cmd, mine) {
    var holder = document.createElement("span");
    screen.appendChild(holder);
    var prompt = document.createElement("span");
    prompt.className = "dim";
    prompt.textContent = "$ ";
    holder.appendChild(prompt);
    var typed = document.createElement("span");
    holder.appendChild(typed);

    if (reduce) {
      typed.textContent = cmd + "\n";
      return Promise.resolve();
    }

    var caret = document.createElement("span");
    caret.className = "caret";
    caret.setAttribute("aria-hidden", "true");
    holder.appendChild(caret);

    var i = 0;
    return new Promise(function (resolve) {
      (function tick() {
        if (mine !== runId) { resolve(false); return; }
        typed.textContent = cmd.slice(0, i);
        if (i >= cmd.length) {
          caret.remove();
          holder.appendChild(document.createTextNode("\n"));
          resolve(true);
          return;
        }
        i += 1;
        timer = setTimeout(tick, 42);
      })();
    });
  }

  async function play() {
    var mine = ++runId;
    stop();
    screen.replaceChildren();
    renderTrays(empty);
    var beat0 = document.getElementById("beat");
    if (beat0) beat0.textContent = "Nothing is in the box until you type it.";
    replay.disabled = true;
    replay.textContent = "Playing…";
    if (!(await wait(500, mine))) return;
    for (var n = 0; n < steps.length; n += 1) {
      if (mine !== runId) return;
      var step = steps[n];
      if (!(await typeCmd(step.cmd, mine))) return;
      if (!(await wait(320, mine))) return;
      step.out.forEach(function (row) {
        line(screen, row.k, row.t);
      });
      renderTrays(step.trays);
      var beat = document.getElementById("beat");
      if (beat && step.say) beat.textContent = step.say;
      screen.parentElement.scrollTop = screen.parentElement.scrollHeight;
      if (!(await wait(HOLD, mine))) return;
    }
    if (mine !== runId) return;
    var promptEnd = document.createElement("span");
    promptEnd.className = "dim";
    promptEnd.textContent = "$ ";
    screen.appendChild(promptEnd);
    if (!reduce) {
      var caret = document.createElement("span");
      caret.className = "caret";
      caret.setAttribute("aria-hidden", "true");
      screen.appendChild(caret);
    }
    replay.disabled = false;
    replay.textContent = "Play again";
  }

  replay.addEventListener("click", function () {
    play();
  });

  var copyBtn = document.getElementById("copy");
  copyBtn.addEventListener("click", function () {
    var text = document.getElementById("install").textContent.trim();
    var done = function () {
      copyBtn.textContent = "Copied";
      setTimeout(function () { copyBtn.textContent = "Copy"; }, 1400);
    };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(done).catch(done);
      return;
    }
    done();
  });

  var started = false;
  function startOnce() {
    if (started) return;
    started = true;
    play();
  }
  if ("IntersectionObserver" in window) {
    var watch = new IntersectionObserver(function (entries) {
      if (entries.some(function (entry) { return entry.isIntersecting; })) {
        watch.disconnect();
        startOnce();
      }
    }, { threshold: 0.4 });
    watch.observe(screen.closest(".term") || screen);
  } else {
    startOnce();
  }
})();
