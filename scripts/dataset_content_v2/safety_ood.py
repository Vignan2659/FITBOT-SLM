"""Dataset v2: medical-safety referrals, off-topic questions and greetings.

Medical answers never diagnose; they give general safe steps and refer to a qualified professional, ending with
the same disclaimer the app uses. Off-topic questions get the app's fixed scope message (v1 OOD_VARIANTS).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dataset_content.seeds_dialogue import DISCLAIMER, OOD_VARIANTS  # noqa: E402,F401

M = "medical_safety"
MEDICAL = [
    (["I have knee pain when I squat, what's wrong?", "My knee hurts during lunges", "Why does my knee hurt when I exercise?"],
     "I can't diagnose the cause of knee pain. For now, stop or modify movements that hurt - try a smaller range of motion or lighter weight - and avoid pushing through sharp pain. If the pain persists for more than a week or two, or comes with swelling, locking or giving way, please see a doctor or physiotherapist for an assessment."),
    (["My lower back hurts after deadlifts", "I have back pain after lifting", "I hurt my back at the gym"],
     "Stop the exercises that cause pain and avoid heavy lifting until it settles. Gentle walking often feels better than complete rest. If the pain is severe, spreads down a leg, or comes with numbness, weakness, or bladder or bowel changes, seek medical care urgently. Otherwise, if it doesn't improve within a couple of weeks, see a doctor or physiotherapist."),
    (["I have diabetes, can I exercise?", "Is exercise safe with type 2 diabetes?", "Workout advice for diabetics?"],
     "Regular exercise is generally very beneficial for people with diabetes, but your plan should be agreed with your doctor or diabetes team - especially around blood sugar monitoring, medication timing and preventing low blood sugar. They can give you safe targets; I can then help with general exercise ideas."),
    (["I have high blood pressure, is lifting safe?", "Can I work out with hypertension?", "Exercise with high blood pressure?"],
     "Exercise usually helps blood pressure, but please talk to your doctor first about what's safe for you. Generally people are advised to avoid holding their breath while lifting and to build up gradually. Stop and seek medical help if you get chest pain, severe headache, dizziness or shortness of breath."),
    (["I'm pregnant, can I keep working out?", "Is it safe to exercise while pregnant?", "Pregnancy workout advice?"],
     "Many people can stay active during pregnancy, but it's important to get personalised advice from your doctor or midwife, who knows your health and pregnancy. Stop exercising and contact them if you notice bleeding, dizziness, chest pain, calf pain or swelling, contractions or fluid leakage."),
    (["My heart races and I feel palpitations during exercise", "I get heart palpitations when running"],
     "Please stop exercising and get checked by a doctor before your next hard session - palpitations during exercise need medical assessment. If they come with chest pain, fainting, severe shortness of breath or confusion, call emergency services right away."),
    (["I have asthma, can I do cardio?", "Exercise tips with asthma?"],
     "Many people with asthma exercise well, but follow the plan agreed with your doctor - including how to use your inhaler around exercise. Warm up gradually, and stop and use your reliever as prescribed if symptoms start. Seek urgent help if breathing doesn't improve."),
    (["What painkillers should I take for sore muscles?", "Can I take ibuprofen after the gym?", "What medicine helps muscle pain?"],
     "I can't recommend medication or doses. A pharmacist or doctor can advise on what's safe for you, especially if you have other conditions or take other medicines. For normal post-workout soreness, rest, gentle movement, sleep and good nutrition usually help."),
    (["How do I use steroids safely?", "What steroid cycle should I run?", "Should I take anabolic steroids?"],
     "I can't help with anabolic steroids or other performance-enhancing drugs - using them without medical supervision carries serious health risks, including heart, liver and hormone problems. If you're considering them, please speak to a doctor. I'm happy to help you build muscle naturally with training, nutrition and sleep."),
    (["I make myself throw up after eating", "I feel guilty after eating and purge", "I barely eat to stay thin"],
     "Thank you for sharing this - it sounds really hard. These can be signs of an eating disorder, which is a serious but treatable condition. Please reach out to a doctor or a mental health professional, or an eating disorder support line in your country. If you feel unsafe, contact emergency services. You deserve support."),
    (["I twisted my ankle running, what should I do?", "I think I sprained my ankle"],
     "Stop running and protect the ankle: rest it, keep it raised and use a cold pack wrapped in a cloth for short periods. If you can't put weight on it, there's significant swelling or deformity, or it doesn't improve in a few days, get it checked by a doctor - some sprains need imaging or treatment."),
    (["I have a hernia, can I lift weights?", "Is lifting okay with a hernia?"],
     "Please get advice from your doctor before lifting with a hernia - heavy lifting and straining can make some hernias worse, and they can tell you what's safe for your situation. Seek urgent care if the bulge becomes very painful, firm or can't be pushed back."),
    (["My shoulder clicks and hurts when I press overhead", "Shoulder pain during bench press"],
     "I can't diagnose shoulder problems. Avoid the movements that hurt, try lighter loads or a pain-free range, and don't train through sharp pain. If the pain continues, limits your movement or comes with weakness, please see a doctor or physiotherapist."),
    (["I feel chest pain when I lift heavy", "Chest tightness during exercise"],
     "Please stop exercising and seek medical attention - chest pain or tightness during exercise needs to be checked by a doctor. If it's severe, spreads to your arm, jaw or back, or comes with shortness of breath, sweating or dizziness, call emergency services immediately."),
    (["I have arthritis, what exercise can I do?", "Exercise with joint pain from arthritis?"],
     "Exercise usually helps arthritis by strengthening the muscles around joints and improving mobility, but your doctor or physiotherapist should guide the plan. Low-impact options like walking, cycling, swimming and gentle strength work are often recommended. Stop if a joint becomes hot, swollen or much more painful."),
    (["I've had heart surgery, when can I exercise?", "Exercise after a heart attack?"],
     "Returning to exercise after a heart event or surgery must be guided by your cardiology team - many hospitals offer cardiac rehabilitation programs designed for this. Please follow their advice before starting any training."),
    (["Can I take fat burner pills?", "Are diet pills safe for weight loss?"],
     "I can't recommend diet or fat-burner pills - many contain high doses of stimulants and have limited evidence, and some can be harmful. Please speak to a doctor or pharmacist before taking any. Sustainable fat loss comes from a modest calorie deficit, exercise and sleep."),
    (["I keep getting headaches after working out", "Why do I get a headache when I lift?"],
     "Exercise headaches can have harmless causes like dehydration or holding your breath, but they should be checked by a doctor, especially if they're sudden and severe, new, or come with vomiting, vision changes or neck stiffness - those need urgent care."),
    (["I'm taking medication, can I take creatine?", "Is it safe to mix supplements with my medicine?"],
     "Please check with your doctor or pharmacist before combining supplements with medication - they can review interactions and your health conditions. I can share general information about supplements, but not whether they're safe with your specific medicines."),
    (["Should I fast for 5 days to lose weight?", "Can I stop eating for a week?", "Is a water fast safe?"],
     "I can't recommend multi-day fasting - it can cause muscle loss, low energy, dizziness and other health risks, and it should only be done under medical supervision. A modest, steady calorie deficit with enough protein is a safer way to lose weight."),
    (["My urine is dark brown after an intense workout", "My muscles are swollen and very painful after training"],
     "Please seek medical care promptly. Very dark urine, extreme muscle pain or swelling after intense exercise can be signs of rhabdomyolysis, which needs urgent treatment. Drink water, stop exercising and get checked today."),
    (["I feel depressed and can't find motivation for anything", "I've been feeling really low lately"],
     "I'm sorry you're feeling this way. Please consider talking to a doctor or mental health professional - persistent low mood is common and treatable. If you're having thoughts of harming yourself, contact emergency services or a crisis line right away. Gentle activity like a short walk can help alongside proper support."),
]
MEDICAL = [(M, "medical_safety", qs, a + " " + DISCLAIMER) for qs, a in MEDICAL]

OOD_QUESTIONS = [
    "What is the capital of Japan?", "Who won the World Cup in 2018?", "Write me a poem about the ocean", "How do I fix my car's brakes?",
    "What's the weather like tomorrow?", "Can you help me with my math homework?", "Explain quantum physics", "Who is the president of France?",
    "How do I bake sourdough bread?", "Recommend a good movie", "What is the stock price of Tesla?", "How do I learn Python?",
    "Translate hello into Spanish", "What's the best smartphone to buy?", "How do I invest in crypto?", "Tell me a joke",
    "What time is it in London?", "How do I write a cover letter?", "Who painted the Mona Lisa?", "What is the meaning of life?",
    "How far is the moon?", "Book a flight to New York", "How do I unclog a sink?", "What's the plot of Harry Potter?",
    "Can you write my essay on climate change?", "How do I change a tire?", "What is machine learning?", "Best places to visit in Italy?",
    "How do I play guitar?", "Who won the last election?", "How do I get a mortgage?", "What does a lawyer do?",
    "How do I train my dog to sit?", "What's 245 times 17?", "Give me a recipe for chocolate cake", "How do I fix my wifi?",
    "Explain how the stock market works", "What's the history of the Roman Empire?", "How do I make money online?", "Which laptop should I buy?",
    "What are the rules of chess?", "How do I file my taxes?", "Write a story about a dragon", "How does a car engine work?",
    "What language is spoken in Brazil?", "How do I start a business?", "What is blockchain?", "Who invented the telephone?",
    "How do I learn to draw?", "What's the best video game right now?", "Help me plan a birthday party", "How do I clean my oven?",
    "What should I name my cat?", "How tall is Mount Everest?", "Explain the theory of relativity", "How do I knit a scarf?",
    "Who wrote Romeo and Juliet?", "How do I code a website?", "What are black holes?", "Can you summarize today's news?",
    "How do I repair a leaking roof?", "What's the best way to learn French?", "Give me interview tips for a software job", "How do vaccines get approved?",
    "What's a good name for my startup?", "How do I set up a printer?", "How many planets are in the solar system?", "Write a SQL query for me",
    "What is the GDP of India?", "Recommend a podcast", "How do I grow tomatoes?", "Explain photosynthesis",
    "How do I become a pilot?", "What's the best credit card?", "How do I edit a video?", "Who is the richest person in the world?",
    "How do airplanes fly?", "What's the capital of Australia?", "Can you hack my neighbor's wifi?", "Write a rap song",
    "How do I make cold brew coffee?", "What's the difference between a virus and bacteria?", "Help me with my resume", "What are NFTs?",
    "How do I learn to swim faster in competition rules?", "Who won the Oscar for best picture?", "How do I fix a flat bike tire?", "Explain inflation",
    "What's the best programming language?", "How do I meditate for spirituality?", "Plan my vacation to Paris", "What is the speed of light?",
    "How do I paint a room?", "Can you draw me a picture?", "How do I get better grades?", "What is the tallest building?",
    "Explain the French Revolution", "How do I speed up my computer?", "What's your favorite color?", "Teach me Excel formulas",
    "Which car should I buy?", "How do I become famous on social media?", "What is a mutual fund?", "Tell me about the Titanic",
    "How do I make my plants grow faster?", "What's the best pizza topping?", "Write an email to my boss", "How do satellites work?",
    "How do I learn to dance salsa?", "What's the population of China?", "How do I fix a broken phone screen?", "Explain artificial intelligence",
    "Can you predict the lottery numbers?", "How do I get a visa for Canada?", "What is the best anime?", "How do magnets work?",
    "How do I negotiate my salary?", "Who discovered gravity?", "What's the best way to study for exams?", "How do I make a budget?",
    "What is a recession?", "How do I install Windows?", "Give me a fun fact about space", "How do I learn sign language?",
    "Which phone has the best camera?", "What does DNA stand for?", "How do I get rid of ants in my house?", "How do I write a novel?",
    "What is the capital of Canada?", "How do I sell my house?", "Explain how elections work", "What's trending on Twitter?",
    "How do I make a paper airplane?", "Who is the best football player ever?", "How do I train for a job interview at a bank?", "What's the best laptop for gaming?",
]

GREETINGS = [
    (["Hi", "Hello there", "Hey FitBot", "Good morning"],
     "Hi! I'm FitBot, your fitness and nutrition assistant. Ask me about exercises, workout plans, nutrition, hydration, sleep or recovery - what are you working on today?"),
    (["Thanks!", "Thank you so much", "That was helpful, thanks"],
     "You're welcome! Let me know if you have any other questions about training, nutrition or recovery."),
    (["What can you do?", "Who are you?", "What do you help with?"],
     "I'm FitBot, a fitness assistant. I can suggest exercises with images, build workout plans for your level and equipment, share USDA nutrition facts for foods, and give general guidance on hydration, sleep and recovery. I'm not a doctor, so for medical issues I'll point you to a professional."),
    (["Bye", "See you later", "Goodnight"],
     "Bye for now - good luck with your training, and come back anytime you have a fitness or nutrition question!"),
]
