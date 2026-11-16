"""Voice-over for the 2 minute FitBot demo film (marketing/demo). Each scene: id, planned length in seconds (from
the storyboard), lead-in before the voice starts, and the lines (caption text, spoken text or None)."""

SCENES = [
    ("hook", 8, 1.6, [("What if your fitness coach lived right on your laptop?", None)]),
    ("problem", 10, 0.6, [("Most fitness advice is generic.", None),
                          ("Guessed calorie numbers, and no idea what level you're at.", None)]),
    ("meet", 10, 0.8, [("Meet FitBot.", None),
                       ("A fitness AI trained for one job, running privately on your own computer.", None)]),
    ("chat", 12, 0.6, [("Just ask.", None),
                       ("You get real exercises with real photos, and you can see every move in motion.", None)]),
    ("level", 12, 0.6, [("Beginner, intermediate or advanced, every plan matches you.", None),
                        ("Never too easy. Never too risky.", None)]),
    ("food", 10, 0.6, [("Nutrition answers come from real USDA data, so there's no guessing.",
                        "Nutrition answers come from real U.S.D.A. data, so there's no guessing.")]),
    ("yoga", 16, 0.8, [("There's yoga too.", None),
                       ("Every pose is shown by real people, and FitBot builds a full routine for your time, "
                        "your goal and your level.", None)]),
    ("bands", 18, 0.8, [("Connect your fitness band,", None),
                        ("and FitBot coaches you with your own steps, heart rate, sleep and stress.", None)]),
    ("safe", 10, 0.6, [("Risky questions get careful, safe answers.", None),
                       ("And your data never leaves your Mac.", None)]),
    ("why", 8, 0.5, [("It's not just another chatbot.", None), ("It's a specialist for your fitness.", None)]),
    ("end", 6, 0.6, [("FitBot. Train smarter.", None)]),
]
LINE_GAP = 0.3
