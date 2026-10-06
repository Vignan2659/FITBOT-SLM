import { fireEvent, render, screen } from "@testing-library/react";
import ExerciseCard from "../components/ExerciseCard.jsx";
import FoodCard from "../components/FoodCard.jsx";
import Message from "../components/Message.jsx";
import WorkoutPlan from "../components/WorkoutPlan.jsx";

const bench = {
  name: "Bench Press", slug: "bench-press", muscle_group: "chest",
  image_url: "https://raw.githubusercontent.com/yuhonas/free-exercise-db/main/exercises/Barbell_Bench_Press_-_Medium_Grip/0.jpg",
  image_urls: [], target_muscles: ["Chest"], secondary_muscles: ["Shoulders", "Triceps"], equipment: "Barbell",
  difficulty: "Intermediate", description: "A compound pressing movement.",
  instructions: ["Lie back on a flat bench.", "Lower the bar to mid-chest."], safety_tips: ["Use a spotter."],
};
const egg = {
  name: "Egg (whole, hard-boiled)", fdc_id: 173424, group: "protein", highlights: ["High protein"],
  portion: { description: "1 large", grams: 50 },
  nutrients: { calories_kcal: 77.5, protein_g: 6.3, carbs_g: 0.6, fat_g: 5.3, fiber_g: 0, sugar_g: 0.6, sodium_mg: 62 },
  source_url: "https://fdc.nal.usda.gov/food-details/173424/nutrients",
};

test("exercise card shows image, name, target, equipment, difficulty and toggles instructions", () => {
  render(<ExerciseCard exercise={bench} />);
  expect(screen.getByRole("img", { name: /bench press/i })).toHaveAttribute("src", bench.image_url);
  expect(screen.getByText("Bench Press")).toBeInTheDocument();
  expect(screen.getByText("Chest • Shoulders • Triceps")).toBeInTheDocument();
  expect(screen.getByText("Barbell")).toBeInTheDocument();
  expect(screen.getByText("Intermediate")).toBeInTheDocument();
  expect(screen.queryByText(/use a spotter/i)).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: /view instructions/i }));
  expect(screen.getByText("Lower the bar to mid-chest.")).toBeInTheDocument();
  expect(screen.getByText(/use a spotter/i)).toBeInTheDocument();
});

test("food card shows USDA values and source link", () => {
  render(<FoodCard food={egg} />);
  expect(screen.getByText("1 large (50 g)")).toBeInTheDocument();
  expect(screen.getByText("6.3 g")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: /USDA FoodData Central #173424/ })).toHaveAttribute("href", egg.source_url);
});

test("workout plan switches between days", () => {
  const plan = { title: "Beginner 2-day gym plan", level: "Beginner", split: "Full-body", equipment: "gym", notes: [],
    days: [
      { day: "Day 1", focus: "Full body A", exercises: [{ name: "Goblet Squat", sets: "2-3", reps: "10-12", rest: "60-90 sec", difficulty: "Beginner", target_muscles: ["Quadriceps"], image_url: "x.jpg" }] },
      { day: "Day 2", focus: "Full body B", exercises: [{ name: "Lat Pulldown", sets: "2-3", reps: "10-12", rest: "60-90 sec", difficulty: "Beginner", target_muscles: ["Lats"], image_url: "y.jpg" }] },
    ] };
  render(<WorkoutPlan plan={plan} />);
  expect(screen.getByText("Goblet Squat")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("tab", { name: "Day 2" }));
  expect(screen.getByText("Lat Pulldown")).toBeInTheDocument();
  expect(screen.getByText("2-3 × 10-12")).toBeInTheDocument();
});

test("bot message renders answer text and structured cards", () => {
  const msg = { id: 1, role: "assistant", intent: "exercise_search", content: "Here are some chest exercises.",
    payload: { exercises: [bench], foods: [egg], sources: [{ title: "USDA FoodData Central (SR Legacy)" }] } };
  render(<Message msg={msg} />);
  expect(screen.getByText("Here are some chest exercises.")).toBeInTheDocument();
  expect(screen.getByText("Exercises")).toBeInTheDocument();
  expect(screen.getByText("Bench Press")).toBeInTheDocument();
  expect(screen.getByText("Egg (whole, hard-boiled)")).toBeInTheDocument();
});
