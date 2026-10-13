# FitBot v2 – launch film script

Duration: 2:23.8 · 1920×1080 · 30 fps · voice: Kokoro neural TTS (af_heart), with macOS voices as fallback

Output: `marketing/FitBot_v2_Launch.mp4` (1080p) and `marketing/FitBot_v2_Launch_small.mp4` (720p). Re-render with `marketing/launch/make_film.command` (about 15 minutes).

All product content on screen is real FitBot output (answers, exercise cards, workout plan, USDA food values, app screenshots). Every number is measured (`evaluation/training_run_4b/results.json`, `evaluation/test_suite_summary_4b.md`). No customers, testimonials or medical claims.

## 0:00.0 – 0:05.3  Veltris logo reveal
* **0:02.2** Veltris presents FitBot.

## 0:05.3 – 0:15.1  The problem: fragmented fitness information
* **0:05.8** Fitness information is fragmented.
* **0:08.1** Workouts live in one app, nutrition in another, and advice on sleep and recovery is scattered everywhere else.

## 0:15.1 – 0:29.9  FitBot identity
* **0:15.7** Meet FitBot: a fitness assistant powered by a fine tuned, four-billion-parameter language model that runs privately, right on your Mac.
* **0:24.0** It understands your question, personalizes the answer, and recommends what to do next.

## 0:29.9 – 0:44.9  Demo: exercise cards (871 exercises)
* **0:30.7** Just ask in plain language.
* **0:32.5** FitBot answers with exercise cards from a library of 871 exercises: real images, target muscles, equipment, and difficulty, at home or in the gym.

## 0:44.9 – 0:57.4  Personalization: workout plan
* **0:45.4** And it adapts to you.
* **0:46.7** Tell FitBot you're a beginner with dumbbells at home, and your level, goal, equipment, and environment shape a complete plan, with sets, reps, and rest for every day.

## 0:57.4 – 1:13.6  Nutrition (USDA)
* **0:58.0** Nutrition answers use values from USDA FoodData Central: calories, protein, carbohydrates, fat, and fiber, instead of guesswork.
* **1:07.4** The same assistant also covers hydration, sleep, recovery, cardio, and weight loss.

## 1:13.6 – 1:27.0  How it works
* **1:14.2** Behind the scenes, every question moves from the interface to intent understanding,
* **1:19.0** then to curated fitness and nutrition knowledge,
* **1:21.9** and finally to the domain-tuned model, which writes a personalized response.

## 1:27.0 – 1:43.6  Dataset → QLoRA fine tuning → validation → testing
* **1:27.5** The model is Qwen3 4B, fine tuned for this domain.
* **1:31.4** 5,470 conversations were prepared, trained with QLoRA on a GPU, then validated and tested on held out questions before reaching the application.

## 1:43.6 – 2:00.9  Measured results
* **1:44.1** And the results are measurable.
* **1:45.9** Its answers match the reference answers nearly three times more closely than the base model.
* **1:51.4** Across 163 real app checks, FitBot gets 93% right, and politely declines every off topic question.

## 2:00.9 – 2:12.6  The complete experience
* **2:01.4** From the first question to saved plans and progress tracking, FitBot delivers a complete experience,
* **2:07.4** offering general fitness and wellness guidance, not medical diagnosis.

## 2:12.6 – 2:23.8  Closing: FitBot × Veltris
* **2:13.2** FitBot. Domain specific AI, built for real world fitness experiences.
* **2:18.2** Presented by Veltris.
