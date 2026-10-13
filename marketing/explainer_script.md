# FitBot explainer, voiceover script

Voice: macOS **Samantha** (American English), 190 words/min.
Total length: 310 s (5.2 min).

## 1. Intro
*Visual: card*

> Meet FitBot: a fitness coach powered by a small language model that runs on your own computer.
> In the next few minutes, you'll see what it can do, and exactly how it works under the hood.

## 2. What
*Visual: card*

> FitBot answers questions about workouts, exercises, nutrition, hydration, sleep, and recovery.
> It shows real exercise photos and real nutrition facts, and it builds personalized workout plans.
> And it needs no paid cloud AI service. Everything runs locally.

## 3. Dashboard, *The dashboard*
*Visual: footage*

> Everything starts on the dashboard, with quick-start prompts, your profile, and an exercise explorer.
> Fifty-eight exercises, each with real public-domain photos.

## 4. Chest, *Exercise cards with images*
*Visual: footage*

> Ask: what exercises can I do for chest?
> FitBot replies with a short answer and interactive exercise cards: target muscles, equipment, difficulty, instructions, and a safety tip.

## 5. Followups, *Follow up conversations*
*Visual: footage*

> It understands follow-ups.
> Say, I'm a beginner, and the cards switch to beginner-friendly moves.
> Say, I only have dumbbells, and it builds a dumbbell workout with sets, reps, and rest times.

## 6. Food, *Real nutrition data*
*Visual: footage*

> Ask what to eat after the workout, and you get nutrition cards with calories, protein, carbs, and fat.
> Every number comes straight from the U.S.D.A.'s FoodData Central database. FitBot never makes up nutrient values.

## 7. Plan, *Workout plans*
*Visual: footage*

> Need a full program? Ask for a beginner three-day gym workout.
> FitBot lays out every day, with exercises, sets, reps, rest, and images, in seconds.

## 8. Arch
*Visual: sequence, arch0, arch1, arch2, arch3, arch4, arch5*

> So, how does it work? Every message travels through a pipeline.
> First, a safety screen checks for high-risk situations.
> Next, an intent classifier and slot extractor work out what you're asking, and remember context from earlier turns.
> Then retrieval gathers real facts: exercises, foods, a workout plan, and expert guidance passages.
> The fine tuned language model writes the answer from those facts.
> Finally, the answer is checked again for safety and sent to the app, with cards and plans attached.

## 9. Code Prompt
*Visual: sequence, code_prompt, code_prompt*

> Here's the heart of it: the prompt builder.
> The same function formats the training data and every live request, so the model always sees the format it learned: the system prompt, your profile, retrieved reference facts, recent history, and your question.

## 10. Code Safety
*Visual: sequence, code_safety, code_safety*

> High-risk messages never depend on the model.
> Clear rules catch things like chest pain, extreme dieting, or steroid questions, and return a reviewed safe response that points you to a professional.

## 11. Code Nlu
*Visual: sequence, code_nlu, code_retriever*

> Intent detection combines a T F I D F and logistic regression classifier from scikit-learn with a fitness vocabulary check, so off topic questions are politely declined.
> For general guidance, Sentence Transformers embeddings find the most relevant passages in a curated knowledge base.

## 12. Model
*Visual: sequence, model_card, code_lora*

> The language model is SmolLM2 360M Instruct: an open, Apache-licensed model with 362 million parameters, small enough to run on a laptop.
> We fine tuned it with LoRA, using Hugging Face PEFT and Transformers, training just 8.7 million parameters, or 2.3 percent of the model.

## 13. Training
*Visual: card*

> Training ran in a Google Colab notebook on a Tesla T4 GPU, in under eight minutes.
> Validation loss fell steadily from 1.71 for the base model to 0.89, with no sign of overfitting.

## 14. Data
*Visual: card*

> The data matters just as much.
> Exercises and photos come from the public-domain free exercise database, and nutrition from USDA SR Legacy.
> 916 conversation examples were written and grounded in those sources, then split into training, validation, and test sets with no overlap.

## 15. Backend
*Visual: sequence, code_chat, code_models*

> The backend is built with FastAPI and SQLAlchemy, on SQLite.
> Passwords are hashed with bcrypt, sessions use JWT tokens that are revoked on logout, and every user can only see their own conversations.

## 16. Frontend Code
*Visual: sequence, code_card*

> The interface is built with React and Vite. Each answer renders structured components, like this exercise card.

## 17. Ux, *UI and UX*
*Visual: footage*

> Signing up takes seconds.
> Your profile stores your level, goal, diet, and equipment, so suggestions are personalized.
> And every exercise card expands to show step by step instructions and a safety tip.

## 18. Mobile, *Works on any screen*
*Visual: mobile*

> The design is dark-mode friendly and fully responsive, so FitBot works just as well on a phone.

## 19. Safety, *Safe and on topic*
*Visual: footage*

> It stays safe and on topic.
> Mention chest pain, and it tells you to stop and get medical help.
> Ask about geography, and it politely steers you back to fitness.

## 20. Results
*Visual: card*

> The results speak for themselves.
> On unseen test questions, perplexity dropped from 5.06 to 2.45, and answers became nearly three times closer to the expert references.
> In end to end testing, 91 percent of 163 chat turns passed, with every safety and off topic case handled correctly.

## 21. Stack
*Visual: card*

> The stack: React, Vite, FastAPI, SQLAlchemy, SQLite, PyTorch, Hugging Face Transformers, PEFT, Sentence Transformers, and scikit-learn.
> All open source, and all running on your own machine.

## 22. Outro
*Visual: card*

> FitBot. Your AI fitness coach. Train smarter.
> FitBot provides general fitness and wellness information, and is not a substitute for professional medical advice.

