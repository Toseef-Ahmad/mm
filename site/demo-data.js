// GENERATED FILE — do not edit by hand.
// Every frame below is real output from the mm CLI, captured by
// site/tools/capture.py inside a pseudo-terminal. Regenerate with:
//     python3 site/tools/capture.py
window.MM_DEMO = {
 "version": "mm 2.1.0",
 "scenarios": [
  {
   "key": "ritual",
   "label": "The ritual",
   "blurb": "Two commands, and a day that queues itself.",
   "frames": [
    {
     "cmd": "mm status",
     "out": "<i class=\"d\">  4 habit(s) due → queued</i>\n\n  <i class=\"b\">interrupt</i>  <i class=\"d\">0/5</i>\n<i class=\"d\">     —</i>\n\n  <i class=\"b\">queue</i>  <i class=\"d\">4/12</i>   <i class=\"a\">gate open — only gate items selectable</i>\n    <i class=\"d\"> 4</i>  <i class=\"d\">Inbox triage</i><i class=\"d\">  · gate-locked</i>\n  <i class=\"a\">→</i> <i class=\"d\"> 1</i>  Deep work — one hard problem, no tabs\n    <i class=\"d\"> 2</i>  Reading — one chapter, no phone\n    <i class=\"d\"> 3</i>  <i class=\"d\">Walk — one loop outside</i><i class=\"d\">  · gate-locked</i>\n\n  <i class=\"b\">quick</i>  <i class=\"d\">0/50</i>\n<i class=\"d\">     —</i>",
     "note": "The day is already queued from your config. You typed none of this."
    },
    {
     "cmd": "mm",
     "out": "  <i class=\"a\">→</i> <i class=\"d\"> 1</i>  Deep work — one hard problem, no tabs   <i class=\"d\">0m00s active</i>",
     "note": "One command asks the only question that matters. mm picks; you do not."
    },
    {
     "cmd": "mm done",
     "out": "  <i class=\"g\">✓ done</i>  <i class=\"d\">1</i>  Deep work — one hard problem, no tabs<i class=\"d\">  · streak 1</i>\n  <i class=\"d\">gates</i> <i class=\"g\">1</i> <i class=\"d\">closed ·</i> <i class=\"w\">1</i> <i class=\"d\">to go — reward unlocks at zero</i>\n\n  <i class=\"a\">→</i> <i class=\"d\"> 2</i>  Reading — one chapter, no phone   <i class=\"d\">0m00s active</i>",
     "note": "Closed — and the next thing is already on screen."
    },
    {
     "cmd": "mm done",
     "out": "  <i class=\"g\">✓ done</i>  <i class=\"d\">2</i>  Reading — one chapter, no phone<i class=\"d\">  · streak 1</i>\n\n  <i class=\"g\">★ ALL GATES CLOSED</i> — <i class=\"b\">day earned.</i>\n  <i class=\"b\">reward unlocked:</i> the evening is yours, guilt-free\n  <i class=\"d\">streak:</i> <i class=\"b\">1</i> <i class=\"d\">day(s) of fully closed loops</i>\n\n  <i class=\"a\">→</i> <i class=\"d\"> 4</i>  Inbox triage   <i class=\"d\">0m00s active</i>",
     "note": "Both gates shut, so the day is earned. That is the entire ritual: mm, mm done, repeat."
    }
   ]
  },
  {
   "key": "gates",
   "label": "Gates",
   "blurb": "The easy thing is not on the menu.",
   "frames": [
    {
     "cmd": "mm status",
     "out": "  <i class=\"b\">interrupt</i>  <i class=\"d\">0/5</i>\n<i class=\"d\">     —</i>\n\n  <i class=\"b\">queue</i>  <i class=\"d\">4/12</i>   <i class=\"a\">gate open — only gate items selectable</i>\n    <i class=\"d\"> 4</i>  <i class=\"d\">Inbox triage</i><i class=\"d\">  · gate-locked</i>\n  <i class=\"a\">→</i> <i class=\"d\"> 1</i>  Deep work — one hard problem, no tabs\n    <i class=\"d\"> 2</i>  Reading — one chapter, no phone\n    <i class=\"d\"> 3</i>  <i class=\"d\">Walk — one loop outside</i><i class=\"d\">  · gate-locked</i>\n\n  <i class=\"b\">quick</i>  <i class=\"d\">0/50</i>\n<i class=\"d\">     —</i>",
     "note": "Inbox triage sits at the top of the list — and mm still will not offer it. A gate is open, so the pointer skips to the work you said mattered."
    },
    {
     "cmd": "mm",
     "out": "  <i class=\"a\">→</i> <i class=\"d\"> 1</i>  Deep work — one hard problem, no tabs   <i class=\"d\">0m00s active</i>",
     "note": "No negotiation, no willpower. There is nothing else to pick."
    },
    {
     "cmd": "mm done",
     "out": "  <i class=\"g\">✓ done</i>  <i class=\"d\">1</i>  Deep work — one hard problem, no tabs<i class=\"d\">  · streak 1</i>\n  <i class=\"d\">gates</i> <i class=\"g\">1</i> <i class=\"d\">closed ·</i> <i class=\"w\">1</i> <i class=\"d\">to go — reward unlocks at zero</i>\n\n  <i class=\"a\">→</i> <i class=\"d\"> 2</i>  Reading — one chapter, no phone   <i class=\"d\">0m00s active</i>",
     "note": "Close the gate and the day opens up. The reward is paid on closed loops, not on good intentions."
    },
    {
     "cmd": "mm status",
     "out": "  <i class=\"b\">interrupt</i>  <i class=\"d\">0/5</i>\n<i class=\"d\">     —</i>\n\n  <i class=\"b\">queue</i>  <i class=\"d\">3/12</i>   <i class=\"a\">gate open — only gate items selectable</i>\n    <i class=\"d\"> 4</i>  <i class=\"d\">Inbox triage</i><i class=\"d\">  · gate-locked</i>\n  <i class=\"a\">→</i> <i class=\"d\"> 2</i>  Reading — one chapter, no phone\n    <i class=\"d\"> 3</i>  <i class=\"d\">Walk — one loop outside</i><i class=\"d\">  · gate-locked</i>\n\n  <i class=\"b\">quick</i>  <i class=\"d\">0/50</i>\n<i class=\"d\">     —</i>",
     "note": "Gate closed. Now the small stuff is reachable."
    }
   ]
  },
  {
   "key": "interrupt",
   "label": "Interrupts",
   "blurb": "Urgency preempts, then unwinds.",
   "frames": [
    {
     "cmd": "mm",
     "out": "  <i class=\"a\">→</i> <i class=\"d\"> 1</i>  Deep work — one hard problem, no tabs   <i class=\"d\">0m00s active</i>",
     "note": "Mid-task on the thing that matters."
    },
    {
     "cmd": "mm add -p \"prod is down\"",
     "out": "  <i class=\"w\">!</i> interrupt  <i class=\"d\">5</i>  prod is down",
     "note": "A genuine fire goes on the interrupt stack."
    },
    {
     "cmd": "mm",
     "out": "  <i class=\"a\">→</i> <i class=\"d\"> 5</i>  prod is down   <i class=\"w\">interrupt</i>",
     "note": "It preempts everything. LIFO, like a call stack."
    },
    {
     "cmd": "mm done",
     "out": "  <i class=\"g\">✓ done</i>  <i class=\"d\">5</i>  prod is down\n\n  <i class=\"a\">→</i> <i class=\"d\"> 1</i>  Deep work — one hard problem, no tabs   <i class=\"d\">0m00s active</i>",
     "note": "Fire out — and the stack unwinds to exactly where you were. An interruption cannot quietly become your new plan."
    }
   ]
  },
  {
   "key": "habits",
   "label": "Habits",
   "blurb": "Configure once, queued forever.",
   "frames": [
    {
     "cmd": "cat ~/.mm/mm.toml",
     "out": "<i class=\"d\"># gate = true  -&gt; until this is closed, mm will not offer you anything else.</i>\n<i class=\"a\">[[habits]]</i>\nname = \"Deep work\"\ndescription = \"one hard problem, no tabs\"\ntype = \"focus\"\nrepeat = 1\nposition = \"queue\"\ngate = true\nweight = 9\nobsidian = \"deep_work\"\n<i class=\"d\"></i>\n<i class=\"d\"># order = 1 puts it at the front of the list — which is not the same as being</i>\n<i class=\"d\"># selectable. While a gate is open this shows as gate-locked.</i>\n<i class=\"a\">[[habits]]</i>\nname = \"Inbox triage\"\ntype = \"admin\"\nrepeat = 1\nposition = \"queue\"\ngate = false\nweight = 1\norder = 1\nobsidian = \"inbox\"",
     "note": "Declare it once, in one file you own. There is no \"add task\" step in the morning."
    },
    {
     "cmd": "mm status",
     "out": "<i class=\"d\">  4 habit(s) due → queued</i>\n\n  <i class=\"b\">interrupt</i>  <i class=\"d\">0/5</i>\n<i class=\"d\">     —</i>\n\n  <i class=\"b\">queue</i>  <i class=\"d\">4/12</i>   <i class=\"a\">gate open — only gate items selectable</i>\n    <i class=\"d\"> 4</i>  <i class=\"d\">Inbox triage</i><i class=\"d\">  · gate-locked</i>\n  <i class=\"a\">→</i> <i class=\"d\"> 1</i>  Deep work — one hard problem, no tabs\n    <i class=\"d\"> 2</i>  Reading — one chapter, no phone\n    <i class=\"d\"> 3</i>  <i class=\"d\">Walk — one loop outside</i><i class=\"d\">  · gate-locked</i>\n\n  <i class=\"b\">quick</i>  <i class=\"d\">0/50</i>\n<i class=\"d\">     —</i>",
     "note": "Everything due today is already queued. You did not type any of it."
    },
    {
     "cmd": "mm habit list",
     "out": "  <i class=\"b\">habits</i>  <i class=\"d\">4 declared</i>\n\n  <i class=\"g\">→</i> Inbox triage                 <i class=\"d\">admin     </i> <i class=\"d\">daily                 </i> <i class=\"d\">streak</i> <i class=\"b\">0</i>  <i class=\"d\">last</i> —<i class=\"d\">  · queue · w1 · #1</i>\n  <i class=\"g\">→</i> Deep work                    <i class=\"d\">focus     </i> <i class=\"d\">daily                 </i> <i class=\"d\">streak</i> <i class=\"b\">0</i>  <i class=\"d\">last</i> —<i class=\"d\">  · gate · queue · w9</i>\n  <i class=\"g\">→</i> Reading                      <i class=\"d\">book      </i> <i class=\"d\">daily                 </i> <i class=\"d\">streak</i> <i class=\"b\">0</i>  <i class=\"d\">last</i> —<i class=\"d\">  · gate · queue · w6</i>\n  <i class=\"g\">→</i> Walk                         <i class=\"d\">fitness   </i> <i class=\"d\">daily                 </i> <i class=\"d\">streak</i> <i class=\"b\">0</i>  <i class=\"d\">last</i> —<i class=\"d\">  · queue · w2</i>",
     "note": "The whole schedule, with cadence and streaks. gate, w9, #1 are the flags from the file."
    },
    {
     "cmd": "mm habit log 'Deep work'",
     "out": "  <i class=\"b\">Deep work</i>  <i class=\"d\">streak 1</i>  <i class=\"d\">best 1</i>  <i class=\"d\">pts 9</i>\n     2026-08-19  <i class=\"g\">done</i>",
     "note": "Streaks are gap-aware: a repeat = 3 habit is never punished for the two days it was not due."
    }
   ]
  },
  {
   "key": "obsidian",
   "label": "Obsidian",
   "blurb": "Your daily note, synced both ways.",
   "frames": [
    {
     "cmd": "cat '2026-08-19.md'",
     "out": "<i class=\"d\">---</i>\ntype: daily\nenergy: 3\n<i class=\"d\">reading: false</i>\n<i class=\"d\">deep_work: false</i>\n<i class=\"d\">walk: false</i>\n<i class=\"d\">inbox: false</i>\n<i class=\"d\">---</i>\n\n# 2026-08-19\n\n## Daily targets\n\n| Target | Property | Weight |\n|---|---|---|\n| Deep work | `deep_work` | 9 |\n| Reading | `reading` | 6 |\n| Walk | `walk` | 2 |\n| Inbox triage | `inbox` | 1 |",
     "note": "Your Obsidian daily note. Plain checkbox properties — mm did not invent a format for you."
    },
    {
     "cmd": "mm status",
     "out": "  <i class=\"b\">interrupt</i>  <i class=\"d\">0/5</i>\n<i class=\"d\">     —</i>\n\n  <i class=\"b\">queue</i>  <i class=\"d\">4/12</i>   <i class=\"a\">gate open — only gate items selectable</i>\n    <i class=\"d\"> 4</i>  <i class=\"d\">Inbox triage</i><i class=\"d\">  · gate-locked</i>\n  <i class=\"a\">→</i> <i class=\"d\"> 1</i>  Deep work — one hard problem, no tabs\n    <i class=\"d\"> 2</i>  Reading — one chapter, no phone\n    <i class=\"d\"> 3</i>  <i class=\"d\">Walk — one loop outside</i><i class=\"d\">  · gate-locked</i>\n\n  <i class=\"b\">quick</i>  <i class=\"d\">0/50</i>\n<i class=\"d\">     —</i>",
     "note": "Same habits, one list, two front ends."
    },
    {
     "cmd": "# you tick the box in Obsidian",
     "out": "<i class=\"d\">---</i>\ntype: daily\nenergy: 3\n<i class=\"g\">reading: true</i>\n<i class=\"d\">deep_work: false</i>\n<i class=\"d\">walk: false</i>\n<i class=\"d\">inbox: false</i>\n<i class=\"d\">---</i>\n\n# 2026-08-19\n\n## Daily targets\n\n| Target | Property | Weight |\n|---|---|---|\n| Deep work | `deep_work` | 9 |\n| Reading | `reading` | 6 |\n| Walk | `walk` | 2 |\n| Inbox triage | `inbox` | 1 |",
     "note": "Tick it in the app you already have open."
    },
    {
     "cmd": "mm status",
     "out": "<i class=\"d\">  obsidian done: Reading</i>\n\n  <i class=\"b\">interrupt</i>  <i class=\"d\">0/5</i>\n<i class=\"d\">     —</i>\n\n  <i class=\"b\">queue</i>  <i class=\"d\">3/12</i>   <i class=\"a\">gate open — only gate items selectable</i>\n    <i class=\"d\"> 4</i>  <i class=\"d\">Inbox triage</i><i class=\"d\">  · gate-locked</i>\n  <i class=\"a\">→</i> <i class=\"d\"> 1</i>  Deep work — one hard problem, no tabs\n    <i class=\"d\"> 3</i>  <i class=\"d\">Walk — one loop outside</i><i class=\"d\">  · gate-locked</i>\n\n  <i class=\"b\">quick</i>  <i class=\"d\">0/50</i>\n<i class=\"d\">     —</i>",
     "note": "Gone from the queue, streak credited. No import step."
    },
    {
     "cmd": "mm done",
     "out": "  <i class=\"g\">✓ done</i>  <i class=\"d\">1</i>  Deep work — one hard problem, no tabs<i class=\"d\">  · streak 1</i>\n\n  <i class=\"g\">★ ALL GATES CLOSED</i> — <i class=\"b\">day earned.</i>\n  <i class=\"b\">reward unlocked:</i> the evening is yours, guilt-free\n  <i class=\"d\">streak:</i> <i class=\"b\">1</i> <i class=\"d\">day(s) of fully closed loops</i>\n\n  <i class=\"a\">→</i> <i class=\"d\"> 4</i>  Inbox triage   <i class=\"d\">0m00s active</i>",
     "note": "Now go the other way: close it in the terminal."
    },
    {
     "cmd": "cat '2026-08-19.md'",
     "out": "<i class=\"d\">---</i>\ntype: daily\nenergy: 3\n<i class=\"g\">reading: true</i>\n<i class=\"g\">deep_work: true</i>\n<i class=\"d\">walk: false</i>\n<i class=\"d\">inbox: false</i>\n<i class=\"d\">---</i>\n\n# 2026-08-19\n\n## Daily targets\n\n| Target | Property | Weight |\n|---|---|---|\n| Deep work | `deep_work` | 9 |\n| Reading | `reading` | 6 |\n| Walk | `walk` | 2 |\n| Inbox triage | `inbox` | 1 |",
     "note": "mm ticked the box for you. Untick it and the habit comes back — your edit always wins."
    }
   ]
  }
 ]
};
