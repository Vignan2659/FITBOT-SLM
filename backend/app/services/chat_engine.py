"""FitBot chat pipeline.

User message
  -> safety screening (hard guardrails / soft flags)
  -> intent detection (+ out-of-domain guardrail) and slot extraction
  -> dialogue state update (follow-ups such as "I'm a beginner", "I only have dumbbells")
  -> structured retrieval (exercise cards, USDA food cards, workout planner) + semantic passage retrieval
  -> fine-tuned SLM generates the answer from the retrieved context, profile and recent history
  -> output safety check, referral/disclaimer
  -> structured response for the frontend
"""
from __future__ import annotations

import re
import time
from typing import Callable

from app.ml.prompting import build_messages, format_exercise, format_exercise_detail, format_food, format_passage
from app.ml.retriever import KnowledgeRetriever
from app.services import safety
from app.services.catalog import Catalog, exercise_card, food_card
from app.services.nlu import NLU, Slots
from app.services.planner import Planner, plan_to_context

OOD_MESSAGE = ("I'm focused on fitness, nutrition and wellness. Ask me something about workouts, exercise, food, "
               "recovery or healthy lifestyle.")
EXERCISE_INTENTS = {"exercise_search", "home_workout", "gym_workout"}
FOOD_INTENTS = {"food_search", "nutrition_question", "weight_loss", "hydration", "muscle_gain"}
FOLLOWUP_RE = re.compile(r"^\s*(what about|how about|and|what if|also|ok(ay)?|so|then|but)\b", re.I)
PLAN_RE = re.compile(r"\b(plan|program|programme|routine|schedule|split|week|days?)\b", re.I)
WORKOUT_RE = re.compile(r"\b(workout|work out|routine|session|circuit)\b", re.I)
GenerateFn = Callable[..., tuple[str, float]]
MODEL_REFUSAL_RE = re.compile(r"focused on fitness|only help with|outside what i can help", re.I)
# phrases blocked on the retry when the model wrongly refuses an in-domain question
REFUSAL_PHRASES = ["I'm focused", " I'm focused", "focused on fitness", "Sorry, that's outside"]


class ChatEngine:
    def __init__(self, catalog: Catalog, nlu: NLU, retriever: KnowledgeRetriever, generate: GenerateFn,
                 history_turns: int = 1):
        self.catalog, self.nlu, self.retriever, self.generate = catalog, nlu, retriever, generate
        self.planner = Planner(catalog.exercises)
        self.retriever_by_id = {p["id"]: p for p in retriever.passages}
        self.history_turns = history_turns

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _effective(slots: Slots, state: dict, profile: dict | None, is_followup: bool) -> dict:
        profile = profile or {}
        eq = slots.equipment or state.get("equipment") or profile.get("equipment") or []
        if isinstance(eq, str):
            eq = [eq]
        if slots.location == "gym" and not slots.equipment:
            eq = ["gym"]          # "...gym workout" overrides remembered home equipment
        elif slots.location == "home" and not slots.equipment and "gym" in eq:
            eq = []
        return {
            # the topic (muscle group) carries over only on genuine follow-ups; constraints persist
            "muscle_group": slots.muscle_group or (state.get("muscle_group") if is_followup else None),
            "level": slots.level or state.get("level") or profile.get("fitness_level"),
            "equipment": eq,
            "location": slots.location or state.get("location") or profile.get("location"),
            "goal": slots.goal or state.get("goal") or profile.get("goal"),
            "days": slots.days or state.get("days"),
            "diet": slots.diet or state.get("diet") or profile.get("dietary_preference"),
        }

    def _resolve_intent(self, message: str, intent: str, slots: Slots, state: dict) -> tuple[str, bool]:
        prev = state.get("intent")
        if not prev or prev in ("out_of_domain", "greeting", "medical_safety"):
            return intent, False
        short = len(message.split()) <= 9
        explicit_request = bool(PLAN_RE.search(message) or WORKOUT_RE.search(message) or slots.days)
        plan_context = prev in ("workout_plan", "home_workout", "gym_workout")
        if slots.constraint_only() and short and (not explicit_request or plan_context):
            # "I'm a beginner", "I only have dumbbells", "make it a home workout" (after a plan)
            return prev, True
        if FOLLOWUP_RE.match(message) and short and not slots.foods and intent not in ("out_of_domain",):
            # "what about legs?" keeps the exercise context; "what about chicken?" is handled by food slots
            if slots.muscle_group and prev in EXERCISE_INTENTS | {"workout_plan"}:
                return prev, True
        if intent == "out_of_domain" and short and slots.constraint_only():
            return prev, True
        if intent == "out_of_domain" and short and self._ood_prob < 0.5:
            # no fitness vocabulary, but the classifier is not confident it is off-topic and the conversation
            # is about fitness (e.g. "I only get 5 hours, is that bad?" after a sleep question)
            return prev, True
        return intent, False

    # ------------------------------------------------------------------ main entry
    def respond(self, message: str, history: list[dict], state: dict | None, profile: dict | None) -> tuple[dict, dict]:
        t0 = time.time()
        state = dict(state or {})
        message = message.strip()
        result = {"answer": "", "category": "general_fitness", "intent": "general_fitness", "intent_confidence": 0.0,
                  "exercises": [], "foods": [], "workout_plan": None, "sources": [], "safety": None,
                  "is_followup": False, "model": {}}

        # 1. safety screening
        sres = safety.screen_input(message)
        if sres.hard:
            result.update(answer=sres.response, category="medical_safety", intent="medical_safety",
                          intent_confidence=1.0, safety={"category": sres.category, "guardrail": True,
                                                         "disclaimer": safety.DISCLAIMER})
            result["model"] = {"generated": False, "reason": "safety guardrail", "total_seconds": round(time.time() - t0, 3)}
            state.update(intent="medical_safety")
            return result, state

        # 2. intent + slots
        intent, conf, top = self.nlu.classify(message)
        self._ood_prob = self.nlu.ood_probability(message)
        slots = self.nlu.slots(message)
        intent, is_followup = self._resolve_intent(message, intent, slots, state)
        if sres.category:  # soft medical flag (pregnancy, chronic condition)
            intent = "medical_safety"
        result.update(intent=intent, category=intent, intent_confidence=round(conf, 3), is_followup=is_followup,
                      intent_top=top)

        if intent == "out_of_domain":
            result["answer"] = OOD_MESSAGE
            result["model"] = {"generated": False, "reason": "out-of-domain guardrail",
                               "total_seconds": round(time.time() - t0, 3)}
            state["intent"] = "out_of_domain"
            return result, state

        eff = self._effective(slots, state, profile, is_followup)
        context: list[str] = []
        exercises: list[dict] = []
        foods: list[dict] = []
        plan = None

        # 3. structured retrieval
        wants_plan = intent == "workout_plan" or (intent in ("home_workout", "gym_workout") and PLAN_RE.search(message)
                                                   and not eff["muscle_group"])
        # "I only have dumbbells" after a goal-level question (weight loss, muscle gain, ...) -> a full plan
        if is_followup and (slots.equipment or slots.location) and not eff["muscle_group"] and \
                intent in ("weight_loss", "muscle_gain", "general_fitness", "cardio", "workout_plan", "home_workout", "gym_workout"):
            wants_plan = True
        if slots.exercises and intent in EXERCISE_INTENTS | {"exercise_safety", "general_fitness", "stretching", "cardio"} \
                and not wants_plan and not slots.muscle_group:
            exercises = slots.exercises[:2]
            context += [format_exercise_detail(e) for e in exercises]
        elif wants_plan:
            location = eff["location"] or ("home" if intent == "home_workout" else None)
            plan = self.planner.plan(level=eff["level"] or "beginner", days=eff["days"] or 3,
                                     goal=eff["goal"] or "general_fitness", equipment=eff["equipment"], location=location)
            context += plan_to_context(plan)
        elif intent in EXERCISE_INTENTS | {"cardio", "stretching"} or (is_followup and eff["muscle_group"]):
            group = eff["muscle_group"] or {"cardio": "cardio", "stretching": "stretching"}.get(intent)
            constraint_followup = is_followup and (slots.equipment or slots.location)
            if group and (constraint_followup or (WORKOUT_RE.search(message) and (eff["equipment"] or eff["location"]))) \
                    and group not in ("cardio", "stretching"):
                plan = self.planner.muscle_workout(group, level=eff["level"] or "beginner", goal=eff["goal"] or "muscle_gain",
                                                   equipment=eff["equipment"], location=eff["location"])
                context += plan_to_context(plan)
                names = [x["name"] for x in plan["days"][0]["exercises"]]
                exercises = [self.catalog.find_exercise(n) for n in names]
            elif group:
                exercises = self.catalog.exercises_for(group, eff["level"], eff["equipment"], eff["location"])
                context += [format_exercise(e) for e in exercises]

        if intent in FOOD_INTENTS or slots.foods or (intent == "medical_safety" and re.search(r"\beat|food|diet", message, re.I)):
            if slots.foods:
                foods = slots.foods[:4]
            elif intent != "muscle_gain" or re.search(r"\b(eat|food|protein|meal)\b", message, re.I):
                foods = self.catalog.foods_for_topic(message, diet=eff["diet"])
            context += [format_food(f) for f in foods]

        # sensitive (soft-flagged) topics always get the matching safety guidance first
        if sres.category:
            pids = {"pregnancy": ["pregnancy", "safety-start"], "medical_condition": ["safety-start", "pa-older"]}
            for pid in pids.get(sres.category, []):
                p = self.retriever_by_id.get(pid)
                if p:
                    context.append(format_passage(p))
                    result["sources"].append({"type": "guidance", "title": p["title"], "source": p["source"]})

        # 4. semantic guidance retrieval (skipped for pure food-fact lookups and plans)
        if not (slots.foods and intent == "food_search") and not plan:
            query = message
            if is_followup and history:
                last_user = next((h["content"] for h in reversed(history) if h["role"] == "user"), "")
                query = f"{last_user} {message}"
            passages = self.retriever.search(query, k=2, topic=intent)
            context += [format_passage(p) for p in passages]
            result["sources"] += [{"type": "guidance", "title": p["title"], "source": p["source"]} for p in passages]
        if foods:
            result["sources"].append({"type": "nutrition", "title": "USDA FoodData Central (SR Legacy)",
                                      "source": "https://fdc.nal.usda.gov/"})
        if exercises or plan:
            result["sources"].append({"type": "exercises", "title": "free-exercise-db (public domain)",
                                      "source": "https://github.com/yuhonas/free-exercise-db"})

        # 5. generation with the fine-tuned SLM
        prompt_profile = {"fitness_level": eff["level"], "goal": eff["goal"], "equipment": eff["equipment"],
                          "location": eff["location"], "dietary_preference": eff["diet"],
                          "age": (profile or {}).get("age")}
        window = history[-2 * self.history_turns:] if self.history_turns > 0 else []
        recent = [{"role": h["role"], "content": h["content"][:700]} for h in window]
        messages = build_messages(message, context, prompt_profile, recent)
        answer, gen_seconds = self.generate(messages)
        refusal_retry = False
        if MODEL_REFUSAL_RE.search(answer) and intent not in ("out_of_domain", "greeting"):
            # The request was classified in-domain (classifier + domain lexicon), but the SLM produced its
            # out-of-domain refusal. Regenerate once with the refusal phrases blocked.
            try:
                answer, extra_s = self.generate(messages, avoid=REFUSAL_PHRASES)
            except TypeError:  # generator without `avoid` support (e.g. test doubles)
                extra_s = 0.0
            gen_seconds += extra_s
            refusal_retry = True
        answer = answer.strip() or "Sorry, I couldn't generate an answer. Could you rephrase your question?"

        # 6. output safety
        flagged = safety.screen_output(answer)
        if flagged:
            answer = safety.SAFE_FALLBACK
        if intent in ("medical_safety", "exercise_safety") or sres.category:
            if sres.category:
                answer = safety.ensure_referral(answer)
            answer = safety.with_disclaimer(answer)
            result["safety"] = {"category": sres.category or intent, "guardrail": False, "output_flagged": flagged,
                                "disclaimer": safety.DISCLAIMER}
        elif flagged:
            result["safety"] = {"category": "unsafe_output_replaced", "guardrail": True, "output_flagged": True,
                                "disclaimer": safety.DISCLAIMER}

        result.update(answer=answer,
                      exercises=[exercise_card(e) for e in exercises if e],
                      foods=[food_card(f) for f in foods],
                      workout_plan=plan,
                      context_used=context)
        result["model"] = {"generated": True, "refusal_retry": refusal_retry, "generation_seconds": round(gen_seconds, 3),
                           "total_seconds": round(time.time() - t0, 3)}

        # 7. new dialogue state
        state.update({k: v for k, v in eff.items() if v})
        state["muscle_group"] = eff["muscle_group"]   # cleared when the topic changes
        state["intent"] = intent
        if slots.foods:
            state["last_foods"] = [f["name"] for f in slots.foods]
        return result, state
