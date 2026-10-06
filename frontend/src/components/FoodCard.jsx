const fmt = (v, unit) => (v === null || v === undefined ? "—" : `${Math.round(v * 10) / 10}${unit}`);

export default function FoodCard({ food }) {
  const n = food.nutrients || {};
  const macroCals = {
    protein: (n.protein_g || 0) * 4,
    carbs: (n.carbs_g || 0) * 4,
    fat: (n.fat_g || 0) * 9,
  };
  const total = macroCals.protein + macroCals.carbs + macroCals.fat || 1;

  return (
    <article className="food-card">
      <header>
        <h4>{food.name}</h4>
        <span className="food-basis">{food.portion ? `${food.portion.description} (${food.portion.grams} g)` : "per 100 g"}</span>
      </header>
      <div className="food-kcal"><strong>{fmt(n.calories_kcal, "")}</strong> kcal</div>
      <div className="macro-bar" role="img"
           aria-label={`Energy split: protein ${Math.round((macroCals.protein / total) * 100)}%, carbohydrate ${Math.round((macroCals.carbs / total) * 100)}%, fat ${Math.round((macroCals.fat / total) * 100)}%`}>
        <span className="m-protein" style={{ width: `${(macroCals.protein / total) * 100}%` }} />
        <span className="m-carbs" style={{ width: `${(macroCals.carbs / total) * 100}%` }} />
        <span className="m-fat" style={{ width: `${(macroCals.fat / total) * 100}%` }} />
      </div>
      <ul className="macros">
        <li><i className="dot m-protein" />Protein <b>{fmt(n.protein_g, " g")}</b></li>
        <li><i className="dot m-carbs" />Carbs <b>{fmt(n.carbs_g, " g")}</b></li>
        <li><i className="dot m-fat" />Fat <b>{fmt(n.fat_g, " g")}</b></li>
        <li>Fiber <b>{fmt(n.fiber_g, " g")}</b></li>
        <li>Sugars <b>{fmt(n.sugar_g, " g")}</b></li>
        <li>Sodium <b>{fmt(n.sodium_mg, " mg")}</b></li>
      </ul>
      {food.highlights?.length > 0 && (
        <div className="chips">{food.highlights.map((h) => <span key={h} className="chip">{h}</span>)}</div>
      )}
      <footer>
        <a href={food.source_url} target="_blank" rel="noreferrer">USDA FoodData Central #{food.fdc_id}</a>
        {food.portion && <span title="Portion values are computed from USDA per-100 g values and USDA portion weight"> · computed per portion</span>}
      </footer>
    </article>
  );
}
