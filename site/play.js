/* One afternoon, one moment at a time. Output matches mm 3.0.0. */
(function () {
  var steps = [
    {
      command: 'mm add "CS302"',
      response: "+ queued  1  CS302",
      explanation: "You’re about to study. Put it in the box, so your head can do the studying.",
      now: "CS302",
      badge: "QUEUE",
      hot: false,
      queue: [{ t: "1  CS302", active: true }],
      interrupts: [],
      quick: []
    },
    {
      command: "mm",
      response: "→  1  CS302   active",
      explanation: "One thing. You didn’t pick it off a list.",
      now: "CS302",
      badge: "QUEUE",
      hot: false,
      queue: [{ t: "1  CS302", active: true }],
      interrupts: [],
      quick: []
    },
    {
      command: 'mm add "write this up later"',
      response: "+ queued  2  write this up later",
      explanation: "An idea, in the middle of the work. It waits behind CS302. You stay on CS302.",
      now: "CS302",
      badge: "QUEUE",
      hot: false,
      queue: [
        { t: "1  CS302", active: true },
        { t: "2  write this up later", active: false }
      ],
      interrupts: [],
      quick: []
    },
    {
      command: "mm",
      response: "→  1  CS302   active",
      explanation: "A gap. The phone is right there. The box already has the next thing.",
      now: "CS302",
      badge: "QUEUE",
      hot: false,
      queue: [
        { t: "1  CS302", active: true },
        { t: "2  write this up later", active: false }
      ],
      interrupts: [],
      quick: []
    },
    {
      command: 'mm add -p "prod is down"',
      response: "! interrupt  3  prod is down",
      explanation: "Something more important. It goes on top. The study is still underneath.",
      now: "prod is down",
      badge: "STACK",
      hot: true,
      queue: [
        { t: "1  CS302", active: false },
        { t: "2  write this up later", active: false }
      ],
      interrupts: ["3  prod is down"],
      quick: []
    },
    {
      command: "mm done",
      response: "✓ done  3  prod is down\n→  1  CS302   active",
      explanation: "The interruption is finished. You are back on the study. The idea is still behind it.",
      now: "CS302",
      badge: "QUEUE",
      hot: false,
      queue: [
        { t: "1  CS302", active: true },
        { t: "2  write this up later", active: false }
      ],
      interrupts: [],
      quick: []
    },
    {
      command: 'mm add -q "email Sam"',
      response: "+ quick  4  email Sam",
      explanation: "A small nag. It stays off the line. It never becomes the next thing.",
      now: "CS302",
      badge: "QUEUE",
      hot: false,
      queue: [
        { t: "1  CS302", active: true },
        { t: "2  write this up later", active: false }
      ],
      interrupts: [],
      quick: ["4  email Sam"]
    }
  ];

  var index = 0;
  var playing = true;
  var timer = null;
  var HOLD = 3200;

  function el(id) {
    return document.getElementById(id);
  }

  function render(i) {
    var data = steps[i];
    el("sim-step").textContent = "STEP " + (i + 1) + " OF " + steps.length;
    el("sim-explanation").textContent = data.explanation;
    el("sim-command").textContent = data.command;
    el("sim-response").textContent = data.response;
    el("sim-response").className = data.hot
      ? "p-space-sm bg-surface-container border-2 border-secondary text-secondary font-mono-sm text-mono-sm whitespace-pre-wrap"
      : "p-space-sm bg-surface-container border border-outline-variant text-on-surface font-mono-sm text-mono-sm whitespace-pre-wrap";

    el("state-now-text").textContent = data.now;
    el("state-now-badge").textContent = data.badge;
    el("state-now-card").className = data.hot
      ? "p-space-md bg-surface-container-high border-2 border-secondary text-secondary font-mono-md text-mono-md flex items-start gap-space-sm"
      : "p-space-md bg-surface-container border border-outline-variant text-primary font-mono-md text-mono-md flex items-start gap-space-sm";

    var intrList = el("state-intr-list");
    var intrBox = el("state-intr-box");
    el("state-intr-count").textContent = data.interrupts.length + (data.interrupts.length === 1 ? " item" : " items");
    intrList.textContent = "";
    if (data.interrupts.length) {
      intrBox.classList.add("border-secondary");
      data.interrupts.forEach(function (line) {
        var row = document.createElement("div");
        row.className = "text-secondary font-semibold";
        row.textContent = line;
        intrList.appendChild(row);
      });
    } else {
      intrBox.classList.remove("border-secondary");
      var empty = document.createElement("span");
      empty.className = "italic text-outline";
      empty.textContent = "—";
      intrList.appendChild(empty);
    }

    var queueList = el("state-queue-list");
    queueList.textContent = "";
    el("state-queue-count").textContent = data.queue.length + (data.queue.length === 1 ? " item" : " items");
    data.queue.forEach(function (item) {
      var row = document.createElement("div");
      row.className = item.active ? "text-primary font-medium" : "text-on-surface-variant";
      row.textContent = item.t + (item.active ? "   active" : "");
      queueList.appendChild(row);
    });

    var quickList = el("state-quick-list");
    quickList.textContent = "";
    el("state-quick-count").textContent = data.quick.length + (data.quick.length === 1 ? " item" : " items");
    if (!data.quick.length) {
      var qe = document.createElement("span");
      qe.className = "italic text-outline";
      qe.textContent = "—";
      quickList.appendChild(qe);
    } else {
      data.quick.forEach(function (line) {
        var row = document.createElement("div");
        row.className = "text-on-surface-variant";
        row.textContent = line;
        quickList.appendChild(row);
      });
    }
  }

  function start() {
    clearInterval(timer);
    timer = setInterval(function () {
      index = (index + 1) % steps.length;
      render(index);
    }, HOLD);
    playing = true;
    el("sim-toggle").textContent = "PAUSE";
  }

  function stop() {
    clearInterval(timer);
    timer = null;
    playing = false;
    el("sim-toggle").textContent = "PLAY";
  }

  el("sim-toggle").addEventListener("click", function () {
    if (playing) stop();
    else start();
  });

  el("sim-replay").addEventListener("click", function () {
    index = 0;
    render(0);
    start();
  });

  function copyText(text, button, doneLabel, idleLabel) {
    if (!navigator.clipboard) return;
    navigator.clipboard.writeText(text).then(function () {
      button.textContent = doneLabel;
      setTimeout(function () {
        button.textContent = idleLabel;
      }, 1600);
    });
  }

  var installUnix = "git clone https://github.com/Toseef-Ahmad/mm.git && cd mm && ./install.sh";
  var installWindows = "git clone https://github.com/Toseef-Ahmad/mm.git\ncd mm\ninstall.cmd";
  var isWindows = /Windows/i.test(navigator.userAgent || "") || /^Win/i.test(navigator.platform || "");
  var install = isWindows ? installWindows : installUnix;
  var cmdEl = el("install-cmd");
  if (cmdEl) cmdEl.textContent = install;
  el("copy-install").addEventListener("click", function () {
    copyText(install, el("copy-install"), "COPIED", "COPY");
  });
  el("copy-snippet").addEventListener("click", function () {
    copyText(install, el("copy-snippet"), "COPIED", "COPY INSTALL COMMAND");
  });

  render(0);
  start();
})();
