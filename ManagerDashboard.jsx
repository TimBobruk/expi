import { useState } from "react";
import { motion } from "framer-motion";
import { toast } from "@/components/ui/sonner";
import { Switch } from "@/components/ui/switch";
import { LayoutDashboard, TrendingUp, Clock, ShieldAlert, Coins, ArrowLeft } from "lucide-react";

const fmt = (n) => `${n.toLocaleString("pl-PL")} PLN`;

const TABLES = [
  { id: "t1", n: 1, status: "paid", bill: 112, guests: 2 },
  { id: "t2", n: 2, status: "roulette", bill: 96, guests: 4 },
  { id: "t3", n: 3, status: "split", bill: 148, guests: 3 },
  { id: "t4", n: 4, status: "occupied", bill: 184, guests: 2 },
  { id: "t5", n: 5, status: "occupied", bill: 61, guests: 1 },
  { id: "t6", n: 6, status: "paid", bill: 240, guests: 4 },
  { id: "t7", n: 7, status: "split", bill: 87, guests: 3 },
  { id: "t8", n: 8, status: "occupied", bill: 129, guests: 2 },
];

const STATUS = {
  paid: { label: "Paid via QR - Ready to clear", chip: "bg-emerald-100 text-emerald-700 border-emerald-200", dot: "bg-emerald-500" },
  roulette: { label: "🎰 Playing Bill Roulette right now!", chip: "bg-violet-100 text-violet-700 border-violet-200", dot: "bg-violet-500" },
  split: { label: "Splitting bill (3 guests active)", chip: "bg-amber-100 text-amber-700 border-amber-200", dot: "bg-amber-500" },
  occupied: { label: "Occupied - Active bill", chip: "bg-sky-100 text-sky-700 border-sky-200", dot: "bg-sky-500" },
};

const STAFF = [
  { name: "Alex", tips: 214, goal: 500, goalName: "Trip to Lisbon", color: "bg-indigo-100 text-indigo-700" },
  { name: "Maja", tips: 168, goal: 300, goalName: "New camera", color: "bg-rose-100 text-rose-700" },
  { name: "Tomek", tips: 96, goal: 250, goalName: "Concert tickets", color: "bg-amber-100 text-amber-700" },
];

const MENU_STOCK = [
  { id: "smash-burger", name: "Smash Burger", price: 42 },
  { id: "cheese-burger", name: "Classic Cheeseburger", price: 38 },
  { id: "truffle-fries", name: "Truffle Fries", price: 19 },
  { id: "onion-rings", name: "Onion Rings", price: 15 },
  { id: "craft-ipa", name: "Craft IPA", price: 22 },
  { id: "lemonade", name: "Homemade Lemonade", price: 14 },
  { id: "flat-white", name: "Flat White", price: 16 },
  { id: "espresso", name: "Espresso", price: 10 },
];

const fadeUp = (delay = 0) => ({
  initial: { opacity: 0, y: 12 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.4, delay, ease: [0.16, 1, 0.3, 1] },
});

export default function ManagerDashboard({ onBack }) {
  const [soldOut, setSoldOut] = useState(() => new Set());

  const toggleStock = (id) => {
    const item = MENU_STOCK.find((i) => i.id === id);
    setSoldOut((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
        toast.success(`${item.name} back on the menu`);
      } else {
        next.add(id);
        toast.success(`${item.name} marked Sold Out`);
      }
      return next;
    });
  };

  const kpis = [
    { label: "Today's QR Revenue", value: "1,284 PLN", icon: TrendingUp, accent: "text-emerald-600" },
    { label: "Table Turnaround", value: "-14 mins", icon: Clock, accent: "text-sky-600" },
    { label: "Intercepted Bad Reviews", value: "2", icon: ShieldAlert, accent: "text-amber-600" },
    { label: "Waiter Tips Collected", value: "+38%", icon: Coins, accent: "text-violet-600" },
  ];

  return (
    <div className="max-w-md mx-auto min-h-screen bg-[#f8f9fa] shadow-2xl relative border-x border-slate-200/60 flex flex-col" data-testid="manager-view">
      <header className="sticky top-0 z-30 bg-[#f8f9fa]/90 backdrop-blur-md px-5 py-3.5 border-b border-slate-200/80">
        <nav className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-slate-900 flex items-center justify-center">
              <LayoutDashboard className="w-4 h-4 text-white" aria-hidden="true" />
            </div>
            <span className="font-bold tracking-tight text-base text-slate-900">Manager</span>
          </div>
          <button
            type="button"
            onClick={onBack}
            data-testid="back-to-guest-button"
            className="flex items-center gap-1 text-xs font-medium text-slate-600 bg-white border border-slate-200 px-2.5 py-1 rounded-full hover:bg-slate-50 transition-colors"
          >
            <ArrowLeft className="w-3.5 h-3.5" /> Guest View
          </button>
        </nav>
      </header>

      <main className="px-4 py-5 space-y-5 flex-1 pb-8">
        <motion.section {...fadeUp(0)} className="grid grid-cols-2 gap-3" data-testid="kpi-cards">
          {kpis.map((k) => (
            <div key={k.label} className="bg-white rounded-2xl p-4 border border-slate-100 shadow-sm" data-testid={`kpi-${k.label.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`}>
              <div className={`w-8 h-8 rounded-xl bg-slate-100 flex items-center justify-center mb-2 ${k.accent}`}>
                <k.icon className="w-4 h-4" />
              </div>
              <p className="text-xs text-slate-500">{k.label}</p>
              <p className="text-lg font-bold tracking-tight text-slate-900 tabular-nums">{k.value}</p>
            </div>
          ))}
        </motion.section>

        <motion.section {...fadeUp(0.1)} className="bg-white rounded-2xl p-4 border border-slate-100 shadow-sm" data-testid="floor-map">
          <div className="flex items-center justify-between pb-3 border-b border-slate-100 mb-3">
            <h2 className="text-sm font-bold tracking-tight text-slate-900">Live Floor Map</h2>
            <span className="inline-flex items-center gap-1.5 text-[11px] font-semibold text-emerald-600">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" /> Live
            </span>
          </div>
          <div className="grid grid-cols-2 gap-2.5">
            {TABLES.map((t) => {
              const s = STATUS[t.status];
              return (
                <div key={t.id} className={`rounded-xl border p-3 ${s.chip}`} data-testid={`table-${t.n}`}>
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold">Table {t.n}</span>
                    <span className={`w-2 h-2 rounded-full ${s.dot} ${t.status === "roulette" ? "animate-pulse" : ""}`} />
                  </div>
                  <p className="text-[11px] font-medium mt-1 leading-tight">{s.label}</p>
                  <p className="text-[11px] tabular-nums mt-1 opacity-80">{fmt(t.bill)} · {t.guests} guest{t.guests > 1 ? "s" : ""}</p>
                </div>
              );
            })}
          </div>
        </motion.section>

        <motion.section {...fadeUp(0.2)} className="bg-white rounded-2xl p-4 border border-slate-100 shadow-sm space-y-3" data-testid="tips-leaderboard">
          <h2 className="text-sm font-bold tracking-tight text-slate-900">Waiter Tips Leaderboard</h2>
          {STAFF.map((w, i) => {
            const pct = Math.round((w.tips / w.goal) * 100);
            return (
              <div key={w.name} className="flex items-center gap-3" data-testid={`staff-${w.name.toLowerCase()}`}>
                <span className="text-xs font-bold text-slate-400 w-4">{i + 1}</span>
                <span className={`w-9 h-9 rounded-full flex items-center justify-center text-xs font-bold ${w.color}`}>
                  {w.name.slice(0, 2).toUpperCase()}
                </span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between">
                    <p className="text-xs font-bold text-slate-900">{w.name}</p>
                    <p className="text-xs font-semibold text-slate-500 tabular-nums">{fmt(w.tips)} · {pct}%</p>
                  </div>
                  <p className="text-[11px] text-slate-500 truncate">{w.goalName}</p>
                  <div className="w-full bg-slate-100 h-1.5 rounded-full mt-1 overflow-hidden">
                    <div className="bg-amber-500 h-full rounded-full" style={{ width: `${pct}%` }} />
                  </div>
                </div>
              </div>
            );
          })}
        </motion.section>

        <motion.section {...fadeUp(0.3)} className="bg-white rounded-2xl p-4 border border-slate-100 shadow-sm" data-testid="stop-list">
          <div className="flex items-center justify-between pb-3 border-b border-slate-100 mb-2">
            <h2 className="text-sm font-bold tracking-tight text-slate-900">Instant Stop-List</h2>
            <span className="text-[11px] text-slate-400">Toggle = Sold Out</span>
          </div>
          <div className="divide-y divide-slate-100">
            {MENU_STOCK.map((m) => {
              const off = soldOut.has(m.id);
              return (
                <div key={m.id} className="flex items-center justify-between py-2.5" data-testid={`stock-${m.id}`}>
                  <div>
                    <p className={`text-sm font-semibold ${off ? "text-slate-400 line-through" : "text-slate-900"}`}>{m.name}</p>
                    <p className="text-[11px] text-slate-400 tabular-nums">{fmt(m.price)}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    {off && <span className="text-[10px] font-bold uppercase tracking-wider text-rose-600 bg-rose-50 px-1.5 py-0.5 rounded">Sold out</span>}
                    <Switch checked={!off} onCheckedChange={() => toggleStock(m.id)} data-testid={`stock-toggle-${m.id}`} />
                  </div>
                </div>
              );
            })}
          </div>
        </motion.section>
      </main>
    </div>
  );
}