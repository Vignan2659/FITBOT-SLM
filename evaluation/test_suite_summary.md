# FitBot test-suite results

Model: `/Users/vignankarthikeya/Downloads/FITBOT SLM/FitBot/models/fitbot-smollm2-360m-lora/merged` (fine-tuned: True, device: mps)

| Suite | Questions | Pass rate | Avg latency (s) | Weakest check |
|---|---:|---:|---:|---|
| fitness_questions | 50 | 76% | 1.42 | intent (78%) |
| nutrition_questions | 20 | 100% | 1.38 | food_cards (100%) |
| exercise_questions | 20 | 100% | 1.72 | exercise_cards (100%) |
| sleep_recovery_questions | 10 | 90% | 1.21 | intent (90%) |
| safety_questions | 10 | 100% | 0.24 | disclaimer_and_referral (100%) |
| out_of_domain_questions | 10 | 100% | 0.02 | intent (100%) |
| followup_conversations | 43 | 98% | 2.21 | relevance_keyword (98%) |

Per-check pass rates:

* **fitness_questions**: intent 78%, no_false_refusal 100%, non_empty 100%, relevance_keyword 98%
* **nutrition_questions**: food_cards 100%, intent 100%, no_false_refusal 100%, non_empty 100%, relevance_keyword 100%, usda_numbers_grounded 100%
* **exercise_questions**: exercise_cards 100%, intent 100%, level 100%, muscle_group 100%, no_false_refusal 100%, non_empty 100%, plan_days 100%, relevance_keyword 100%, workout_plan 100%
* **sleep_recovery_questions**: intent 90%, no_false_refusal 100%, non_empty 100%, relevance_keyword 100%
* **safety_questions**: disclaimer_and_referral 100%, guardrail 100%, intent 100%, non_empty 100%, relevance_keyword 100%
* **out_of_domain_questions**: intent 100%, non_empty 100%, ood_refusal 100%, relevance_keyword 100%
* **followup_conversations**: exercise_cards 100%, followup_detected 100%, food_cards 100%, guardrail 100%, intent 100%, level 100%, muscle_group 100%, no_false_refusal 100%, non_empty 100%, ood_refusal 100%, plan_days 100%, relevance_keyword 98%, workout_plan 100%

## Failed questions (14)

* [fitness_questions] **Is it okay to work out every day?** → intent `sleep`; failed: intent
* [fitness_questions] **What is progressive overload?** → intent `exercise_search`; failed: intent
* [fitness_questions] **How do I lose fat but keep muscle?** → intent `muscle_gain`; failed: relevance_keyword
* [fitness_questions] **What's the best time of day to exercise?** → intent `exercise_search`; failed: intent
* [fitness_questions] **How much exercise do adults need per week?** → intent `workout_plan`; failed: intent
* [fitness_questions] **Do I need a personal trainer?** → intent `nutrition_question`; failed: intent
* [fitness_questions] **How can I improve my posture?** → intent `cardio`; failed: intent
* [fitness_questions] **Is it bad to skip leg day?** → intent `general_fitness`; failed: intent
* [fitness_questions] **What are the benefits of strength training?** → intent `nutrition_question`; failed: intent
* [fitness_questions] **How do I get fit fast?** → intent `muscle_gain`; failed: intent
* [fitness_questions] **Is swimming a good workout?** → intent `exercise_search`; failed: intent
* [fitness_questions] **How do I avoid getting injured at the gym?** → intent `gym_workout`; failed: intent
* [sleep_recovery_questions] **Is it bad to exercise before bed?** → intent `exercise_search`; failed: intent
* [followup_conversations] **I'm a beginner with no equipment.** → intent `cardio`; failed: relevance_keyword
