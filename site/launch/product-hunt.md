# mm — Product Hunt launch kit

Everything to copy on launch day, plus the reasoning behind each choice so you
can rewrite any of it in your own voice. Asset specs verified against Product
Hunt's posting guide and help centre, August 2026.

Assets are generated: `python3 site/tools/make-gallery.py` rewrites
`launch/gallery/*.png` and `launch/thumbnail-240.png` from the same captured CLI
output the website uses, so a launch image can never show something the tool
does not actually print. Re-run it if the demo or the copy changes.

---

## 1. The fields

### Name (40 char limit)

```
mm
```

Just the name. No emoji, no descriptor — Product Hunt strips those. A two-letter
name is a real risk in a feed full of "AI-powered" everything, which is exactly
why the tagline has to do all the work.

### Tagline (60 char limit)

**Recommended:**

```
A terminal to-do list that shows you one task at a time
```

55 characters. It names the category (to-do list), the medium (terminal), and
the one mechanism that makes it different, in that order. Someone scrolling
knows in one read whether this is for them, which is the only job this line has.

**Alternates**, if you want more edge:

| Tagline | Chars | Trade-off |
|---|---|---|
| `The to-do list that hides everything but one task` | 49 | More intriguing, slightly less concrete |
| `A CLI to-do list that blocks the easy tasks` | 43 | Leads with the gate; assumes "CLI" is understood |
| `Never choose what to work on again` | 34 | Best line, but it never says what the product is |

Do not use the fourth one on Product Hunt. It works as a headline on your own
site, where the terminal demo is right underneath explaining the rest. In a feed
it is just a slogan.

### Description (260 char limit)

```
mm answers one question — what now — with exactly one task. Mark what
matters as a gate and mm won't offer you anything easier until it's done.
Interrupts preempt, then unwind. Habits sync both ways with your Obsidian
daily note. Zero dependencies, MIT.
```

253 characters. Product Hunt's own docs disagree about this limit — the launch
guide says 500, the help centre says 260 — so this stays under the smaller one.

### Launch tags (up to 3)

```
Productivity   ·   Task Management   ·   Developer Tools
```

Swap **Developer Tools** for **Open Source** if you would rather be found by
people who filter for licence over language. Do not add a third loosely-related
tag to widen reach; tag pages send small, well-matched traffic and a bad match
just costs you the impression.

### Links

- Website: `https://mm.tafil.app`
- Repository: `https://github.com/Toseef-Ahmad/mm`
- Documentation: `https://mm.tafil.app/docs`

---

## 2. Media

| Asset | Spec | File |
|---|---|---|
| Thumbnail | 240×240, under 3 MB | `launch/thumbnail-240.png` |
| Gallery 1 | 1270×760 | `launch/gallery/01-one-task.png` |
| Gallery 2 | 1270×760 | `launch/gallery/02-gates.png` |
| Gallery 3 | 1270×760 | `launch/gallery/03-interrupts.png` |
| Gallery 4 | 1270×760 | `launch/gallery/04-obsidian.png` |
| Gallery 5 | 1270×760 | `launch/gallery/05-open-source.png` |

Upload in that order. The first gallery image becomes the preview card wherever
your listing gets shared, so it carries the promise; two through four each prove
one mechanism; five removes the "what's the catch" objection.

**Optional but worth it:** a 20–40 second screen recording of a real session —
`mm`, do the thing, `mm done`, gate closes. Product Hunt accepts a YouTube URL
only, and it must not be private. Do not narrate the philosophy; just let the
terminal run.

---

## 3. The maker's first comment

Post this yourself, within a minute of going live. It is the most-read block of
text on the page after the tagline, and a launch without one reads abandoned.

```
Hi Product Hunt 👋

I built mm because my problem was never remembering what to do. It was
opening a perfectly good to-do list, seeing eleven things, and picking the
easiest one. Every app I tried answered "what have I got?" — and that
question always has a comfortable answer.

So mm only answers "what now", with exactly one task.

The part that actually changed my days is gates. You mark the work that
matters as a gate, and while it is open mm refuses to hand you anything
else. Not a red label. Not a nag. The easy task is still in the list,
greyed out and marked gate-locked, and the tool simply will not offer it.
You can always override it — mm done <id> closes anything — but you have to
type that, on purpose. Turns out that is the whole difference.

Two other things I use every day:

→ Interrupts go on a stack that unwinds. Something urgent preempts
  everything, and closing it puts you back on the exact task you left,
  rather than quietly replacing it.
→ Habits sync both ways with my Obsidian daily note. I tick "reading" in
  Obsidian, it leaves the queue with the streak credited. I run mm done, the
  box ticks itself.

It is Python 3.11+, zero dependencies, MIT, and everything lives in ~/.mm as
plain files. No account, no server, no telemetry — there is no network code
in it at all.

What it is not: there is no GUI and no phone app, no due dates and no
reminders. If you need those, a normal to-do app is genuinely the better
tool and I would rather you keep using it.

I would love to hear where gates break for you — especially the day you
override one, and why. That is the feedback I cannot get from my own usage.
```

Then pin the install line as a follow-up reply:

```
pipx install git+https://github.com/Toseef-Ahmad/mm.git
```

---

## 4. Reply bank

Answer everything within the first four hours. Comment velocity matters more
than any single reply, and the first hours set the day's ranking.

**"How is this different from Taskwarrior / todo.txt?"**
> They are better task databases than mm will ever be — real query languages,
> dates, recurrence, huge ecosystems. But they will still show you forty rows
> and let you pick. mm shows one, and while a gate is open it will not offer the
> alternatives. Narrower on purpose.

**"This is just a to-do list with extra steps."**
> Fair, with one difference: every other list is a place to keep work, and mm is
> a thing that starts it. The whole design is about deleting the moment where
> you choose, because that moment is where my days used to go.

**"What stops me from just overriding the gate?"**
> Nothing, and that is deliberate. `mm done <id>` closes anything. A tool that
> locked me out of my own machine would have lasted a week. What the gate
> changes is that skipping becomes something you type on purpose instead of the
> default result of glancing at a list.

**"No GUI? No mobile?"**
> No, and it is not on the roadmap. It is one command in a terminal you already
> have open. If you are not in a terminal all day this is honestly not for you.

**"Why 'mm'?"**
> It is two keystrokes. You type it thirty times a day, so it had to cost
> nothing. It is short for MyMover.

**"Does it work on Windows?"**
> Untested — CI covers macOS and Linux only, so I will not claim it. The core is
> portable Python and the file locking degrades gracefully, so it may well work.
> WSL definitely does.

**"Where does my data go?"**
> Nowhere. `~/.mm`, plain JSON and TOML. There is no network code in the tool.

**"Can I use it without Obsidian?"**
> Yes — sync is off until you add an `[obsidian]` block. Most of mm has nothing
> to do with Obsidian.

---

## 5. Timing and the run-up

Product Hunt days start at **12:01 AM Pacific** and run 24 hours. Everyone
posted that day competes with you, and the ranking rewards early engagement, so
being live at the start of the window matters more than the hour you are awake.

**Tuesday, Wednesday or Thursday.** Weekends are quiet in both directions —
less competition, but far fewer people. Monday and Friday are noisy.

### Two weeks before

- [ ] Create your Product Hunt account if you do not have one, and use it — a
      brand-new account posting on day one looks exactly like what it is.
      Comment on other launches, follow makers in your space.
- [ ] Have someone try a cold install from the README on a clean machine, and
      watch them without helping. Every stumble is a launch-day comment.

### One week before

- [ ] Regenerate assets: `python3 site/tools/make-gallery.py`
- [ ] Re-record the demo and redeploy if the CLI has changed:
      `python3 site/tools/capture.py && cd site && vercel --prod --yes`
- [ ] Tag a release so the repo's front page shows a version, not just commits.
- [ ] Create the draft on Product Hunt and schedule it.
- [ ] Line up the two or three people who will genuinely try it that morning.
      Not vote-beggars — users. Asking for upvotes violates Product Hunt's rules
      and gets launches removed.

### The day before

- [ ] Deploy the site and click through it on a phone.
- [ ] Check `pipx install git+…` works from a clean shell.
- [ ] Write the first comment into a draft so you are pasting, not composing.
- [ ] Sleep. Being awake at 3am refreshing a leaderboard helps nothing.

### Launch day

- [ ] Post the first comment immediately.
- [ ] Reply to everything for the first four hours.
- [ ] Post to the other places below, staggered across the day — not all at once.
- [ ] File the good criticism as GitHub issues while the thread is live, and say
      you have done it. It is the most convincing thing a maker can do.

---

## 6. Where else to post

A Product Hunt launch does not carry itself, and for a terminal tool these are
often better traffic than PH:

| Where | Notes |
|---|---|
| **Show HN** | `Show HN: mm – a terminal to-do list that shows you one task at a time`. Post the site, link the repo in the first comment. Same day or the day after. |
| **r/commandline** | Exactly the audience. Lead with the terminal, not the philosophy. |
| **r/ObsidianMD** | Lead with the two-way daily-note sync; the CLI is secondary there. |
| **r/productivity** | Lead with the choosing problem. Expect "just use paper" — engage anyway. |
| **Lobsters** | Only if you have an account with history. Tag `unix`, `practices`. |
| **Hacker News comment sections** | On any procrastination or task-manager thread. Contribute, do not drop links. |

One rule for all of them: never post the same paragraph twice. Each community
cares about a different part of this tool, and the copy-paste is always obvious.

---

## 7. What actually counts as success

For a zero-dependency CLI with a two-letter name, a top-five finish is not the
goal and chasing it will make you write worse copy. The things that compound:

- People who install it and are still running it in a month.
- Issues from strangers. The first one is a milestone.
- One good blog post or newsletter mention — worth more than 200 upvotes.
- GitHub stars, as a lagging signal that the pitch landed.

The launch is a day. The docs, the landing page and the tool are what keep
working afterwards, and those are already done.
