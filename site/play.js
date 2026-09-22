/* One moment at a time. Captured phrasing from mm 3.0.0. */
(function () {
  var steps = [
    {
      cmd: 'mm add "CS302"',
      say: "You’re about to study. Put it in the box, so your head can do the studying.",
      out: [{ k: "good", t: "  + queued  1  CS302" }],
      trays: {
        interrupt: [],
        queue: [{ id: "1", text: "CS302", active: true }],
        quick: []
      }
    },
    {
      cmd: "mm",
      say: "One thing. You didn’t pick it off a list.",
      out: [{ k: "arrow", t: "  →  1  CS302   active" }],
      trays: {
        interrupt: [],
        queue: [{ id: "1", text: "CS302", active: true }],
        quick: []
      }
    },
    {
      cmd: 'mm add "write this up later"',
      say: "An idea, in the middle of the work. It waits behind CS302. You stay on CS302.",
      out: [{ k: "good", t: "  + queued  2  write this up later" }],
      trays: {
        interrupt: [],
        queue: [
          { id: "1", text: "CS302", active: true },
          { id: "2", text: "write this up later" }
        ],
        quick: []
      }
    },
    {
      cmd: "mm",
      say: "A gap. The phone is right there. The box already has the next thing.",
      out: [{ k: "arrow", t: "  →  1  CS302   active" }],
      trays: {
        interrupt: [],
        queue: [
          { id: "1", text: "CS302", active: true },
          { id: "2", text: "write this up later" }
        ],
        quick: []
      }
    },
    {
      cmd: 'mm add -p "prod is down"',
      say: "Something more important. It goes on top. The study is still underneath.",
      out: [{ k: "hot", t: "  ! interrupt  3  prod is down" }],
      trays: {
        interrupt: [{ id: "3", text: "prod is down", hot: true, active: true }],
        queue: [
          { id: "1", text: "CS302" },
          { id: "2", text: "write this up later" }
        ],
        quick: []
      }
    },
    {
      cmd: "mm done",
      say: "The interruption is finished. You are back on the study. The idea is still behind it.",
      out: [
        { k: "good", t: "  ✓ done  3  prod is down" },
        { k: "arrow", t: "  →  1  CS302   active" }
      ],
      trays: {
        interrupt: [],
        queue: [
          { id: "1", text: "CS302", active: true },
          { id: "2", text: "write this up later" }
        ],
        quick: []
      }
    },
    {
      cmd: 'mm add -q "email Sam"',
      say: "A small nag. It stays off the line, and out of your head.",
      out: [{ k: "dim", t: "  + quick  4  email Sam" }],
      trays: {
        interrupt: [],
        queue: [
          { id: "1", text: "CS302", active: true },
          { id: "2", text: "write this up later" }
        ],
        quick: [{ id: "4", text: "email Sam", quiet: true }]
      }
    }
  ];

  var screen = document.getElementById("screen");
  var beat = document.getElementById("beat");
  var again = document.getElementById("replay");
  var timer = null;

  function line(cls, text) {
    var span = document.createElement("div");
    if (cls) span.className = cls;
    span.textContent = text;
    screen.appendChild(span);
  }

  function show(step) {
    screen.replaceChildren();
    line("dim", "$ " + step.cmd);
    step.out.forEach(function (row) { line(row.k, row.t); });
    beat.textContent = step.say;
    ["interrupt", "queue", "quick"].forEach(function (name) {
      var slot = document.getElementById("tray-" + name);
      slot.replaceChildren();
      var items = step.trays[name];
      if (!items.length) {
        var dash = document.createElement("p");
        dash.className = "empty";
        dash.textContent = "—";
        slot.appendChild(dash);
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

  function play() {
    if (timer) clearInterval(timer);
    var i = 0;
    show(steps[0]);
    timer = setInterval(function () {
      i += 1;
      if (i >= steps.length) {
        clearInterval(timer);
        timer = null;
        return;
      }
      show(steps[i]);
    }, 2600);
  }

  again.addEventListener("click", play);

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
