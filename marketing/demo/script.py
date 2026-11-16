"""Voice-over for the FitBot demo film (marketing/demo). Each scene: id, design length of its animation in seconds,
lead-in before the voice, the lines (caption text, spoken text or None) and the tail after the voice. A scene lasts
exactly lead + voice + tail, and its animation is stretched to fit, so there is no dead air between topics.

Facts only: the numbers are measured (evaluation/training_run_4b/results.json, evaluation/test_suite_summary_4b.md)."""

SCENES = [
    ("intro", 7, 1.3, [("Veltris presents FitBot.", None)], 2.4),
    ("problem", 8, 0.4, [("Fitness advice is everywhere, but it's generic.", None),
                         ("The numbers are guessed, and nobody knows your level.", None)], 0.5),
    ("meet", 9, 0.5, [("Meet FitBot: an AI fitness coach, powered by a fine tuned, four billion parameter language model,",
                       None), ("running privately on your own Mac.", None)], 0.6),
    ("uses", 9, 0.4, [("One assistant for every part of your fitness:", None),
                      ("workouts, nutrition, yoga, sleep, hydration, recovery, and progress tracking.", None)], 0.5),
    ("chat", 12, 0.4, [("Just ask, in plain language.", None),
                       ("FitBot answers with real exercises from a library of 871, and the photos play every move in motion.",
                        "FitBot answers with real exercises from a library of eight hundred and seventy-one, and the photos "
                        "play every move in motion.")], 0.6),
    ("level", 12, 0.4, [("It trains at your level.", None),
                        ("Beginners get simple, stable movements. Advanced lifters get heavy compound lifts, with sets, "
                         "reps and rest for every day.", None)], 0.5),
    ("food", 9, 0.4, [("Nutrition answers use real USDA data: calories, protein, carbs and fat, with no guessing.",
                       "Nutrition answers use real U.S.D.A. data: calories, protein, carbs and fat, with no guessing.")], 0.6),
    ("yoga", 15, 0.5, [("There's a full yoga studio, too.", None),
                       ("34 poses shown by real people, and complete routines built for your time, your goal and your level.",
                        "Thirty-four poses shown by real people, and complete routines built for your time, your goal and "
                        "your level.")], 1.1),
    ("bands", 18, 0.4, [("Connect your fitness band: Apple Watch, Samsung, Fitbit, Huawei, OnePlus, Noise or WHOOP.",
                         "Connect your fitness band: Apple Watch, Samsung, Fitbit, Huawei, OnePlus, Noise, or Whoop."),
                        ("FitBot reads your steps, heart rate, sleep and stress, and coaches you with your own numbers.",
                         None)], 1.5),
    ("track", 8, 0.4, [("Save your plans, log your workouts, and watch your streak grow.", None)], 1.4),
    ("model", 16, 0.4, [("Under the hood is Qwen3 4B, fine tuned with QLoRA on 5,470 fitness conversations.",
                         "Under the hood is Qwen 3, four B, fine tuned with Q-LoRA on five thousand, four hundred and "
                         "seventy fitness conversations."),
                        ("Every question flows from intent understanding, to curated fitness knowledge, to the model, "
                         "which writes your answer.", None)], 0.6),
    ("results", 9, 0.4, [("And it's measured.", None),
                         ("FitBot's answers match the reference answers nearly three times more closely than the base "
                          "model.", None)], 0.7),
    ("safe", 9, 0.4, [("Risky questions get careful, safe answers, and your data never leaves your Mac.", None)], 0.6),
    ("why", 8, 0.4, [("It's not just another chatbot.", None), ("It's a specialist, built for your fitness.", None)], 0.6),
    ("end", 7, 0.7, [("FitBot. Train smarter.", None), ("Presented by Veltris.", None)], 3.0),
]
LINE_GAP = 0.28
