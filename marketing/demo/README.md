# FitBot 2 minute demo film

Everything on screen comes from the real app: answers from the fine tuned model, the exercise and yoga photos,
the band data page and screenshots of the web app. The music is synthesised in code and the voice is the Kokoro
neural voice (af_heart), so there is nothing to license.

1. On the Mac, with FitBot set up: double click `make_assets.command` (real answers, screenshots, voice-over).
   `collect.command` redoes only the answers and screenshots.
2. Copy `build/` to a work folder together with the `assets/` (screenshots, exercise photos, yoga photos, grain)
   and run, in this folder:

```bash
python timeline.py WORK/vo WORK          # places the voice lines on the storyboard
python music_demo.py WORK                # original 120 BPM score, ducked under the voice
python build_demo.py WORK --stills 12,40 # preview frames
python build_demo.py WORK                # renders each scene, joins them, adds the sound
```

The storyboard and the spoken lines are in `script.py`, the animation in `stage.html` (`render(t)` draws any
moment of the film).
