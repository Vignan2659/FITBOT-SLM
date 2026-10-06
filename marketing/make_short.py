"""FitBot short explainer (< 3 minutes): same look, voice and assets as make_explainer.py, tighter script.

    .venv/bin/python marketing/make_short.py   ->  marketing/FitBot_short.mp4 + marketing/short_script.md
"""
import make_explainer as m

m.OUT_NAME, m.MD_NAME = "FitBot_short.mp4", "short_script.md"
m.MAX_SECONDS = 175          # hard stop: never produce a video of 3 minutes or more

m.SCRIPT = [
    ("intro", {"type": "card", "make": "intro"}, None, [
        ("Meet FitBot: an AI fitness coach powered by a small language model that runs on your own computer.", None)]),
    ("chest", {"type": "footage", "src": "demo", "segs": [("chest_start", "chest_end")]},
     "Exercise cards with images", [
        ("Ask what exercises to do for chest, and you get exercise cards with real photos, target muscles, "
         "equipment, and difficulty.", None)]),
    ("followups", {"type": "footage", "src": "demo", "segs": [("beginner_start", "beginner_end"),
                                                            ("dumbbell_start", "dumbbell_end")]},
     "Follow-up conversations", [
        ("It follows the conversation.", None),
        ("Say you're a beginner, or that you only have dumbbells, and it builds a matching workout with sets, reps, "
         "and rest.", None)]),
    ("food", {"type": "footage", "src": "demo", "segs": [("food_start", "food_end")]},
     "Real nutrition data", [
        ("Nutrition answers use exact values from the USDA FoodData Central database, so the numbers are never made up.",
         "Nutrition answers use exact values from the U S D A Food Data Central database, so the numbers are never "
         "made up.")]),
    ("plan", {"type": "footage", "src": "demo", "segs": [("plan_start", "plan_end")]},
     "Workout plans", [
        ("Ask for a beginner three-day gym workout, and FitBot lays out every day, with exercises, sets, reps, and "
         "images, in seconds.", None)]),
    ("arch", {"type": "sequence", "images": ["arch3", "arch5"]}, None, [
        ("Under the hood, every message passes a safety screen, then an intent classifier, then retrieval of real "
         "exercise and food facts.", None),
        ("Finally, the fine-tuned model writes the answer, which is checked again before it reaches you.", None)]),
    ("code", {"type": "sequence", "images": ["code_prompt", "code_safety"]}, None, [
        ("One shared prompt builder formats both the training data and live requests, so the model always sees what "
         "it learned.", None),
        ("And high-risk messages, like chest pain or extreme dieting, are handled by clear safety rules, not by the "
         "model.", None)]),
    ("model", {"type": "sequence", "images": ["model_card", "training"]}, None, [
        ("The model is SmolLM2 360M Instruct, fine-tuned with LoRA on a Google Colab T4 GPU in under eight minutes.",
         "The model is Smol L M 2, 360 M, Instruct, fine-tuned with Laura on a Google Colab T 4 GPU in under eight "
         "minutes."),
        ("Validation loss fell from 1.71 to 0.89.", "Validation loss fell from 1 point 7 1, to 0 point 8 9.")]),
    ("stack", {"type": "card", "make": "stack"}, None, [
        ("It's built with React and Vite, FastAPI and SQLite, and PyTorch with Hugging Face Transformers and PEFT.",
         "It's built with React and Veet, Fast A P I and S Q Lite, and Pie Torch with Hugging Face Transformers and "
         "peft.")]),
    ("ux", {"type": "footage", "src": "extras", "segs": [("profile_start", "profile_end"),
                                                       ("instructions_start", "instructions_end")]},
     "UI and UX", [
        ("Your profile personalizes suggestions, and every card expands into step-by-step instructions.", None)]),
    ("safety", {"type": "footage", "src": "demo", "segs": [("safety_start", "safety_end"), ("ood_start", "ood_end")]},
     "Safe and on topic", [
        ("It stays safe and on topic: chest pain gets a doctor referral, and off-topic questions are politely "
         "declined.", None)]),
    ("results", {"type": "card", "make": "results"}, None, [
        ("On unseen questions, perplexity dropped from 5.06 to 2.45, and 91 percent of 163 end-to-end chat turns "
         "passed.", "On unseen questions, perplexity dropped from 5 point 0 6, to 2 point 4 5, and 91 percent of "
                    "163 end-to-end chat turns passed.")]),
    ("outro", {"type": "card", "make": "outro"}, None, [
        ("FitBot. Your AI fitness coach. Train smarter.", None),
        ("FitBot provides general fitness information and is not a substitute for professional medical advice.",
         None)]),
]

if __name__ == "__main__":
    m.main()
