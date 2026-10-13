# FitBot test-suite results

Model: `models/fitbot-smollm2-360m-lora/merged` (fine-tuned: True, device: mps)

| Suite | Questions | Pass rate | Avg latency (s) | Weakest check |
|---|---:|---:|---:|---|
| fitness_questions | 50 | 76% | 0.95 | intent (80%) |
| nutrition_questions | 20 | 100% | 0.99 | food_cards (100%) |
| exercise_questions | 20 | 100% | 1.18 | exercise_cards (100%) |
| sleep_recovery_questions | 10 | 100% | 0.83 | intent (100%) |
| safety_questions | 10 | 100% | 0.16 | disclaimer_and_referral (100%) |
| out_of_domain_questions | 10 | 100% | 0.02 | intent (100%) |
| followup_conversations | 43 | 98% | 1.08 | relevance_keyword (98%) |

Per-check pass rates:

* **fitness_questions**: intent 80%, no_false_refusal 100%, non_empty 100%, relevance_keyword 94%
* **nutrition_questions**: food_cards 100%, intent 100%, no_false_refusal 100%, non_empty 100%, relevance_keyword 100%, usda_numbers_grounded 100%
* **exercise_questions**: exercise_cards 100%, intent 100%, level 100%, muscle_group 100%, no_false_refusal 100%, non_empty 100%, plan_days 100%, relevance_keyword 100%, workout_plan 100%
* **sleep_recovery_questions**: intent 100%, no_false_refusal 100%, non_empty 100%, relevance_keyword 100%
* **safety_questions**: disclaimer_and_referral 100%, guardrail 100%, intent 100%, non_empty 100%, relevance_keyword 100%
* **out_of_domain_questions**: intent 100%, non_empty 100%, ood_refusal 100%, relevance_keyword 100%
* **followup_conversations**: exercise_cards 100%, followup_detected 100%, food_cards 100%, guardrail 100%, intent 100%, level 100%, muscle_group 100%, no_false_refusal 100%, non_empty 100%, ood_refusal 100%, plan_days 100%, relevance_keyword 98%, workout_plan 100%

## Failed questions (13)

* [fitness_questions] **Is it okay to work out every day?** → intent `general_fitness`; failed: relevance_keyword
* [fitness_questions] **What is progressive overload?** → intent `general_fitness`; failed: intent
* [fitness_questions] **How do I lose fat but keep muscle?** → intent `weight_loss`; failed: relevance_keyword
* [fitness_questions] **How much exercise do adults need per week?** → intent `workout_plan`; failed: intent
* [fitness_questions] **Are machines safe for beginners?** → intent `equipment`; failed: intent
* [fitness_questions] **How do I avoid shin splints when running?** → intent `medical_safety`; failed: intent, relevance_keyword
* [fitness_questions] **Can I train abs every day?** → intent `workout_plan`; failed: intent
* [fitness_questions] **Do I need a personal trainer?** → intent `equipment`; failed: intent
* [fitness_questions] **Is it bad to skip leg day?** → intent `general_fitness`; failed: intent
* [fitness_questions] **What are the benefits of strength training?** → intent `nutrition_question`; failed: intent
* [fitness_questions] **How do I get fit fast?** → intent `medical_safety`; failed: intent
* [fitness_questions] **Is swimming a good workout?** → intent `hydration`; failed: intent
* [followup_conversations] **I'm a beginner with no equipment.** → intent `cardio`; failed: relevance_keyword
