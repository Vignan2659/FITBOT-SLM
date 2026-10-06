import ExerciseCard from "./ExerciseCard.jsx";
import FoodCard from "./FoodCard.jsx";
import WorkoutPlan from "./WorkoutPlan.jsx";
import { IconDumbbell, IconShield } from "./Icons.jsx";

const INTENT_LABEL = {
  exercise_search: "Exercises", workout_plan: "Workout plan", nutrition_question: "Nutrition", food_search: "Food",
  weight_loss: "Weight loss", muscle_gain: "Muscle gain", cardio: "Cardio", hydration: "Hydration", sleep: "Sleep",
  recovery: "Recovery", stretching: "Stretching", home_workout: "Home workout", gym_workout: "Gym workout",
  equipment: "Equipment", exercise_safety: "Exercise safety", general_fitness: "General fitness",
  medical_safety: "Health & safety", greeting: "Hello", out_of_domain: "Out of scope",
};

// Renders plain text with paragraphs and simple numbered / bulleted lines.
function RichText({ text }) {
  const blocks = text.split(/\n{2,}/);
  return blocks.map((b, i) => {
    const lines = b.split("\n").filter(Boolean);
    if (lines.length > 1 && lines.every((l) => /^\s*(\d+[.)]|[-*•])\s+/.test(l))) {
      return <ul key={i} className="rt-list">{lines.map((l, j) => <li key={j}>{l.replace(/^\s*(\d+[.)]|[-*•])\s+/, "")}</li>)}</ul>;
    }
    return <p key={i}>{lines.join(" ")}</p>;
  });
}

export default function Message({ msg }) {
  if (msg.role === "user") {
    return <div className="msg msg-user"><div className="bubble">{msg.content}</div></div>;
  }
  const p = msg.payload || {};
  const exercises = p.exercises || [];
  const foods = p.foods || [];
  const intent = msg.intent || p.category;
  return (
    <div className="msg msg-bot">
      <div className="bot-avatar" aria-hidden><IconDumbbell width={16} height={16} /></div>
      <div className="bot-content">
        <div className="bot-tags">
          {intent && <span className={`tag tag-${intent}`}>{INTENT_LABEL[intent] || intent}</span>}
          {p.is_followup && <span className="tag tag-soft">Follow-up</span>}
          {p.safety && <span className="tag tag-safety"><IconShield width={12} height={12} /> Safety</span>}
        </div>
        <div className="bubble bubble-bot"><RichText text={msg.content} /></div>
        {p.workout_plan && <WorkoutPlan plan={p.workout_plan} />}
        {exercises.length > 0 && !p.workout_plan && (
          <div className="card-grid">{exercises.map((e) => <ExerciseCard key={e.slug || e.name} exercise={e} />)}</div>
        )}
        {exercises.length > 0 && p.workout_plan && p.workout_plan.days?.length === 1 && (
          <details className="more-cards">
            <summary>Exercise details ({exercises.length})</summary>
            <div className="card-grid">{exercises.map((e) => <ExerciseCard key={e.slug || e.name} exercise={e} />)}</div>
          </details>
        )}
        {foods.length > 0 && (
          <div className="card-grid food-grid">{foods.map((f) => <FoodCard key={f.fdc_id} food={f} />)}</div>
        )}
        {p.sources?.length > 0 && (
          <div className="sources">
            Sources: {p.sources.map((s, i) => <span key={i} className="src">{s.title}</span>)}
          </div>
        )}
      </div>
    </div>
  );
}
