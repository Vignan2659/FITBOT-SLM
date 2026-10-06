"""Voice-over script for the FitBot launch film (scene id, lines). A line is (on-screen/caption text, spoken text or
None). Spoken text only differs where the voice needs help with pronunciation.

Facts only: no customers, statistics, accuracy numbers or medical claims.
"""

SCENES = [
    # id, lead-in seconds, lines, tail seconds
    ("intro", 2.2, [
        ("Veltris presents FitBot.", None),
    ], 1.6),
    ("problem", 0.5, [
        ("Fitness information is fragmented.", None),
        ("Workouts live in one app, nutrition in another, and advice on sleep and recovery is scattered everywhere "
         "else.", None),
    ], 0.8),
    ("identity", 0.6, [
        ("Meet FitBot: an AI assistant powered by a small language model, built specifically for fitness and "
         "wellness.", None),
        ("It understands your question, personalizes the answer, and recommends what to do next.", None),
    ], 1.0),
    ("exercises", 0.8, [
        ("Just ask in plain language.", None),
        ("FitBot responds with exercise cards: real images, target muscles, equipment, and difficulty, for strength, "
         "cardio, and stretching, at home or in the gym.", None),
    ], 1.0),
    ("personal", 0.5, [
        ("And it adapts to you.", None),
        ("Tell FitBot you're a beginner with dumbbells at home, and your level, goal, equipment, and environment "
         "shape a complete plan, with sets, reps, and rest for every day.", None),
    ], 1.2),
    ("nutrition", 0.6, [
        ("Nutrition answers use values from USDA FoodData Central: calories, protein, carbohydrates, fat, and fiber, "
         "instead of guesswork.",
         "Nutrition answers use values from U.S.D.A. Food Data Central: calories, protein, carbohydrates, fat, and "
         "fiber, instead of guesswork."),
        ("The same assistant also covers hydration, sleep, recovery, cardio, and weight loss.", None),
    ], 1.0),
    ("architecture", 0.6, [
        ("Behind the scenes, every question moves from the interface to intent understanding,", None),
        ("then to curated fitness and nutrition knowledge,", None),
        ("and finally to the domain-specific model, which writes a personalized response.", None),
    ], 0.9),
    ("training", 0.5, [
        ("The model itself was fine-tuned for this domain.", None),
        ("A curated fitness dataset was prepared, trained on a GPU, then validated and tested on held-out questions "
         "before reaching the application.", "A curated fitness dataset was prepared, trained on a G.P.U., then "
         "validated and tested on held-out questions, before reaching the application."),
    ], 1.0),
    ("experience", 0.5, [
        ("From the first question to saved plans and progress tracking, FitBot delivers a complete experience,", None),
        ("offering general fitness and wellness guidance, not medical diagnosis.", None),
    ], 1.0),
    ("outro", 0.6, [
        ("FitBot. Domain-specific AI, built for real-world fitness experiences.", None),
        ("Presented by Veltris.", None),
    ], 4.2),
]

LINE_GAP = 0.35   # pause between lines inside a scene
