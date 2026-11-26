# Demo Day: Plant-care App — speaker notes

> Fictional sample talk. Every `##` heading is one section; the panel pages through them
> and auto-follows the projected tab using `notes_rules` in the config.

**Before you start:** projector on, blank screen on (F9), source window picked (F7).

## 1. Intro — who we are and the problem

- Hook: "Raise your hand if you have ever killed a houseplant." *(pause)*
- Problem: watering is guesswork; plants die from too much water more often than too little.
- Team: three people, one weekend, two soil sensors.
- Say what they will see: the code, the data, the live app.

> Slide cue: switch from the title slide to the problem slide.

## 2. Demo A — code walkthrough

- Open the repository page. Show the folder layout first, not the code.
- `sensor/reader.py`: reads moisture every 10 minutes, smooths with a rolling average.
- `app/reminders.py`: one rule — remind when moisture stays below 30 % for 6 hours.
- Tests: run them once on screen; point at the green bar.

**If the network is slow:** show the screenshot in the backup folder instead.

## 3. Demo B — watering data

- Open the spreadsheet with two weeks of readings.
- Point at the saw-tooth: each spike is a watering.
- The chart: moisture vs. days; the dashed line is the 30 % threshold.
- What we learned: most plants were watered *too often*.

| Plant | Waterings | Suggested |
|---|---|---|
| Fern | 9 | 6 |
| Cactus | 4 | 1 |

## 4. Demo C — the live app

1. Add a plant: name, species, pot size.
2. Trigger a reminder with the "simulate dry soil" button.
3. Show offline mode: turn Wi-Fi off, add a reading, turn it back on, watch it sync.

- Keep the pointer still while talking; click ripples show where you click.
- Press F8 to freeze the projector before typing anything private.

## 5. Q&A

- Repeat each question before answering.
- Likely questions:
  - *Which sensors?* Two capacitive soil sensors, about the price of a coffee each.
  - *Does it work for outdoor plants?* Not yet; rain breaks the model.
  - *Is the data shared?* No, it stays on the device unless you export it.

## 6. Wrap-up — next steps and thanks

- Roadmap: more species, weather data, a shared household mode.
- Thank the organisers and the audience.
- Last slide: repository link and a feedback form.
- Press F9 for the blank screen while people leave.
