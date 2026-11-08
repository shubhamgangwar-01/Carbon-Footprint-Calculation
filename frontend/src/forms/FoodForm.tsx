import { Droplets, Plus, Trash2, UtensilsCrossed } from "lucide-react";
import { Alert, Card, Field, NotApplicable, NumberInput, Select, Toggle } from "../components/ui";
import { useConference } from "../state/ConferenceContext";
import type { FoodData, IngredientEntry, MealEntry } from "../types";
import { uid } from "../utils/format";

const SERVICES = [
  { v: "breakfast", l: "Breakfast" }, { v: "lunch", l: "Lunch" }, { v: "dinner", l: "Dinner" }, { v: "snack", l: "Snacks & refreshments" },
];
const MAIN_DIETS = ["vegetarian", "vegan", "non_vegetarian_chicken", "non_vegetarian_fish", "non_vegetarian_egg", "non_vegetarian_mutton", "non_vegetarian_pork", "non_vegetarian_beef"];
const SNACK_DIETS = ["snack_refreshment", "snack_refreshment_coffee"];
const DIET_LABEL: Record<string, string> = {
  vegetarian: "Vegetarian", vegan: "Vegan", non_vegetarian_chicken: "Non-veg (chicken)", non_vegetarian_fish: "Non-veg (fish)",
  non_vegetarian_egg: "Egg", non_vegetarian_mutton: "Non-veg (mutton)", non_vegetarian_pork: "Non-veg (pork)", non_vegetarian_beef: "Non-veg (beef)",
  snack_refreshment: "Tea + snack", snack_refreshment_coffee: "Coffee + snack",
};
const empty = (): FoodData => ({ not_applicable: false, meals: [], ingredients: [], bottled_water: null });

export default function FoodForm() {
  const { input, setInput, options } = useConference();
  const fd = input.food || empty();
  const set = (patch: Partial<FoodData>) => setInput((p) => ({ ...p, food: { ...(p.food || empty()), ...patch } }));
  const methodOf = (s: string) => (fd.ingredients.some((i) => i.service === s) ? "ingredient" : "meal");
  const mealFactor = (d: string) => options?.meal_models.find((m) => m.key === d)?.factor;
  const setCount = (service: string, diet: string, count: number) => {
    const others = fd.meals.filter((m) => !(m.service === service && m.diet === diet));
    set({ meals: count > 0 ? [...others, { id: uid(), service, diet, count, data_type: "actual" } as MealEntry] : others });
  };
  const switchMethod = (service: string, m: string) => {
    if (m === "ingredient") set({ meals: fd.meals.filter((x) => x.service !== service), ingredients: [...fd.ingredients, { id: uid(), service, food_key: "food.rice", quantity: 0, unit: "kg", data_type: "actual" }] });
    else set({ ingredients: fd.ingredients.filter((x) => x.service !== service) });
  };
  const updIng = (id: string, p: Partial<IngredientEntry>) => set({ ingredients: fd.ingredients.map((x) => (x.id === id ? { ...x, ...p } : x)) });
  const foodWaste = input.waste?.entries.find((w) => w.material === "food");
  const foods = options?.food_items || [];
  const IngredientRows = ({ service }: { service: string }) => (
    <div className="space-y-2">
      {fd.ingredients.filter((i) => i.service === service).map((i) => (
        <div key={i.id} className="grid grid-cols-6 gap-2">
          <div className="col-span-3"><Select ariaLabel="Food item" value={i.food_key} onChange={(v) => updIng(i.id, { food_key: v })} options={foods.map((f) => ({ value: f.key, label: `${f.label} (${f.factor.toFixed(2)} kg CO₂e/kg)` }))} /></div>
          <NumberInput ariaLabel="Quantity" value={i.quantity} onChange={(v) => updIng(i.id, { quantity: v ?? 0 })} />
          <Select ariaLabel="Unit" value={i.unit} onChange={(v) => updIng(i.id, { unit: v })} options={[{ value: "kg", label: "kg" }, { value: "g", label: "g" }, { value: "tonne", label: "tonne" }, { value: "litre", label: "litre" }]} />
          <button className="btn-ghost text-red-600" aria-label="Remove" onClick={() => set({ ingredients: fd.ingredients.filter((x) => x.id !== i.id) })}><Trash2 size={16} /></button>
        </div>
      ))}
      <button className="btn-secondary" onClick={() => set({ ingredients: [...fd.ingredients, { id: uid(), service, food_key: "food.vegetables", quantity: 0, unit: "kg", data_type: "actual" }] })}><Plus size={14} />Add ingredient</button>
    </div>
  );
  return (
    <div className="space-y-6">
      <Card title="Food & beverages" icon={<UtensilsCrossed size={20} />}
        subtitle="For each meal service use EITHER meal counts (modelled per-meal factors) OR purchased ingredient quantities - never both, to avoid double counting.">
        <NotApplicable checked={fd.not_applicable} onChange={(v) => set({ not_applicable: v })} what="Catering" />
        {!fd.not_applicable && <div className="mt-3"><Alert kind="info">Per-meal factors model one-third of the ICMR-NIN “My Plate for the Day” (2024) using Poore & Nemecek (2018) farm-to-retail data, e.g. vegetarian ≈ {mealFactor("vegetarian")?.toFixed(2) ?? "0.79"} kg, chicken ≈ {mealFactor("non_vegetarian_chicken")?.toFixed(2) ?? "1.72"} kg CO₂e per meal. Ingredient quantities from the caterer are more accurate.</Alert></div>}
      </Card>
      {!fd.not_applicable && SERVICES.map((s) => {
        const method = methodOf(s.v);
        const diets = s.v === "snack" ? SNACK_DIETS : MAIN_DIETS;
        const total = fd.meals.filter((m) => m.service === s.v).reduce((a, m) => a + m.count, 0);
        return (
          <Card key={s.v} title={s.l} subtitle={method === "meal" ? `${total.toLocaleString()} servings` : "Ingredient-based"}
            actions={<div className="w-48"><Select ariaLabel={`${s.l} method`} value={method} onChange={(m) => switchMethod(s.v, m)} options={[{ value: "meal", label: "Meal counts" }, { value: "ingredient", label: "Ingredient quantities" }]} /></div>}>
            {method === "meal" ? (
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                {diets.map((d) => (
                  <Field key={d} label={DIET_LABEL[d]} unit="servings" tip={mealFactor(d) ? `Modelled factor: ${mealFactor(d)!.toFixed(3)} kg CO₂e per serving.` : undefined}>
                    <NumberInput step="1" value={fd.meals.find((m) => m.service === s.v && m.diet === d)?.count ?? null} onChange={(v) => setCount(s.v, d, v ?? 0)} />
                  </Field>
                ))}
              </div>
            ) : <IngredientRows service={s.v} />}
          </Card>
        );
      })}
      {!fd.not_applicable && (
        <Card title="Beverages & bottled water" icon={<Droplets size={20} />} subtitle="Tea, coffee, milk and other beverages by quantity; bottled water by number of bottles.">
          <IngredientRows service="beverages" />
          <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Field label="Bottled water" unit="bottles"><NumberInput step="1" value={fd.bottled_water?.bottles ?? null} onChange={(v) => set({ bottled_water: v ? { bottles: v, volume_litres: fd.bottled_water?.volume_litres ?? 0.5, bottle_mass_g: fd.bottled_water?.bottle_mass_g ?? null, recycled_pet: fd.bottled_water?.recycled_pet ?? false, data_type: "actual" } : null })} /></Field>
            {fd.bottled_water && <>
              <Field label="Volume per bottle" unit="litres"><NumberInput value={fd.bottled_water.volume_litres} onChange={(v) => set({ bottled_water: { ...fd.bottled_water!, volume_litres: v ?? 0.5 } })} /></Field>
              <Field label="Empty bottle mass" unit="g" tip="PET mass of one empty bottle from the supplier's specification. Required - no default is assumed." error={!fd.bottled_water.bottle_mass_g ? "Required to count bottled water" : undefined}>
                <NumberInput value={fd.bottled_water.bottle_mass_g} onChange={(v) => set({ bottled_water: { ...fd.bottled_water!, bottle_mass_g: v } })} />
              </Field>
              <div className="flex items-end pb-2"><Toggle checked={fd.bottled_water.recycled_pet} onChange={(v) => set({ bottled_water: { ...fd.bottled_water!, recycled_pet: v } })} label="Recycled PET (rPET)" /></div>
            </>}
          </div>
          <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Field label="Food waste" unit="kg" tip="Synchronised with the Waste step (counted once, under Waste). Enter disposal routes on the next step.">
              <NumberInput value={foodWaste?.generated_kg ?? null} onChange={(v) => setInput((p) => {
                const entries = (p.waste?.entries || []).filter((w) => w.material !== "food");
                const prev = p.waste?.entries.find((w) => w.material === "food");
                const nw = v ? [...entries, { ...(prev || { id: uid(), material: "food", landfill_kg: 0, recycling_kg: 0, composting_kg: 0, incineration_kg: 0, anaerobic_digestion_kg: 0, data_type: "actual" as const }), generated_kg: v }] : entries;
                return { ...p, waste: { not_applicable: false, entries: nw } };
              })} />
            </Field>
          </div>
        </Card>
      )}
    </div>
  );
}
