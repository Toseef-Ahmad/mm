/* Transcript captured from mm 3.0.0 on 2026-09-22, NO_COLOR=1. */
(function () {
  var steps = [
    {
      cmd: 'mm add "CS302"',
      out: [{ k: "good", t: "  + queued  1  CS302" }],
      trays: {
        interrupt: [],
        queue: [{ id: "1", text: "CS302" }],
        quick: []
      }
    },
    {
      cmd: "mm",
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
      out: [{ k: "hot", t: "  ! interrupt  2  prod is down" }],
      trays: {
        interrupt: [{ id: "2", text: "prod is down", hot: true }],
        queue: [{ id: "1", text: "CS302", active: true }],
        quick: []
      }
    },
    {
      cmd: "mm",
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

  function wait(ms) {
    return new Promise(function (resolve) {
      timer = setTimeout(resolve, reduce ? 0 : ms);
    });
  }

  function typeCmd(cmd) {
    var holder = document.createElement("span");
    screen.appendChild(holder);
    var prompt = document.createElement("span");
    prompt.className = "dim";
    prompt.textContent = "$ ";
    holder.appendChild(prompt);
    var typed = document.createElement("span");
    holder.appendChild(typed);
    var caret = document.createElement("span");
    caret.className = "caret";
    caret.setAttribute("aria-hidden", "true");
    holder.appendChild(caret);

    if (reduce) {
      typed.textContent = cmd;
      caret.remove();
      holder.appendChild(document.createTextNode("\n"));
      return Promise.resolve();
    }

    var i = 0;
    return new Promise(function (resolve) {
      (function tick() {
        typed.textContent = cmd.slice(0, i);
        if (i >= cmd.length) {
          caret.remove();
          holder.appendChild(document.createTextNode("\n"));
          resolve();
          return;
        }
        i += 1;
        timer = setTimeout(tick, 28);
      })();
    });
  }

  async function play() {
    stop();
    screen.replaceChildren();
    renderTrays(empty);
    replay.disabled = true;
    for (var n = 0; n < steps.length; n += 1) {
      var step = steps[n];
      await typeCmd(step.cmd);
      await wait(180);
      step.out.forEach(function (row) {
        line(screen, row.k, row.t);
      });
      renderTrays(step.trays);
      screen.parentElement.scrollTop = screen.parentElement.scrollHeight;
      await wait(700);
    }
    var caret = document.createElement("span");
    caret.className = "caret";
    caret.setAttribute("aria-hidden", "true");
    var prompt = document.createElement("span");
    prompt.className = "dim";
    prompt.textContent = "$ ";
    screen.appendChild(prompt);
    screen.appendChild(caret);
    replay.disabled = false;
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

  play();
})();
