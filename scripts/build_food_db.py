"""Build FitBot's nutrition database from USDA FoodData Central SR Legacy (CC0 1.0).

Source: https://fdc.nal.usda.gov/fdc-datasets/FoodData_Central_sr_legacy_food_json_2018-04.zip
Output: data/nutrition/foods.json

All nutrient values are copied exactly from SR Legacy (per 100 g). Per-portion values
are *computed* from the USDA gram weight of the chosen household portion and are
labelled as computed. Nothing is estimated or invented: if a nutrient is missing in
USDA data it is stored as null.

The `group` / `fitbot_tags` fields are FitBot's own classification for retrieval.
Data-driven highlights (e.g. "high protein") are derived from the USDA numbers using
the thresholds in `highlights_for`.
"""
from __future__ import annotations

import io
import json
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "FoodData_Central_sr_legacy_food_json_2018-04.json"
ZIP_URL = "https://fdc.nal.usda.gov/fdc-datasets/FoodData_Central_sr_legacy_food_json_2018-04.zip"
OUT = ROOT / "data" / "nutrition" / "foods.json"

# USDA nutrient numbers -> FitBot field names
NUTRIENTS = {
    "208": "calories_kcal", "203": "protein_g", "205": "carbs_g", "204": "fat_g",
    "291": "fiber_g", "269": "sugar_g", "307": "sodium_mg", "606": "saturated_fat_g",
    "306": "potassium_mg", "301": "calcium_mg", "303": "iron_mg", "262": "caffeine_mg",
    "601": "cholesterol_mg", "645": "mono_fat_g", "646": "poly_fat_g", "304": "magnesium_mg", "309": "zinc_mg",
    "320": "vitamin_a_ug", "401": "vitamin_c_mg", "328": "vitamin_d_ug", "418": "vitamin_b12_ug", "255": "water_g",
}

# (display name, fdcId, group, fitbot tags, aliases, preferred portion keyword)
FOODS: list[tuple] = [
    # --- Protein foods ---
    ("Egg (whole, hard-boiled)", 173424, "protein", ["breakfast", "vegetarian"], ["egg", "eggs", "boiled egg", "hard boiled egg"], "large"),
    ("Egg (whole, raw)", 171287, "protein", ["breakfast", "vegetarian"], ["raw egg", "whole egg"], "large"),
    ("Egg white", 172183, "protein", ["breakfast", "vegetarian", "lean"], ["egg whites"], "large"),
    ("Chicken breast (roasted)", 171477, "protein", ["lean", "post_workout"], ["chicken", "chicken breast", "grilled chicken"], "breast"),
    ("Chicken thigh (roasted)", 172388, "protein", [], ["chicken thigh"], "thigh"),
    ("Ground turkey (cooked)", 171506, "protein", ["lean"], ["turkey", "ground turkey"], "oz"),
    ("Lean ground beef 90% (cooked)", 171794, "protein", [], ["beef", "ground beef", "mince"], "oz"),
    ("Top sirloin steak (lean, cooked)", 168634, "protein", ["lean"], ["steak", "sirloin", "red meat"], "oz"),
    ("Pork tenderloin (roasted)", 168250, "protein", ["lean"], ["pork"], "oz"),
    ("Salmon (Atlantic, farmed, cooked)", 175168, "protein", ["healthy_fats", "omega3"], ["salmon", "fish"], "fillet"),
    ("Tuna (light, canned in water)", 171986, "protein", ["lean"], ["tuna", "canned tuna"], "can"),
    ("Cod (Atlantic, cooked)", 171956, "protein", ["lean"], ["cod", "white fish"], "fillet"),
    ("Tilapia (cooked)", 175177, "protein", ["lean"], ["tilapia"], "fillet"),
    ("Sardines (canned in oil)", 175139, "protein", ["omega3"], ["sardines", "sardine"], "can"),
    ("Shrimp (cooked)", 171971, "protein", ["lean"], ["shrimp", "prawns"], "oz"),
    ("Whey protein powder", 173180, "protein", ["post_workout", "supplement"], ["whey", "protein powder", "protein shake"], "scoop"),
    # --- Plant proteins / legumes ---
    ("Tofu (firm)", 172448, "plant_protein", ["vegetarian", "vegan"], ["tofu"], "cup"),
    ("Tempeh", 174272, "plant_protein", ["vegetarian", "vegan"], ["tempeh"], "cup"),
    ("Lentils (boiled)", 172421, "plant_protein", ["vegetarian", "vegan", "high_fiber"], ["lentils", "dal", "daal"], "cup"),
    ("Chickpeas (boiled)", 173757, "plant_protein", ["vegetarian", "vegan", "high_fiber"], ["chickpeas", "garbanzo beans", "chana"], "cup"),
    ("Black beans (boiled)", 173735, "plant_protein", ["vegetarian", "vegan", "high_fiber"], ["black beans", "beans"], "cup"),
    ("Kidney beans (boiled)", 173740, "plant_protein", ["vegetarian", "vegan", "high_fiber"], ["kidney beans", "rajma"], "cup"),
    ("Pinto beans (boiled)", 175200, "plant_protein", ["vegetarian", "vegan", "high_fiber"], ["pinto beans"], "cup"),
    ("Edamame (prepared)", 168411, "plant_protein", ["vegetarian", "vegan"], ["edamame", "soybeans"], "cup"),
    ("Hummus", 174289, "plant_protein", ["vegetarian", "vegan", "snack"], ["hummus"], "tbsp"),
    # --- Dairy & alternatives ---
    ("Greek yogurt (plain, nonfat)", 170894, "dairy", ["vegetarian", "breakfast", "snack", "post_workout"], ["greek yogurt", "yogurt", "curd"], "container"),
    ("Greek yogurt (plain, whole milk)", 171304, "dairy", ["vegetarian", "breakfast"], ["full fat greek yogurt"], "container"),
    ("Yogurt (plain, low fat)", 170886, "dairy", ["vegetarian", "breakfast", "snack"], ["plain yogurt", "low fat yogurt"], "cup"),
    ("Milk (2% reduced fat)", 171267, "dairy", ["vegetarian", "breakfast"], ["milk", "2% milk"], "cup"),
    ("Milk (whole)", 171265, "dairy", ["vegetarian"], ["whole milk", "full cream milk"], "cup"),
    ("Milk (skim / nonfat)", 171269, "dairy", ["vegetarian", "lean"], ["skim milk", "nonfat milk"], "cup"),
    ("Chocolate milk (low fat)", 170881, "dairy", ["vegetarian", "post_workout"], ["chocolate milk"], "cup"),
    ("Cottage cheese (low fat, 2%)", 172182, "dairy", ["vegetarian", "snack"], ["cottage cheese"], "cup"),
    ("Cheddar cheese", 173414, "dairy", ["vegetarian"], ["cheese", "cheddar"], "slice"),
    ("Mozzarella (part skim)", 170847, "dairy", ["vegetarian"], ["mozzarella"], "oz"),
    ("Soy milk (original, fortified)", 172456, "dairy_alternative", ["vegetarian", "vegan"], ["soy milk", "soymilk"], "cup"),
    ("Almond milk (unsweetened)", 174832, "dairy_alternative", ["vegetarian", "vegan"], ["almond milk"], "cup"),
    # --- Grains & starches ---
    ("Oats (dry)", 169705, "grains", ["breakfast", "high_fiber", "vegetarian", "vegan", "pre_workout"], ["oats", "oatmeal", "porridge", "rolled oats"], "cup"),
    ("White rice (cooked)", 168878, "grains", ["vegetarian", "vegan", "pre_workout", "post_workout"], ["rice", "white rice"], "cup"),
    ("Brown rice (cooked)", 169704, "grains", ["vegetarian", "vegan", "high_fiber"], ["brown rice"], "cup"),
    ("Quinoa (cooked)", 168917, "grains", ["vegetarian", "vegan"], ["quinoa"], "cup"),
    ("Whole-wheat bread", 172688, "grains", ["vegetarian", "breakfast"], ["whole wheat bread", "brown bread", "wholemeal bread"], "slice"),
    ("White bread", 174924, "grains", ["vegetarian"], ["white bread", "bread"], "slice"),
    ("Pasta (cooked)", 169737, "grains", ["vegetarian", "vegan"], ["pasta", "spaghetti", "noodles"], "cup"),
    ("Couscous (cooked)", 169700, "grains", ["vegetarian", "vegan"], ["couscous"], "cup"),
    ("Bagel (plain)", 175049, "grains", ["vegetarian", "breakfast"], ["bagel"], "bagel"),
    ("Whole-wheat tortilla", 174081, "grains", ["vegetarian"], ["tortilla", "wrap", "roti", "chapati"], "tortilla"),
    ("Potato (baked, with skin)", 170093, "starchy_vegetable", ["vegetarian", "vegan", "post_workout"], ["potato", "potatoes", "baked potato"], "medium"),
    ("Sweet potato (baked)", 168483, "starchy_vegetable", ["vegetarian", "vegan", "high_fiber"], ["sweet potato", "yam"], "medium"),
    ("Sweet corn (boiled)", 169999, "starchy_vegetable", ["vegetarian", "vegan"], ["corn", "sweet corn"], "cup"),
    ("Popcorn (air-popped)", 167959, "snacks", ["vegetarian", "vegan", "snack", "high_fiber"], ["popcorn"], "cup"),
    ("Rice cake (brown rice, multigrain)", 169680, "snacks", ["vegetarian", "vegan", "snack", "pre_workout"], ["rice cake", "rice cakes"], "cake"),
    # --- Fruit ---
    ("Banana", 173944, "fruit", ["vegetarian", "vegan", "pre_workout", "snack"], ["banana", "bananas"], "medium"),
    ("Apple (with skin)", 171688, "fruit", ["vegetarian", "vegan", "snack"], ["apple", "apples"], "medium"),
    ("Orange", 169097, "fruit", ["vegetarian", "vegan", "snack"], ["orange", "oranges"], "fruit"),
    ("Blueberries", 171711, "fruit", ["vegetarian", "vegan", "breakfast"], ["blueberries", "berries"], "cup"),
    ("Strawberries", 167762, "fruit", ["vegetarian", "vegan", "breakfast"], ["strawberries"], "cup"),
    ("Grapes", 174683, "fruit", ["vegetarian", "vegan", "snack"], ["grapes"], "cup"),
    ("Mango", 169910, "fruit", ["vegetarian", "vegan"], ["mango", "mangoes"], "cup"),
    ("Pineapple", 169124, "fruit", ["vegetarian", "vegan"], ["pineapple"], "cup"),
    ("Watermelon", 167765, "fruit", ["vegetarian", "vegan", "hydrating"], ["watermelon"], "cup"),
    ("Pear", 167776, "fruit", ["vegetarian", "vegan", "high_fiber"], ["pear", "pears"], "medium"),
    ("Kiwifruit", 168153, "fruit", ["vegetarian", "vegan"], ["kiwi", "kiwifruit"], "fruit"),
    ("Cherries (sweet)", 171719, "fruit", ["vegetarian", "vegan"], ["cherries"], "cup"),
    ("Medjool dates", 168191, "fruit", ["vegetarian", "vegan", "pre_workout"], ["dates", "date"], "date"),
    ("Raisins", 168165, "fruit", ["vegetarian", "vegan", "pre_workout"], ["raisins"], "box"),
    # --- Vegetables ---
    ("Broccoli (boiled)", 169967, "vegetables", ["vegetarian", "vegan", "high_fiber"], ["broccoli"], "cup"),
    ("Spinach (raw)", 168462, "vegetables", ["vegetarian", "vegan"], ["spinach", "palak"], "cup"),
    ("Kale (raw)", 168421, "vegetables", ["vegetarian", "vegan"], ["kale"], "cup"),
    ("Carrots (raw)", 170393, "vegetables", ["vegetarian", "vegan", "snack"], ["carrot", "carrots"], "medium"),
    ("Tomato (raw)", 170457, "vegetables", ["vegetarian", "vegan"], ["tomato", "tomatoes"], "medium"),
    ("Cucumber (with peel)", 168409, "vegetables", ["vegetarian", "vegan", "hydrating"], ["cucumber"], "cup"),
    ("Red bell pepper (raw)", 170108, "vegetables", ["vegetarian", "vegan"], ["bell pepper", "capsicum", "red pepper"], "medium"),
    ("Cauliflower (raw)", 169986, "vegetables", ["vegetarian", "vegan"], ["cauliflower"], "cup"),
    ("Green peas (boiled)", 170420, "vegetables", ["vegetarian", "vegan", "high_fiber"], ["peas", "green peas"], "cup"),
    ("Mushrooms (white, raw)", 169251, "vegetables", ["vegetarian", "vegan"], ["mushroom", "mushrooms"], "cup"),
    ("Romaine lettuce", 169247, "vegetables", ["vegetarian", "vegan"], ["lettuce", "salad greens"], "cup"),
    ("Onion (raw)", 170000, "vegetables", ["vegetarian", "vegan"], ["onion", "onions"], "medium"),
    # --- Healthy fats ---
    ("Almonds", 170567, "fats", ["vegetarian", "vegan", "snack", "healthy_fats"], ["almonds", "almond"], "oz"),
    ("Walnuts", 170187, "fats", ["vegetarian", "vegan", "healthy_fats", "omega3"], ["walnuts", "walnut"], "oz"),
    ("Cashews (raw)", 170162, "fats", ["vegetarian", "vegan", "healthy_fats"], ["cashews", "cashew"], "oz"),
    ("Peanuts (dry-roasted)", 173806, "fats", ["vegetarian", "vegan", "healthy_fats"], ["peanuts", "groundnuts"], "oz"),
    ("Peanut butter (smooth)", 172470, "fats", ["vegetarian", "vegan", "healthy_fats"], ["peanut butter"], "tbsp"),
    ("Chia seeds", 170554, "fats", ["vegetarian", "vegan", "healthy_fats", "high_fiber", "omega3"], ["chia", "chia seeds"], "oz"),
    ("Flaxseed", 169414, "fats", ["vegetarian", "vegan", "healthy_fats", "high_fiber", "omega3"], ["flaxseed", "flax seeds", "linseed"], "tbsp"),
    ("Pumpkin seeds (kernels)", 170556, "fats", ["vegetarian", "vegan", "healthy_fats"], ["pumpkin seeds", "pepitas"], "oz"),
    ("Avocado", 171706, "fats", ["vegetarian", "vegan", "healthy_fats"], ["avocado"], "fruit"),
    ("Olive oil", 171413, "fats", ["vegetarian", "vegan", "healthy_fats"], ["olive oil", "oil"], "tbsp"),
    ("Butter (salted)", 173410, "fats", ["vegetarian", "limit"], ["butter"], "tbsp"),
    ("Ghee", 171314, "fats", ["vegetarian", "limit"], ["ghee", "clarified butter"], "tbsp"),
    ("Dark chocolate (70-85%)", 170273, "treats", ["vegetarian"], ["dark chocolate"], "oz"),
    # --- Beverages ---
    ("Water (tap)", 173647, "beverages", ["hydrating"], ["water", "tap water"], "cup"),
    ("Coconut water (unsweetened)", 174831, "beverages", ["hydrating"], ["coconut water"], "cup"),
    ("Black coffee (brewed)", 171890, "beverages", ["pre_workout"], ["coffee", "black coffee"], "cup"),
    ("Black tea (brewed)", 173227, "beverages", [], ["tea", "black tea"], "cup"),
    ("Orange juice", 169098, "beverages", ["limit_portion"], ["orange juice", "juice"], "cup"),
    ("Apple juice (unsweetened)", 167771, "beverages", ["limit_portion"], ["apple juice"], "cup"),
    ("Cola (regular)", 174852, "beverages", ["limit"], ["cola", "coke", "soda", "soft drink", "fizzy drink"], "can"),
    ("Energy drink (Red Bull)", 173210, "beverages", ["limit"], ["energy drink", "red bull"], "can"),
    ("Fruit punch drink", 171914, "beverages", ["limit"], ["fruit punch", "sugary drink"], "cup"),
    ("Beer (regular)", 168746, "beverages", ["limit", "alcohol"], ["beer"], "can"),
    ("Red wine", 173190, "beverages", ["limit", "alcohol"], ["wine", "red wine"], "glass"),
    # --- Foods often worth limiting ---
    ("Potato chips (barbecue)", 167962, "treats", ["limit"], ["chips", "crisps", "potato chips"], "oz"),
    ("French fries (fast food)", 170698, "treats", ["limit"], ["french fries", "fries", "chips (fries)"], "medium"),
    ("Glazed doughnut", 172758, "treats", ["limit"], ["doughnut", "donut"], "medium"),
    ("Chocolate chip cookies", 172716, "treats", ["limit"], ["cookies", "cookie", "biscuits"], "cookie"),
    ("Milk chocolate", 167587, "treats", ["limit"], ["milk chocolate", "chocolate bar", "candy"], "bar"),
    ("Vanilla ice cream", 167575, "treats", ["limit"], ["ice cream"], "cup"),
    ("Cheese pizza (frozen, cooked)", 170317, "treats", ["limit"], ["pizza"], "serving"),
    ("Granulated sugar", 169655, "treats", ["limit"], ["sugar", "table sugar"], "tsp"),
    ("Honey", 169640, "treats", ["limit_portion"], ["honey"], "tbsp"),
]

def highlights_for(per100: dict, portion: dict | None, group: str, tags: list[str]) -> list[str]:
    """Descriptive labels derived only from USDA numbers (documented thresholds)."""
    def v(k):
        return per100.get(k) or 0.0
    out = []
    kcal = v("calories_kcal")
    # protein supplies >=20% of energy and >=5 g/100 g (excludes low-calorie greens)
    if v("protein_g") >= 5 and kcal and v("protein_g") * 4 / kcal >= 0.20:
        out.append("High protein")
    if v("fiber_g") >= 6:
        out.append("High fiber")
    portion_sugar = ((portion or {}).get("nutrients") or {}).get("sugar_g") or 0
    # per-serving sugar rule applies to drinks/treats (whole fruit is judged per 100 g only)
    if v("sugar_g") >= 20 or (group in ("beverages", "treats", "dairy") and portion_sugar >= 20):
        out.append("High sugar")
    if v("sodium_mg") >= 600:
        out.append("High sodium")
    # saturated fat >=5 g/100 g and at least a third of total fat
    if v("saturated_fat_g") >= 5 and v("fat_g") and v("saturated_fat_g") / v("fat_g") >= 0.33:
        out.append("High saturated fat")
    if "limit" not in tags and v("fat_g") >= 10 and v("saturated_fat_g") / max(v("fat_g"), 1e-9) < 0.25:
        out.append("Mostly unsaturated fat")
    return out


def load_sr_legacy() -> list[dict]:
    if not RAW.exists():
        print(f"Downloading {ZIP_URL} ...")
        data = urllib.request.urlopen(ZIP_URL, timeout=300).read()
        zipfile.ZipFile(io.BytesIO(data)).extractall(RAW.parent)
    return json.loads(RAW.read_text())["SRLegacyFoods"]


def portion_label(p: dict) -> str:
    unit = p.get("measureUnit", {}).get("name", "")
    unit = "" if unit in ("undetermined", "") else unit
    amount = p.get("amount") or p.get("value") or 1
    amount = int(amount) if float(amount).is_integer() else amount
    return " ".join(str(x) for x in (amount, unit, p.get("modifier", "")) if str(x).strip()).strip()


def pick_portion(portions: list[dict], keyword: str) -> dict | None:
    if not portions:
        return None
    ordered = sorted(portions, key=lambda p: p.get("sequenceNumber", 99))
    for p in ordered:
        if keyword and keyword in portion_label(p).lower():
            return p
    return ordered[0]


def main() -> None:
    foods = {f["fdcId"]: f for f in load_sr_legacy()}
    out, missing = [], []
    for (name, fdc_id, group, tags, aliases, portion_kw) in FOODS:
        src = foods.get(fdc_id)
        if src is None:
            missing.append((name, fdc_id))
            continue
        per100 = {v: None for v in NUTRIENTS.values()}
        for n in src.get("foodNutrients", []):
            key = NUTRIENTS.get(str(n.get("nutrient", {}).get("number")))
            if key and n.get("amount") is not None:
                per100[key] = round(float(n["amount"]), 2)
        p = pick_portion(src.get("foodPortions", []), portion_kw)
        portion = None
        if p and p.get("gramWeight"):
            g = float(p["gramWeight"])
            portion = {
                "description": portion_label(p),
                "grams": g,
                "nutrients": {k: (round(v * g / 100, 1) if v is not None else None) for k, v in per100.items()},
                "note": "computed from USDA per-100 g values and USDA portion gram weight",
            }
        highlights = highlights_for(per100, portion, group, tags)
        out.append({
            "name": name,
            "slug": name.lower().split(" (")[0].replace(" ", "-"),
            "fdc_id": fdc_id,
            "usda_description": src["description"],
            "usda_category": src.get("foodCategory", {}).get("description"),
            "group": group,
            "fitbot_tags": tags,
            "aliases": aliases,
            "per_100g": per100,
            "portion": portion,
            "highlights": highlights,
            "source": "USDA FoodData Central, SR Legacy (April 2018), CC0 1.0",
            "source_url": f"https://fdc.nal.usda.gov/food-details/{fdc_id}/nutrients",
        })
    if missing:
        sys.exit(f"fdcIds not found: {missing}")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False))
    groups: dict[str, int] = {}
    for f in out:
        groups[f["group"]] = groups.get(f["group"], 0) + 1
    print(f"Wrote {len(out)} foods -> {OUT.relative_to(ROOT)}  {groups}")
    no_portion = [f["name"] for f in out if not f["portion"]]
    if no_portion:
        print("No USDA portion for:", no_portion)


if __name__ == "__main__":
    main()
