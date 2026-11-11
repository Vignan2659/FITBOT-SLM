import { fireEvent, render, screen } from "@testing-library/react";
import ExerciseCard from "../components/ExerciseCard.jsx";
import FoodCard from "../components/FoodCard.jsx";
import Message from "../components/Message.jsx";
import WorkoutPlan, { planDayEntries } from "../components/WorkoutPlan.jsx";
import { MemoryRouter } from "react-router-dom";
import YogaCard from "../components/YogaCard.jsx";
import YogaRoutine from "../components/YogaRoutine.jsx";
import BandCard, { bandTiles } from "../components/BandCard.jsx";
import { parseHeartRate, sessionStats } from "../hooks/useHeartRate.js";

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

test("plan day becomes log entries with the planned dose as a note", () => {
  const day = { day: "Day 1", exercises: [{ name: "Goblet Squat", sets: "2-3", reps: "10-12" }, { name: "Plank", sets: "2-3", reps: "20-40 sec" }] };
  expect(planDayEntries(day, "2026-10-06")).toEqual([
    { day: "2026-10-06", exercise: "Goblet Squat", notes: "Day 1: 2-3 × 10-12" },
    { day: "2026-10-06", exercise: "Plank", notes: "Day 1: 2-3 × 20-40 sec" },
  ]);
});

test("plan action buttons appear only when enabled", () => {
  const plan = { title: "P", days: [{ day: "Day 1", focus: "F", exercises: [] }] };
  const { rerender } = render(<WorkoutPlan plan={plan} />);
  expect(screen.queryByRole("button", { name: /save plan/i })).not.toBeInTheDocument();
  rerender(<WorkoutPlan plan={plan} saveable onLogged={() => {}} />);
  expect(screen.getByRole("button", { name: /save plan/i })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /log day 1 as done/i })).toBeInTheDocument();
});

// ------------------------------------------------------------------ yoga

const warrior = {
  slug: "warrior-ii", name: "Warrior II", sanskrit: "Virabhadrasana II", difficulty: "Beginner", sides: true,
  category: ["Strength", "Flexibility", "Weight management", "Mobility"], duration: "30 seconds to 1 minute each side",
  image: "/yoga/photos/warrior-ii-1.jpg", image_urls: ["/yoga/photos/warrior-ii-1.jpg"],
};
const routine = {
  title: "15-Minute Beginner Yoga", minutes: 15, level: "Beginner", notes: ["Move slowly."],
  steps: [{ order: 1, slug: "mountain-pose", name: "Mountain Pose", phase: "Centre", duration: "1 min", difficulty: "Beginner",
            image: "/yoga/photos/thumb/mountain-pose-1.jpg", cue: "Stand tall." },
          { order: 2, slug: "warrior-ii", name: "Warrior II", phase: "Standing", duration: "1 min each side", difficulty: "Beginner",
            image: "/yoga/photos/thumb/warrior-ii-1.jpg", cue: "Bend the front knee." }],
};

test("yoga card shows a real photo, level, categories and links to the pose page", () => {
  render(<MemoryRouter><YogaCard pose={warrior} /></MemoryRouter>);
  expect(screen.getByRole("img", { name: /warrior ii/i })).toHaveAttribute("src", "/yoga/photos/thumb/warrior-ii-1.jpg");
  expect(screen.getByText("Beginner")).toBeInTheDocument();
  expect(screen.getByText("Both sides")).toBeInTheDocument();
  expect(screen.getByText("Strength • Flexibility • Weight management")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: /view pose/i })).toHaveAttribute("href", "/yoga/warrior-ii");
});

test("yoga routine lists timed steps linking to each pose", () => {
  render(<MemoryRouter><YogaRoutine routine={routine} /></MemoryRouter>);
  expect(screen.getByText("15-Minute Beginner Yoga")).toBeInTheDocument();
  expect(screen.getByText("1 min each side")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: /2\. Warrior II/ })).toHaveAttribute("href", "/yoga/warrior-ii");
  expect(screen.getByRole("button", { name: /log as done/i })).toBeInTheDocument();
});

test("chat message renders yoga cards and a yoga routine from the payload", () => {
  const msg = { id: 9, role: "assistant", content: "Here you go.", intent: "yoga",
                payload: { yoga_poses: [warrior], yoga_routine: routine, sources: [] } };
  render(<MemoryRouter><Message msg={msg} /></MemoryRouter>);
  expect(screen.getByText("Yoga")).toBeInTheDocument();
  expect(screen.getByText("15-Minute Beginner Yoga")).toBeInTheDocument();
  expect(screen.getAllByText("Warrior II").length).toBeGreaterThan(0);
});

test("band card shows the day's numbers and links to the Bands page", () => {
  const band = { day: "2026-11-10", is_today: false, steps: 9321, distance_km: 6.4, resting_hr: 58, avg_hr: 74, sleep_minutes: 388,
    stress: 72, stress_estimated: true, hrv_ms: 51 };
  render(<MemoryRouter><BandCard band={band} /></MemoryRouter>);
  expect(screen.getByText("9,321")).toBeInTheDocument();
  expect(screen.getByText("6.4 km")).toBeInTheDocument();
  expect(screen.getByText("58 bpm")).toBeInTheDocument();
  expect(screen.getByText("6 h 28 min")).toBeInTheDocument();
  expect(screen.getByText("under 7 hours")).toBeInTheDocument();
  expect(screen.getByText("72 / 100")).toBeInTheDocument();
  expect(screen.getByText("high · estimated")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: /open bands/i })).toHaveAttribute("href", "/bands");
  expect(bandTiles({ day: "2026-11-10" })).toEqual([]);
});

test("bot message shows the band card when the answer used band data", () => {
  const msg = { id: 9, role: "assistant", intent: "sleep", content: "You slept 6 hours 28 minutes.",
    payload: { category: "band", band: { day: "2026-11-10", is_today: true, steps: 4000, sleep_minutes: 388 }, sources: [{ title: "Your fitness band data" }] } };
  render(<MemoryRouter><Message msg={msg} /></MemoryRouter>);
  expect(screen.getByText("Your band")).toBeInTheDocument();
  expect(screen.getByText("4,000")).toBeInTheDocument();
  expect(screen.getByText(/From your band · Today/)).toBeInTheDocument();
});

test("heart rate measurement is read in both 8 and 16 bit form", () => {
  expect(parseHeartRate(new DataView(new Uint8Array([0x00, 72]).buffer))).toBe(72);
  expect(parseHeartRate(new DataView(new Uint8Array([0x01, 0x2c, 0x01]).buffer))).toBe(300);
  expect(sessionStats([{ bpm: 100 }, { bpm: 140 }, { bpm: 120 }])).toEqual({ avg: 120, max: 140, min: 100 });
  expect(sessionStats([])).toEqual({ avg: null, max: null, min: null });
});
