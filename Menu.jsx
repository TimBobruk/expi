import { useState } from "react";
import { motion } from "framer-motion";
import { toast } from "@/components/ui/sonner";
import { ArrowLeft, Plus, Check, UtensilsCrossed } from "lucide-react";

const fmt = (n) => `${n.toFixed(2)} PLN`;

const CATEGORIES = ["All", "Burgers", "Sides", "Drinks", "Coffee"];

const MENU_ITEMS = [
  { id: "smash-burger", name: "Smash Burger", price: 42, category: "Burgers", desc: "Double smashed patty, cheddar, pickles, house sauce" },
  { id: "truffle-fries", name: "Truffle Fries", price: 19, category: "Sides", desc: "Parmesan, truffle oil, sea salt" },
  { id: "craft-ipa", name: "Craft IPA", price: 22, category: "Drinks", desc: "Local hazy IPA, 0.5L" },
  { id: "flat-white", name: "Flat White", price: 16, category: "Coffee", desc: "Double ristretto, silky milk" },
  { id: "cheese-burger", name: "Classic Cheeseburger", price: 38, category: "Burgers", desc: "Beef, cheddar, lettuce, tomato" },
  { id: "onion-rings", name: "Onion Rings", price: 15, category: "Sides", desc: "Buttermilk batter, chipotle mayo" },
  { id: "lemonade", name: "Homemade Lemonade", price: 14, category: "Drinks", desc: "Mint, cucumber, sparkling" },
  { id: "espresso", name: "Espresso", price: 10, category: "Coffee", desc: "Single origin, double shot" },
];

const fadeUp = (delay = 0) => ({
  initial: { opacity: 0, y: 12 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.4, delay, ease: [0.16, 1, 0.3, 1] },
});

export default function MenuView({ billItems, onAdd, onBack }) {
  const [category, setCategory] = useState("All");
  const [added, setAdded] = useState(() => new Set(billItems.map((i) => i.id)));

  const items = category === "All" ? MENU_ITEMS : MENU_ITEMS.filter((i) => i.category === category);

  const add = (item) => {
    onAdd(item);
    setAdded((prev) => new Set(prev).add(item.id));
    toast.success(`${item.name} added to bill`);
  };

  return (
    <div className="max-w-md mx-auto min-h-screen bg-[#f8f9fa] shadow-2xl relative border-x border-slate-200/60 flex flex-col" data-testid="menu-view">
      <header className="sticky top-0 z-30 bg-[#f8f9fa]/90 backdrop-blur-md px-5 py-3.5 border-b border-slate-200/80">
        <nav className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-slate-900 flex items-center justify-center">
              <UtensilsCrossed className="w-4 h-4 text-white" aria-hidden="true" />
            </div>
            <span className="font-bold tracking-tight text-base text-slate-900">Menu</span>
          </div>
          <button
            type="button"
            onClick={onBack}
            data-testid="back-to-bill-button"
            className="flex items-center gap-1 text-xs font-medium text-slate-600 bg-white border border-slate-200 px-2.5 py-1 rounded-full hover:bg-slate-50 transition-colors"
          >
            <ArrowLeft className="w-3.5 h-3.5" /> Back to Bill
          </button>
        </nav>
      </header>

      <main className="px-4 py-5 space-y-4 flex-1 pb-8">
        <div className="flex gap-2 overflow-x-auto pb-1 -mx-4 px-4" data-testid="menu-categories">
          {CATEGORIES.map((c) => (
            <button
              key={c}
              type="button"
              onClick={() => setCategory(c)}
              data-testid={`menu-cat-${c.toLowerCase()}`}
              className={`shrink-0 px-3.5 py-1.5 rounded-full text-xs font-bold transition-colors ${
                category === c ? "bg-slate-900 text-white" : "bg-white border border-slate-200 text-slate-600"
              }`}
            >
              {c}
            </button>
          ))}
        </div>

        <div className="space-y-3">
          {items.map((item, i) => {
            const isAdded = added.has(item.id);
            return (
              <motion.div
                key={item.id}
                {...fadeUp(i * 0.05)}
                className="bg-white rounded-2xl p-4 border border-slate-100 shadow-sm flex items-center justify-between gap-3"
                data-testid={`menu-item-${item.id}`}
              >
                <div className="min-w-0">
                  <p className="text-sm font-bold text-slate-900">{item.name}</p>
                  <p className="text-xs text-slate-500 truncate mt-0.5">{item.desc}</p>
                  <p className="text-sm font-bold tabular-nums text-slate-900 mt-1">{fmt(item.price)}</p>
                </div>
                <button
                  type="button"
                  onClick={() => add(item)}
                  disabled={isAdded}
                  data-testid={`add-item-${item.id}`}
                  className={`shrink-0 w-9 h-9 rounded-full flex items-center justify-center transition-all active:scale-90 ${
                    isAdded ? "bg-emerald-100 text-emerald-600" : "bg-slate-900 text-white"
                  }`}
                  aria-label={`Add ${item.name}`}
                >
                  {isAdded ? <Check className="w-4 h-4" /> : <Plus className="w-4 h-4" />}
                </button>
              </motion.div>
            );
          })}
        </div>
      </main>
    </div>
  );
}