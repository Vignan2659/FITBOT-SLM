"""Voice-over script for the FitBot launch film (scene id, lines). A line is (on-screen/caption text, spoken text or
None). Spoken text only differs where the voice needs help with pronunciation or numbers.

Facts only: every number is measured (evaluation/training_run_4b/results.json, evaluation/test_suite_summary_4b*.md).
No customers, testimonials or medical claims.
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
        ("Meet FitBot: a fitness assistant powered by a fine-tuned, four-billion-parameter language model that runs "
         "privately, right on your Mac.", None),
        ("It understands your question, personalizes the answer, and recommends what to do next.", None),
    ], 1.0),
    ("exercises", 0.8, [
        ("Just ask in plain language.", None),
        ("FitBot answers with exercise cards from a library of 871 exercises: real images, target muscles, equipment, "
         "and difficulty, at home or in the gym.",
         "FitBot answers with exercise cards from a library of eight hundred and seventy-one exercises: real images, "
         "target muscles, equipment, and difficulty, at home or in the gym."),
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
        ("and finally to the domain-tuned model, which writes a personalized response.", None),
    ], 0.9),
    ("training", 0.5, [
        ("The model is Qwen3 4B, fine-tuned for this domain.", "The model is Qwen 3, four B, fine-tuned for this domain."),
        ("5,470 conversations were prepared, trained with QLoRA on a GPU, then validated and tested on held-out "
         "questions before reaching the application.",
         "Five thousand, four hundred and seventy conversations were prepared, trained with Q-LoRA on a G.P.U., then "
         "validated and tested on held-out questions, before reaching the application."),
    ], 1.0),
    ("results", 0.5, [
        ("And the results are measurable.", None),
        ("Its answers match the reference answers nearly three times more closely than the base model.", None),
        ("Across 163 real app checks, FitBot gets 93% right, and politely declines every off-topic question.",
         "Across one hundred and sixty-three real app checks, FitBot gets ninety-three percent right, and politely "
         "declines every off-topic question."),
    ], 1.2),
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
