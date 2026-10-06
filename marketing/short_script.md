# FitBot explainer — voiceover script

Voice: macOS **Samantha** (American English), 190 words/min.
Total length: 119 s (2.0 min).

## 1. Intro
*Visual: card*

> Meet FitBot: an AI fitness coach powered by a small language model that runs on your own computer.

## 2. Chest — *Exercise cards with images*
*Visual: footage*

> Ask what exercises to do for chest, and you get exercise cards with real photos, target muscles, equipment, and difficulty.

## 3. Followups — *Follow-up conversations*
*Visual: footage*

> It follows the conversation.
> Say you're a beginner, or that you only have dumbbells, and it builds a matching workout with sets, reps, and rest.

## 4. Food — *Real nutrition data*
*Visual: footage*

> Nutrition answers use exact values from the USDA FoodData Central database, so the numbers are never made up.

## 5. Plan — *Workout plans*
*Visual: footage*

> Ask for a beginner three-day gym workout, and FitBot lays out every day, with exercises, sets, reps, and images, in seconds.

## 6. Arch
*Visual: sequence — arch3, arch5*

> Under the hood, every message passes a safety screen, then an intent classifier, then retrieval of real exercise and food facts.
> Finally, the fine-tuned model writes the answer, which is checked again before it reaches you.

## 7. Code
*Visual: sequence — code_prompt, code_safety*

> One shared prompt builder formats both the training data and live requests, so the model always sees what it learned.
> And high-risk messages, like chest pain or extreme dieting, are handled by clear safety rules, not by the model.

## 8. Model
*Visual: sequence — model_card, training*

> The model is SmolLM2 360M Instruct, fine-tuned with LoRA on a Google Colab T4 GPU in under eight minutes.
> Validation loss fell from 1.71 to 0.89.

## 9. Stack
*Visual: card*

> It's built with React and Vite, FastAPI and SQLite, and PyTorch with Hugging Face Transformers and PEFT.

## 10. Ux — *UI and UX*
*Visual: footage*

> Your profile personalizes suggestions, and every card expands into step-by-step instructions.

## 11. Safety — *Safe and on topic*
*Visual: footage*

> It stays safe and on topic: chest pain gets a doctor referral, and off-topic questions are politely declined.

## 12. Results
*Visual: card*

> On unseen questions, perplexity dropped from 5.06 to 2.45, and 91 percent of 163 end-to-end chat turns passed.

## 13. Outro
*Visual: card*

> FitBot. Your AI fitness coach. Train smarter.
> FitBot provides general fitness information and is not a substitute for professional medical advice.

