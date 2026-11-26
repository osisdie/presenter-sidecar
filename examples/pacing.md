# Pacing — Demo Day: Plant-care App

A fictional 60-minute talk used to demonstrate the panel timers. The panel reads the
schedule lines and the breakdown table below; everything else in this file is ignored.

## Schedule

Format: `<HH:MM or +H:MM>  <Short>: <title>  (<N>m)`. The `<Short>` name becomes the
timer button and is matched (case-insensitive) against the `##` headings of the notes.

```text
14:00  Intro: who we are and the problem       (8m)
+0:08  Demo A: code walkthrough on GitHub      (12m)
+0:20  Demo B: watering data in a spreadsheet  (10m)
+0:30  Demo C: the live app                    (15m)
+0:45  Q&A: questions from the room            (10m)
+0:55  Wrap-up: next steps and thanks          (5m)
15:00  END
```

## Breakdown

Format: `| <Short> (<N>m) | <breakdown> |`. Shown under the running timer.

| Section | Breakdown |
|---|---|
| Intro (8m) | Hook 2｜Problem 3｜Team 3 |
| Demo A (12m) | Repo tour 4｜Sensor code 5｜Tests 3 |
| Demo B (10m) | Raw readings 4｜Chart 3｜What we learned 3 |
| Demo C (15m) | Add a plant 5｜Reminder flow 5｜Offline mode 5 |
| Q&A (10m) | Open floor 10 |
| Wrap-up (5m) | Roadmap 2｜Thanks 1｜Links 2 |
