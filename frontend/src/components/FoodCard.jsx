import { useState } from "react";

const fmt = (v, unit) => (v === null || v === undefined ? "—" : `${Math.round(v * 10) / 10}${unit}`);

// FDA Daily Values for adults, 2,000 kcal reference diet (21 CFR 101.9).
const DV = {
  fat_g: 78, saturated_fat_g: 20, cholesterol_mg: 300, sodium_mg: 2300, carbs_g: 275, fiber_g: 28, protein_g: 50,
  vitamin_d_ug: 20, calcium_mg: 1300, iron_mg: 18, potassium_mg: 4700, vitamin_a_ug: 900, vitamin_c_mg: 90,
  magnesium_mg: 420, zinc_mg: 11, vitamin_b12_ug: 2.4,
};

const GROUP_EMOJI = {
  protein: "🍗", plant_protein: "🫘", dairy: "🥛", dairy_alternative: "🌱", grains: "🌾", starchy_vegetable: "🥔",
  snacks: "🥨", fruit: "🍎", vegetables: "🥦", fats: "🥑", treats: "🍩", beverages: "🥤",
};

// First matching keyword wins (order matters: "chocolate milk" before "milk", "pineapple" before "apple").
const FOOD_EMOJI = [
  ["egg", "🥚"], ["chicken", "🍗"], ["turkey", "🦃"], ["beef", "🥩"], ["steak", "🥩"], ["pork", "🥓"], ["shrimp", "🦐"],
  ["salmon", "🐟"], ["tuna", "🐟"], ["cod", "🐟"], ["tilapia", "🐟"], ["sardine", "🐟"], ["whey", "🥤"],
  ["tofu", "🥡"], ["edamame", "🫛"], ["chickpea", "🫘"], ["peas", "🫛"], ["hummus", "🧆"], ["bean", "🫘"], ["lentil", "🫘"],
  ["chocolate milk", "🍫"], ["yogurt", "🥣"], ["cottage", "🧀"], ["cheddar", "🧀"], ["mozzarella", "🧀"], ["pizza", "🍕"],
  ["milk chocolate", "🍫"], ["dark chocolate", "🍫"], ["cookie", "🍪"], ["ice cream", "🍨"], ["doughnut", "🍩"],
  ["milk", "🥛"], ["oats", "🥣"], ["rice cake", "🍘"], ["rice", "🍚"], ["quinoa", "🌾"], ["couscous", "🌾"],
  ["bagel", "🥯"], ["bread", "🍞"], ["tortilla", "🫓"], ["pasta", "🍝"], ["sweet potato", "🍠"], ["chips", "🥔"],
  ["fries", "🍟"], ["potato", "🥔"], ["popcorn", "🍿"], ["corn", "🌽"], ["banana", "🍌"], ["apple juice", "🧃"], ["pineapple", "🍍"],
  ["orange juice", "🧃"], ["apple", "🍎"], ["orange", "🍊"], ["blueberr", "🫐"], ["strawberr", "🍓"], ["grape", "🍇"],
  ["mango", "🥭"], ["watermelon", "🍉"], ["pear", "🍐"], ["kiwi", "🥝"], ["cherr", "🍒"],
  ["date", "🌴"], ["raisin", "🍇"], ["broccoli", "🥦"], ["spinach", "🥬"], ["kale", "🥬"], ["lettuce", "🥬"],
  ["carrot", "🥕"], ["tomato", "🍅"], ["cucumber", "🥒"], ["pepper", "🫑"], ["cauliflower", "🥦"], ["mushroom", "🍄"],
  ["onion", "🧅"], ["peanut", "🥜"], ["almond", "🌰"], ["walnut", "🌰"], ["cashew", "🌰"], ["seed", "🌱"],
  ["avocado", "🥑"], ["olive", "🫒"], ["butter", "🧈"], ["ghee", "🧈"], ["coconut", "🥥"], ["water", "💧"],
  ["coffee", "☕"], ["tea", "🍵"], ["cola", "🥤"], ["energy drink", "⚡"], ["punch", "🧃"], ["beer", "🍺"],
  ["wine", "🍷"], ["sugar", "🍬"], ["honey", "🍯"],
];

function foodEmoji(food) {
  const name = food.name.toLowerCase();
  const hit = FOOD_EMOJI.find(([k]) => name.includes(k));
  return hit ? hit[1] : GROUP_EMOJI[food.group] || "🍽️";
}

const MICROS = [
  ["potassium_mg", "Potassium", " mg"], ["calcium_mg", "Calcium", " mg"], ["iron_mg", "Iron", " mg"],
  ["magnesium_mg", "Magnesium", " mg"], ["zinc_mg", "Zinc", " mg"], ["vitamin_a_ug", "Vitamin A", " µg"],
  ["vitamin_c_mg", "Vitamin C", " mg"], ["vitamin_d_ug", "Vitamin D", " µg"], ["vitamin_b12_ug", "Vitamin B12", " µg"],
];

function pct(n, key) {
  const v = n[key];
  return v === null || v === undefined || !DV[key] ? null : Math.round((v / DV[key]) * 100);
}

function Row({ n, k, label, unit, dot }) {
  const p = pct(n, k);
  return (
    <li>
      {dot && <i className={`dot ${dot}`} />}{label}
      <b>{fmt(n[k], unit)}</b>
      <span className="dv">{p === null ? "" : `${p}%`}</span>
    </li>
  );
}

export default function FoodCard({ food }) {
  const portion = food.portion;
  const per100 = food.per_100g || food.nutrients || {};
  const [basis, setBasis] = useState(portion ? "portion" : "100g");
  const n = basis === "portion" ? food.nutrients || {} : per100;

  const macroCals = { protein: (n.protein_g || 0) * 4, carbs: (n.carbs_g || 0) * 4, fat: (n.fat_g || 0) * 9 };
  const total = macroCals.protein + macroCals.carbs + macroCals.fat || 1;
  const share = (k) => Math.round((macroCals[k] / total) * 100);
  // protein density is basis-independent, so use the USDA per-100 g values
  const proteinPer100kcal = per100.calories_kcal ? (per100.protein_g || 0) / per100.calories_kcal * 100 : null;

  return (
    <article className="food-card">
      <header className="food-head">
        <span className="food-emoji" aria-hidden>{foodEmoji(food)}</span>
        <h4>{food.name}</h4>
      </header>
      <div className="basis-toggle" role="group" aria-label="Nutrition basis">
        {portion && (
          <button className={basis === "portion" ? "on" : ""} onClick={() => setBasis("portion")} aria-pressed={basis === "portion"}>
            {`${portion.description} (${portion.grams} g)`}
          </button>
        )}
        <button className={basis === "100g" ? "on" : ""} onClick={() => setBasis("100g")} aria-pressed={basis === "100g"}>per 100 g</button>
      </div>
      <div className="food-kcal"><strong>{fmt(n.calories_kcal, "")}</strong> kcal</div>
      <div className="macro-bar" role="img"
           aria-label={`Energy split: protein ${share("protein")}%, carbohydrate ${share("carbs")}%, fat ${share("fat")}%`}>
        <span className="m-protein" style={{ width: `${(macroCals.protein / total) * 100}%` }} />
        <span className="m-carbs" style={{ width: `${(macroCals.carbs / total) * 100}%` }} />
        <span className="m-fat" style={{ width: `${(macroCals.fat / total) * 100}%` }} />
      </div>
      <div className="energy-split">
        <span><i className="dot m-protein" />{share("protein")}% protein</span>
        <span><i className="dot m-carbs" />{share("carbs")}% carbs</span>
        <span><i className="dot m-fat" />{share("fat")}% fat</span>
      </div>
      <ul className="macros">
        <li className="macros-head"><span>Nutrient</span><span>Amount</span><span>% DV</span></li>
        <Row n={n} k="protein_g" label="Protein" unit=" g" dot="m-protein" />
        <Row n={n} k="carbs_g" label="Carbs" unit=" g" dot="m-carbs" />
        <Row n={n} k="fiber_g" label="Fiber" unit=" g" />
        <Row n={n} k="sugar_g" label="Sugars" unit=" g" />
        <Row n={n} k="fat_g" label="Fat" unit=" g" dot="m-fat" />
        <Row n={n} k="saturated_fat_g" label="Saturated" unit=" g" />
        <Row n={n} k="cholesterol_mg" label="Cholesterol" unit=" mg" />
        <Row n={n} k="sodium_mg" label="Sodium" unit=" mg" />
      </ul>
      {proteinPer100kcal !== null && (
        <div className="fit-fact">💪 <b>{fmt(proteinPer100kcal, " g")}</b> protein per 100 kcal
          <span className="muted"> · {proteinPer100kcal >= 10 ? "great" : proteinPer100kcal >= 5 ? "good" : "low"} protein density</span>
        </div>
      )}
      <details className="micros">
        <summary>Vitamins, minerals &amp; more</summary>
        <ul className="macros">
          {MICROS.map(([k, label, unit]) => <Row key={k} n={n} k={k} label={label} unit={unit} />)}
          <Row n={n} k="mono_fat_g" label="Monounsat. fat" unit=" g" />
          <Row n={n} k="poly_fat_g" label="Polyunsat. fat" unit=" g" />
          {n.caffeine_mg > 0 && <Row n={n} k="caffeine_mg" label="☕ Caffeine" unit=" mg" />}
          <Row n={n} k="water_g" label="💧 Water" unit=" g" />
        </ul>
      </details>
      {food.highlights?.length > 0 && (
        <div className="chips">{food.highlights.map((h) => <span key={h} className="chip">{h}</span>)}</div>
      )}
      <footer>
        <a href={food.source_url} target="_blank" rel="noreferrer">USDA FoodData Central #{food.fdc_id}</a>
        {basis === "portion" && <span title="Portion values are computed from USDA per-100 g values and USDA portion weight"> · computed per portion</span>}
        <div>% DV: FDA Daily Values, 2,000 kcal diet. — = not reported by USDA.</div>
      </footer>
    </article>
  );
}
