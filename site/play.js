/* One afternoon, one moment at a time. Output matches mm 3.0.0. */
(function () {
  var steps = [
    {
      command: 'mm add "CS302"',
      response: "+ queued  1  CS302",
      explanation: "You’re about to study. Put it in the box, so your head can do the studying.",
      now: "CS302",
      badge: "Queue",
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
      badge: "Queue",
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
      badge: "Queue",
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
      badge: "Queue",
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
      badge: "Stack",
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
      badge: "Queue",
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
      badge: "Queue",
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

  function installForThisOs() {
    var reported = (navigator.userAgentData && navigator.userAgentData.platform) || "";
    var blob = (reported + " " + (navigator.userAgent || "") + " " + (navigator.platform || "")).toLowerCase();
    var windows = "git clone https://github.com/Toseef-Ahmad/mm.git\ncd mm\ninstall.cmd";
    var unix = "git clone https://github.com/Toseef-Ahmad/mm.git && cd mm && ./install.sh";
    if (blob.indexOf("win") !== -1) return { os: "Windows", command: windows };
    if (blob.indexOf("linux") !== -1 || blob.indexOf("android") !== -1 || blob.indexOf("cros") !== -1) {
      return { os: "Linux", command: unix };
    }
    if (blob.indexOf("mac") !== -1 || blob.indexOf("iphone") !== -1 || blob.indexOf("ipad") !== -1) {
      return { os: "macOS", command: unix };
    }
    return { os: "macOS / Linux", command: unix };
  }

  var installChoice = installForThisOs();
  var install = installChoice.command;
  if (el("install-os")) el("install-os").textContent = installChoice.os;
  if (el("install-cmd")) el("install-cmd").textContent = install;

  function render(i) {
    var data = steps[i];
    el("sim-step").textContent = "Step " + (i + 1) + " of " + steps.length;
    el("sim-explanation").textContent = data.explanation;
    el("sim-command").textContent = data.command;
    el("sim-response").textContent = data.response;
    el("sim-response").className = data.hot ? "term-response is-hot" : "term-response";

    el("state-now-text").textContent = data.now;
    el("state-now-badge").textContent = data.badge;
    el("state-now-card").className = data.hot ? "state-now-card is-hot" : "state-now-card";

    var intrList = el("state-intr-list");
    var intrBox = el("state-intr-box");
    el("state-intr-count").textContent = data.interrupts.length + (data.interrupts.length === 1 ? " item" : " items");
    intrList.textContent = "";
    if (data.interrupts.length) {
      intrBox.classList.add("has-items");
      data.interrupts.forEach(function (line) {
        var row = document.createElement("div");
        row.className = "is-hot";
        row.textContent = line;
        intrList.appendChild(row);
      });
    } else {
      intrBox.classList.remove("has-items");
      var empty = document.createElement("span");
      empty.className = "is-empty";
      empty.textContent = "—";
      intrList.appendChild(empty);
    }

    var queueList = el("state-queue-list");
    queueList.textContent = "";
    el("state-queue-count").textContent = data.queue.length + (data.queue.length === 1 ? " item" : " items");
    data.queue.forEach(function (item) {
      var row = document.createElement("div");
      row.className = item.active ? "is-active" : "";
      row.textContent = item.t + (item.active ? "   active" : "");
      queueList.appendChild(row);
    });

    var quickList = el("state-quick-list");
    quickList.textContent = "";
    el("state-quick-count").textContent = data.quick.length + (data.quick.length === 1 ? " item" : " items");
    if (!data.quick.length) {
      var qe = document.createElement("span");
      qe.className = "is-empty";
      qe.textContent = "—";
      quickList.appendChild(qe);
    } else {
      data.quick.forEach(function (line) {
        var row = document.createElement("div");
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
    el("sim-toggle").textContent = "Pause";
  }

  function stop() {
    clearInterval(timer);
    timer = null;
    playing = false;
    el("sim-toggle").textContent = "Play";
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

  el("copy-install").addEventListener("click", function () {
    copyText(install, el("copy-install"), "Copied", "Copy");
  });
  el("copy-snippet").addEventListener("click", function () {
    copyText(install, el("copy-snippet"), "Copied", "Copy install command");
  });

  render(0);
  start();
})();
