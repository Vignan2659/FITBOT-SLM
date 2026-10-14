# FitBot v2 – launch film script

Duration: 2:28.8 · 1920×1080 · 30 fps · voice: Kokoro-82M neural TTS, female blend of af_bella (60%) and af_sarah (40%)

Output: `marketing/FitBot_v2_Launch.mp4` (1080p) and `marketing/FitBot_v2_Launch_small.mp4` (720p). Re-render with `marketing/launch/make_film.command` (about 15 minutes).

All product content on screen is real FitBot output (answers, exercise cards, workout plan, USDA food values, app screenshots). Every number is measured (`evaluation/training_run_4b/results.json`, `evaluation/test_suite_summary_4b.md`). No customers, testimonials or medical claims.

## 0:00.0 – 0:05.4  Veltris logo reveal
* **0:02.2** Veltris presents FitBot.

## 0:05.4 – 0:15.4  The problem: fragmented fitness information
* **0:05.9** Fitness information is fragmented.
* **0:08.2** Workouts live in one app, nutrition in another, and advice on sleep and recovery is scattered everywhere else.

## 0:15.4 – 0:31.0  FitBot identity
* **0:16.0** Meet FitBot: a fitness assistant powered by a fine tuned, four-billion-parameter language model that runs privately, right on your Mac.
* **0:24.9** It understands your question, personalizes the answer, and recommends what to do next.

## 0:31.0 – 0:46.6  Demo: exercise cards (871 exercises)
* **0:31.8** Just ask in plain language.
* **0:33.8** FitBot answers with exercise cards from a library of 871 exercises: real images, target muscles, equipment, and difficulty, at home or in the gym.

## 0:46.6 – 0:59.4  Personalization: workout plan
* **0:47.1** And it adapts to you.
* **0:48.5** Tell FitBot you're a beginner with dumbbells at home, and your level, goal, equipment, and environment shape a complete plan, with sets, reps, and rest for every day.

## 0:59.4 – 1:15.8  Nutrition (USDA)
* **0:60.0** Nutrition answers use values from USDA FoodData Central: calories, protein, carbohydrates, fat, and fiber, instead of guesswork.
* **1:09.5** The same assistant also covers hydration, sleep, recovery, cardio, and weight loss.

## 1:15.8 – 1:30.0  How it works
* **1:16.4** Behind the scenes, every question moves from the interface to intent understanding,
* **1:21.5** then to curated fitness and nutrition knowledge,
* **1:24.5** and finally to the domain-tuned model, which writes a personalized response.

## 1:30.0 – 1:47.3  Dataset → QLoRA fine tuning → validation → testing
* **1:30.5** The model is Qwen3 4B, fine tuned for this domain.
* **1:34.7** 5,470 conversations were prepared, trained with QLoRA on a GPU, then validated and tested on held out questions before reaching the application.

## 1:47.3 – 2:04.9  Measured results
* **1:47.8** And the results are measurable.
* **1:49.6** Its answers match the reference answers nearly three times more closely than the base model.
* **1:54.9** Across 163 real app checks, FitBot gets 93% right, and politely declines every off topic question.

## 2:04.9 – 2:17.2  The complete experience
* **2:05.4** From the first question to saved plans and progress tracking, FitBot delivers a complete experience,
* **2:11.8** offering general fitness and wellness guidance, not medical diagnosis.

## 2:17.2 – 2:28.8  Closing: FitBot × Veltris
* **2:17.8** FitBot. Domain specific AI, built for real world fitness experiences.
* **2:23.3** Presented by Veltris.
