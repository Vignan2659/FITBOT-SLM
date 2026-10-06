"""FitBot safety layer.

1. Pre-generation screening of the user message.
   * HARD categories (emergencies, self-harm, eating disorders, starvation, deliberate dehydration,
     performance-enhancing drugs, medication questions, injury diagnosis) get a fixed, reviewed
     guardrail response. These are guardrails, not the main AI: they guarantee consistent, safe
     wording for high-risk situations regardless of model output.
   * SOFT categories (pregnancy, chronic conditions) are answered by the SLM with safety context,
     and a professional referral + disclaimer is guaranteed.
2. Post-generation screening of the model output for unsafe advice.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

DISCLAIMER = ("FitBot provides general fitness and wellness information and is not a substitute "
              "for professional medical advice.")

REFERRAL_RE = re.compile(r"doctor|healthcare|health professional|physiotherapist|physical therapist|dietitian|"
                         r"pharmacist|emergency|mental health|obstetric|surgeon|medical", re.I)


@dataclass
class SafetyResult:
    category: str | None = None
    hard: bool = False
    response: str | None = None


HARD_RULES: list[tuple[str, re.Pattern, str]] = [
    ("self_harm", re.compile(r"\b(kill myself|suicid\w*|self[- ]harm|hurt myself|end my life|want to die|"
                             r"feel(ing)? (really )?hopeless|no reason to live)\b", re.I),
     "I'm really sorry you're feeling this way. You deserve support right now - please contact your local emergency "
     "number or a crisis line, or reach out to someone you trust. A doctor or mental health professional can help. "
     "If you are in immediate danger, call emergency services now."),
    ("emergency", re.compile(r"\b(chest (pain|pressure|tightness|hurts?)|my chest hurts|heart attack|"
                             r"can'?t breathe|cannot breathe|passed out|faint(ed|ing)|black(ed)? out|"
                             r"irregular heartbeat|heart (is )?racing.*(dizzy|faint)|numb(ness)? in my (arm|face))", re.I),
     "Please stop exercising and get medical help promptly. Chest pain or pressure, fainting, severe breathlessness or "
     "an irregular heartbeat during or after exercise need to be checked by a doctor before you train again. If symptoms "
     "are severe, spread to your arm, jaw or back, or come with sweating, nausea or dizziness, call emergency services "
     "right away."),
    ("eating_disorder", re.compile(r"\b(make myself (throw up|vomit|sick)|throw(ing)? up after (eating|meals?)|purg(e|ing)|"
                                   r"bulimi\w*|anorexi\w*|laxatives? (to|for) (lose|weight)|binge and (purge|vomit)|"
                                   r"eating disorder|exercise for hours to burn it off)\b", re.I),
     "Thank you for sharing this - it takes courage. What you describe can be a sign of disordered eating, and you "
     "deserve proper support. Please reach out to a doctor, a registered dietitian or a mental health professional, or "
     "an eating disorder helpline in your country. If you feel unsafe, contact emergency services. You don't have to "
     "deal with this alone."),
    ("starvation", re.compile(r"\b(starv\w+ (myself|to lose)|stop eating|not eat(ing)? (anything|for \d+)|eat nothing|"
                              r"only eat [1-7]\d\d calories|(eat|eating) ([1-7]\d\d|[1-9]\d) (k?cal|calories)|"
                              r"[1-7]\d\d calories a day|water fast(ing)? for \d+|skip (all|every) meals?)\b", re.I),
     "I can't recommend starving yourself or very low calorie intakes - they can cause muscle loss, nutrient "
     "deficiencies, dizziness and fatigue, and they are hard to sustain. A safer approach is a modest calorie deficit "
     "with plenty of protein, vegetables and whole foods, aiming for about 0.5-1 kg per week. If you're struggling with "
     "food or weight, please talk to a doctor or registered dietitian."),
    ("dehydration", re.compile(r"\b(dehydrat\w* (myself|yourself|to (lose|make|cut))|stop drinking water|"
                               r"cut(ting)? water|sweat (out|off) (the )?water|water cut|no water (before|for))\b", re.I),
     "I can't recommend deliberate dehydration - rapid water cutting can cause dizziness, kidney strain, heat illness "
     "and dangerous drops in performance. If you compete in a weight-class sport, please work with a qualified coach, "
     "sports dietitian or doctor on a safe, gradual plan."),
    ("peds", re.compile(r"\b(steroids?|anabolic|sarms?|clenbuterol|clen|dnp|trenbolone|tren|hgh|growth hormone|"
                        r"testosterone (cycle|injection)|cycle of (test|tren|deca)|ephedrine)\b", re.I),
     "I can't help with steroids, SARMs, clenbuterol, DNP or similar drugs. They carry serious health risks - including "
     "heart, liver and hormonal problems, and in DNP's case potentially fatal overheating - and many are illegal without "
     "a prescription. Safe progress comes from training, nutrition and sleep. If you are already using any of these, "
     "please speak to a doctor."),
    ("medication", re.compile(r"\b(medication|medicine|meds|prescription|antidepressants?|insulin|"
                              r"blood thinners?|painkillers?|ibuprofen|sleeping pills?)\b", re.I),
     "I can't give advice about medication, dosages or interactions. Please ask your doctor or pharmacist before "
     "combining any supplement, pre-workout or diet change with medication, or before taking medicine for pain or "
     "sleep. They can advise safely based on your health history."),
    ("injury_diagnosis", re.compile(r"\b(diagnos\w+|tore\b|torn (muscle|ligament|tendon|acl|mcl|meniscus|rotator)|tear(ed)? my|"
                                    r"(broke|broken) (my )?(bone|arm|leg|wrist|ankle|foot|hand|toe|finger|rib|nose)|"
                                    r"fractur\w+|sprain\w*|"
                                    r"dislocat\w+|swollen|swelling|sharp pain|shooting pain|pain (going|running|shooting) "
                                    r"down|numb(ness)?|tingling|popping sound|herniat\w+|hernia)\b", re.I),
     "I can't diagnose injuries, but sudden or sharp pain, swelling, numbness, weakness or a popping sensation should "
     "be assessed by a doctor or physiotherapist. Until then, stop the exercises that cause pain and protect the area. "
     "Get urgent care for severe pain, a visible deformity, or numbness with loss of strength or bladder control. A "
     "professional can guide a safe return to training."),
]

SOFT_RULES: list[tuple[str, re.Pattern]] = [
    ("pregnancy", re.compile(r"\b(pregnan\w*|postpartum|post-partum|trimester|breastfeeding)\b", re.I)),
    ("medical_condition", re.compile(r"\b(diabet\w*|heart (condition|disease|problem)|high blood pressure|hypertension|"
                                     r"asthma|kidney|liver disease|arthritis|osteoporosis|epilep\w*|cancer|"
                                     r"after (my )?surgery|recent surgery|operation)\b", re.I)),
]

UNSAFE_OUTPUT = [
    re.compile(r"\b(fast|stop eating|don'?t eat)\b[^.]{0,30}\bfor \d+ (days|weeks)\b", re.I),
    re.compile(r"\b(eat|consume|limit yourself to)\b[^.]{0,20}\b([1-7]\d\d) (k?cal|calories)( a| per)? day\b", re.I),
    re.compile(r"\bpush through (the )?(sharp |joint )?pain\b", re.I),
    re.compile(r"\bdehydrat\w* yourself\b", re.I),
    re.compile(r"\b\d+\s?mg (of )?(testosterone|trenbolone|clenbuterol|dnp)\b", re.I),
    re.compile(r"\bno need to (see|consult|visit) (a|your) (doctor|professional)\b", re.I),
]


def screen_input(text: str) -> SafetyResult:
    for category, pattern, response in HARD_RULES:
        if pattern.search(text):
            return SafetyResult(category, True, f"{response} {DISCLAIMER}")
    for category, pattern in SOFT_RULES:
        if pattern.search(text):
            return SafetyResult(category, False, None)
    return SafetyResult()


def screen_output(answer: str) -> bool:
    """True if the generated answer looks unsafe."""
    return any(p.search(answer) for p in UNSAFE_OUTPUT)


SAFE_FALLBACK = ("I want to keep this safe, so here is general guidance: progress gradually, eat balanced meals with "
                 "enough protein, stay hydrated, sleep 7+ hours and stop any exercise that causes sharp pain. For "
                 "anything related to symptoms, injuries or medical conditions, please talk to a qualified "
                 "healthcare professional.")


def ensure_referral(answer: str) -> str:
    if not REFERRAL_RE.search(answer):
        answer = answer.rstrip() + (" Because this involves a health condition, please check with your doctor or "
                                    "another qualified healthcare professional before changing your routine.")
    return answer


def with_disclaimer(answer: str) -> str:
    return answer if DISCLAIMER in answer else f"{answer.rstrip()} {DISCLAIMER}"
