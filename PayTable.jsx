import "@/App.css";
import { BrowserRouter, Routes, Route, useNavigate } from "react-router-dom";
import PayTable from "@/pages/PayTable";
import ManagerDashboard from "@/pages/ManagerDashboard";
import { Toaster } from "@/components/ui/sonner";

function AdminRoute() {
  const navigate = useNavigate();
  return <ManagerDashboard onBack={() => navigate("/")} />;
}

function App() {
  return (
    <div className="App">
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<PayTable />} />
          <Route path="/admin" element={<AdminRoute />} />
        </Routes>
      </BrowserRouter>
      <Toaster position="top-center" richColors />
    </div>
  );
}

export default App;
/app/frontend/src/pages/PayTable.jsx (lines 1–260 shown above; remaining 818 lines below)
import { useState, useMemo, useEffect, useRef, useCallback } from "react";

import axios from "axios";
import { motion, AnimatePresence } from "framer-motion";
import { Checkbox } from "@/components/ui/checkbox";
import { Avatar, AvatarImage, AvatarFallback } from "@/components/ui/avatar";
import { Progress } from "@/components/ui/progress";
import {
  Drawer,
  DrawerContent,
  DrawerHeader,
  DrawerTitle,
  DrawerDescription,
  DrawerFooter,
} from "@/components/ui/drawer";
import { toast } from "@/components/ui/sonner";
import { Apple, UtensilsCrossed, CheckCircle2, Loader2, Minus, Plus, X, Zap, Download, Star, Camera } from "lucide-react";
import MenuView from "@/pages/Menu";
import ManagerDashboard from "@/pages/ManagerDashboard";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const WAITER_PHOTO =
  "https://images.unsplash.com/photo-1647483684830-7ddde27dcf4d?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NTYxOTB8MHwxfHNlYXJjaHwzfHxwb3J0cmFpdCUyMHdhaXRlciUyMHNtaWxpbmd8ZW58MHx8fHwxNzk0NTk3OTgyfDA&ixlib=rb-4.1.0&q=85";

const INITIAL_BILL_ITEMS = [
  { id: "smash-burger", name: "Smash Burger", price: 42, diners: [{ label: "You", bg: "bg-indigo-100 text-indigo-700" }, { label: "AK", bg: "bg-rose-100 text-rose-700" }] },
  { id: "craft-ipa", name: "Craft IPA", price: 22, diners: [{ label: "You", bg: "bg-indigo-100 text-indigo-700" }] },
  { id: "truffle-fries", name: "Truffle Fries", price: 19, diners: [{ label: "M", bg: "bg-amber-100 text-amber-700" }] },
  { id: "flat-white", name: "Flat White", price: 16, diners: [{ label: "SZ", bg: "bg-emerald-100 text-emerald-700" }] },
];

const PAY_MODES = [
  { id: "mine", label: "My Items" },
  { id: "equal", label: "Split Equal" },
  { id: "full", label: "Full Bill" },
  { id: "roulette", label: "🎰 Roulette", roulette: true },
];

const TIP_OPTIONS = [0, 5, 10, 15];
const PLATFORM_FEE = 1.5;
const DRINKS_ROUND_PRICE = 22; // one round: a Craft IPA for each guest

const ROULETTE_STAKES = [
  { id: "all", label: "Loser Pays All 💀" },
  { id: "drinks", label: "Loser Pays the Round 🍺" },
  { id: "items", label: "Loser Pays Picks 🎯" },
];

const INITIAL_GUESTS = ["You", "Marta", "Kuba", "Alex"];

const AVATAR_STYLES = [
  "bg-indigo-100 text-indigo-700",
  "bg-rose-100 text-rose-700",
  "bg-amber-100 text-amber-700",
  "bg-emerald-100 text-emerald-700",
  "bg-sky-100 text-sky-700",
  "bg-fuchsia-100 text-fuchsia-700",
];

const initials = (name) => (name === "You" ? "You" : name.slice(0, 2).toUpperCase());

const CONFETTI = Array.from({ length: 16 }, (_, i) => ({
  id: i,
  x: (Math.random() - 0.5) * 220,
  y: -(40 + Math.random() * 120),
  r: Math.random() * 360,
  delay: Math.random() * 0.25,
  e: ["🎉", "🎊", "✨", "🍾"][i % 4],
}));

const fmt = (n) => `${n.toFixed(2)} PLN`;

const fadeUp = (delay = 0) => ({
  initial: { opacity: 0, y: 12 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.5, delay, ease: [0.16, 1, 0.3, 1] },
});

export default function PayTable() {
  const [selected, setSelected] = useState(() => new Set(["smash-burger", "craft-ipa"]));
  const [payMode, setPayMode] = useState("mine");
  const [view, setView] = useState("bill"); // bill | menu
  const [billItems, setBillItems] = useState(INITIAL_BILL_ITEMS);
  const [showMenu, setShowMenu] = useState(false);
  const [showManager, setShowManager] = useState(false);

  const addToBill = (item) => {
    setBillItems((prev) => {
      const exists = prev.find((i) => i.id === item.id);
      if (exists) return prev;
      return [...prev, { ...item, diners: [{ label: "You", bg: "bg-indigo-100 text-indigo-700" }] }];
    });
    setSelected((prev) => new Set(prev).add(item.id));
  };
  const [tipPercent, setTipPercent] = useState(10);
  const [paying, setPaying] = useState(null); // 'apple_pay' | 'blik' | null
  const [receipt, setReceipt] = useState(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [stars, setStars] = useState(0);
  const [feedback, setFeedback] = useState("");
  const [feedbackSent, setFeedbackSent] = useState(false);
  const [thanks, setThanks] = useState(false);
  const [voucherSent, setVoucherSent] = useState(false);

  // --- feature state ---
  const [simulateFriend, setSimulateFriend] = useState(false);
  const [martaOnIpa, setMartaOnIpa] = useState(false);
  const [people, setPeople] = useState(4);
  const [guests, setGuests] = useState(INITIAL_GUESTS);
  const [rouletteStake, setRouletteStake] = useState("all"); // all | drinks | items
  const [roulettePickItems, setRoulettePickItems] = useState(() => new Set(["craft-ipa"]));
  const [spinning, setSpinning] = useState(false);
  const [spinIndex, setSpinIndex] = useState(0);
  const [loser, setLoser] = useState(null);
  const [confettiKey, setConfettiKey] = useState(0);
  const [newGuest, setNewGuest] = useState("");
  const [paidViaRoulette, setPaidViaRoulette] = useState(null); // {loser, total, method, stakeLabel} | null
  const spinTimers = useRef([]);

  const billTotal = useMemo(() => billItems.reduce((s, i) => s + i.price, 0), [billItems]);
  const drinksTotal = DRINKS_ROUND_PRICE * guests.length;
  const roulettePicksTotal = useMemo(
    () => billItems.filter((i) => roulettePickItems.has(i.id)).reduce((s, i) => s + i.price, 0),
    [billItems, roulettePickItems]
  );

  // Marta selects Craft IPA a moment after simulation is toggled on
  useEffect(() => {
    if (!simulateFriend) {
      setMartaOnIpa(false);
      return;
    }
    const t = setTimeout(() => setMartaOnIpa(true), 1200);
    return () => clearTimeout(t);
  }, [simulateFriend]);

  useEffect(() => () => spinTimers.current.forEach(clearTimeout), []);

  const subtotal = useMemo(() => {
    if (payMode === "full" || payMode === "roulette") return billTotal;
    if (payMode === "equal") return billTotal / people;
    return billItems.filter((i) => selected.has(i.id)).reduce((s, i) => s + i.price, 0);
  }, [payMode, selected, billTotal, people, billItems]);

  const selectedCount = useMemo(() => {
    if (payMode === "mine") return selected.size;
    return billItems.length;
  }, [payMode, selected, billItems]);

  const tipAmount = (subtotal * tipPercent) / 100;
  const rawTotal = subtotal + tipAmount;
  const rouletteStakeTotal =
    rouletteStake === "drinks"
      ? drinksTotal
      : rouletteStake === "items"
        ? roulettePicksTotal + tipAmount
        : rawTotal;
  const total = payMode === "roulette" && paidViaRoulette ? paidViaRoulette.total - PLATFORM_FEE : payMode === "roulette" ? rouletteStakeTotal : rawTotal;
  const payTotal = payMode === "roulette" && paidViaRoulette ? paidViaRoulette.total : total + PLATFORM_FEE;

  const toggleItem = (id) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const addGuest = () => {
    const name = newGuest.trim();
    if (!name || guests.includes(name) || guests.length >= 6) return;
    setGuests((g) => [...g, name]);
    setNewGuest("");
  };

  const removeGuest = (name) => {
    if (guests.length <= 2) return;
    setGuests((g) => g.filter((x) => x !== name));
    setLoser((l) => (l === name ? null : l));
  };

  const spinWheel = useCallback(() => {
    if (spinning || paidViaRoulette || guests.length < 2) return;
    setLoser(null);
    setSpinning(true);
    spinTimers.current.forEach(clearTimeout);
    spinTimers.current = [];

    const target = Math.floor(Math.random() * guests.length);
    const steps = 20 + Math.floor(Math.random() * guests.length);
    let i = 0;
    let delay = 50;
    let elapsed = 0;
    const DURATION = 3000;

    while (i < steps && elapsed + delay <= DURATION - 350) {
      const idx = i;
      spinTimers.current.push(setTimeout(() => setSpinIndex(idx % guests.length), elapsed));
      elapsed += delay;
      delay = Math.min(delay * 1.16, 380);
      i += 1;
    }
    spinTimers.current.push(
      setTimeout(() => {
        setSpinIndex(target);
        setSpinning(false);
        setLoser(guests[target]);
        setConfettiKey((k) => k + 1);
      }, DURATION)
    );
  }, [spinning, guests, paidViaRoulette]);

  const handlePay = async (method) => {
    if (payMode === "roulette" && !paidViaRoulette && !loser) {
      toast.error("Spin first!", { description: "The wheel decides who pays. Hit SPIN THE WHEEL!" });
      return;
    }
    if (payMode === "roulette" && paidViaRoulette) {
      toast.success("Already paid", { description: `${paidViaRoulette.loser} covered the ${paidViaRoulette.stakeLabel}.` });
      return;
    }
    if (total <= 0) {
      toast.error("Nothing to pay", { description: "Select at least one item or switch pay mode." });
      return;
    }
    setPaying(method);
    try {
      const { data } = await axios.post(`${API}/checkouts`, {
        table_number: "Table #12",
        pay_mode: payMode,
        payment_method: method,
        tip_percent: tipPercent,
        items: billItems.map((i) => ({
          name: i.name,
          price: i.price,
          selected: payMode === "mine" ? selected.has(i.id) : true,
        })),
        subtotal: Number(subtotal.toFixed(2)),
        tip_amount: Number(tipAmount.toFixed(2)),
        total: Number(payTotal.toFixed(2)),
      });
      const rouletteResult = payMode === "roulette" ? loser : null;
      setReceipt({ ...data, roulette_loser: rouletteResult, platform_fee: PLATFORM_FEE });
      if (payMode === "roulette") {
        setPaidViaRoulette({
          loser,
          total: payTotal,
          method,
          stakeLabel: rouletteStake === "drinks" ? "round of drinks" : rouletteStake === "items" ? "picks" : "bill",
        });
      }
      setStars(0);
      setFeedback("");
      setFeedbackSent(false);
      setThanks(false);
      setVoucherSent(false);
      setProcessing(true);
      setDrawerOpen(true);
      setTimeout(() => setProcessing(false), 1000);
    } catch (e) {
      console.error(e);
      toast.error("Payment failed", { description: "Could not complete checkout. Try again." });
    } finally {
      setPaying(null);
    }
  };

  const selectPayMode = (m) => {
    setPayMode(m);
    if (m !== "roulette") setPaidViaRoulette(null);
  };

  const summaryLabel =
    payMode === "mine"
      ? `Selected Items (${selectedCount})`
      : payMode === "equal"
        ? `Split Equally (${people} guests)`
        : payMode === "roulette"
          ? paidViaRoulette
            ? paidViaRoulette.stakeLabel === "round of drinks"
              ? `Round of Drinks — paid by ${paidViaRoulette.loser}`
              : paidViaRoulette.stakeLabel === "picks"
                ? `Picks — paid by ${paidViaRoulette.loser}`
                : `Full Bill — paid by ${paidViaRoulette.loser}`
            : rouletteStake === "drinks"
              ? `Round of Drinks (${guests.length} guests)`
              : rouletteStake === "items"
                ? `Roulette Picks (${roulettePickItems.size} items)`
                : "Full Bill — Roulette"
          : "Full Bill (4 items)";

  return (
    <div className="bg-[#f8f9fa] min-h-screen" data-testid="paytable-page">
      {showManager ? (
        <ManagerDashboard onBack={() => setShowManager(false)} />
      ) : showMenu ? (
        <MenuView billItems={billItems} onAdd={addToBill} onBack={() => setShowMenu(false)} />
      ) : (
        <div className="max-w-md mx-auto min-h-screen bg-[#f8f9fa] shadow-2xl relative border-x border-slate-200/60 flex flex-col">
          {/* Header */}
          <header className="sticky top-0 z-30 bg-[#f8f9fa]/90 backdrop-blur-md px-5 py-3.5 border-b border-slate-200/80" data-testid="app-header">
            <nav className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="w-7 h-7 rounded-lg bg-slate-900 flex items-center justify-center">
                  <UtensilsCrossed className="w-4 h-4 text-white" aria-hidden="true" />
                </div>
                <span className="font-bold tracking-tight text-base text-slate-900" data-testid="app-name">
                  PayTable
                </span>
              </div>
              <div className="flex items-center gap-2">
                <span
                  className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200/60"
                  data-testid="table-badge"
                >
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                  Table #12
                </span>
                <button
                  type="button"
                  onClick={() => setShowMenu(true)}
                  className="text-xs font-medium text-slate-600 bg-white border border-slate-200 px-2.5 py-1 rounded-full hover:bg-slate-50 transition-colors"
                  data-testid="view-menu-button"
                >
                  Menu
                </button>
                <button
                  type="button"
                  onClick={() => setShowManager(true)}
                  className="text-xs font-bold text-white bg-slate-900 px-2.5 py-1 rounded-full hover:bg-slate-800 transition-colors"
                  data-testid="switch-to-manager-button"
                >
                  Manager
                </button>
              </div>
            </nav>
          </header>

          {/* Demo switcher */}
          <div className="sticky top-[57px] z-20 bg-[#f8f9fa]/90 backdrop-blur-md px-5 py-2 border-b border-slate-200/60 flex items-center justify-between" data-testid="demo-switcher">
            <span className="text-[10px] font-bold uppercase tracking-widest text-slate-400">Demo View</span>
            <div className="flex items-center gap-1 bg-white border border-slate-200 rounded-full p-0.5">
              {[
                { id: "guest", label: "Guest" },
                { id: "manager", label: "Manager" },
                { id: "landing", label: "B2B Landing" },
              ].map((v) => (
                <button
                  key={v.id}
                  type="button"
                  onClick={() => (v.id === "manager" ? setShowManager(true) : null)}
                  data-testid={`view-${v.id}`}
                  className={`px-3 py-1 rounded-full text-[11px] font-bold transition-colors ${
                    v.id === "guest" && !showManager ? "bg-slate-900 text-white" : "text-slate-600"
                  }`}
                >
                  {v.label}
                </button>
              ))}
            </div>
          </div>

          {/* Simulate friend floating toggle */}
          <button
            type="button"
            onClick={() => setSimulateFriend((s) => !s)}
            data-testid="simulate-friend-toggle"
            className={`fixed bottom-28 right-4 z-50 flex items-center gap-1.5 px-3.5 py-2 rounded-full text-xs font-bold shadow-lg transition-colors ${
              simulateFriend ? "bg-slate-900 text-white" : "bg-white text-slate-700 border border-slate-200"
            }`}
          >
            <Zap className={`w-3.5 h-3.5 ${simulateFriend ? "text-amber-400 fill-amber-400" : ""}`} aria-hidden="true" />
            Simulate Friend
          </button>

          {/* Main */}
          <main className="px-4 py-5 space-y-5 flex-1 pb-8">
            {/* Hero + mode selector */}
            <motion.section
              className="bg-white rounded-2xl p-5 border border-slate-100 shadow-sm"
              data-testid="restaurant-hero"
              {...fadeUp(0)}
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wider text-slate-400" data-testid="restaurant-name">
                    Craft Burger &amp; Bar
                  </p>
                  <h1 className="text-2xl font-bold tracking-tight text-slate-900 mt-1">Split &amp; Pay Bill</h1>
                  <p className="text-xs text-slate-500 mt-1">Tap items to pay your share or split evenly with table.</p>
                </div>
                <div className="w-12 h-12 rounded-2xl bg-amber-50 border border-amber-200 flex items-center justify-center shrink-0 text-amber-700 font-bold text-lg" aria-hidden="true">
                  🍔
                </div>
              </div>

              <div className="mt-4 p-1 bg-slate-100 rounded-xl grid grid-cols-4 gap-1 text-center font-medium text-xs text-slate-600" role="radiogroup" data-testid="pay-mode-selector">
                {PAY_MODES.map((m) => {
                  const active = payMode === m.id;
                  return (
                    <button
                      key={m.id}
                      type="button"
                      role="radio"
                      aria-checked={active}
                      onClick={() => selectPayMode(m.id)}
                      data-testid={`pay-mode-${m.id}`}
                      className={`relative py-2 rounded-lg transition-colors ${
                        active ? "bg-slate-900 text-white shadow-md" : "hover:bg-slate-200/70"
                      } ${m.roulette ? "shadow-[0_0_14px_rgba(245,158,11,0.45)]" : ""}`}
                    >
                      {m.label}
                    </button>
                  );
                })}
              </div>

              {/* Split equally people counter */}
              {payMode === "equal" && (
                <motion.div
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="mt-3 flex items-center justify-between bg-slate-50 border border-slate-200/80 rounded-xl px-3 py-2.5"
                  data-testid="people-counter"
                >
                  <span className="text-xs font-semibold text-slate-600">Guests splitting</span>
                  <div className="flex items-center gap-3">
                    <button
                      type="button"
                      onClick={() => setPeople((p) => Math.max(2, p - 1))}
                      disabled={people <= 2}
                      data-testid="people-minus"
                      className="w-8 h-8 rounded-full bg-white border border-slate-200 flex items-center justify-center text-slate-700 disabled:opacity-40 active:scale-95 transition-transform"
                    >
                      <Minus className="w-4 h-4" />
                    </button>
                    <span className="text-base font-bold tabular-nums text-slate-900 w-5 text-center" data-testid="people-count">
                      {people}
                    </span>
                    <button
                      type="button"
                      onClick={() => setPeople((p) => Math.min(8, p + 1))}
                      disabled={people >= 8}
                      data-testid="people-plus"
                      className="w-8 h-8 rounded-full bg-white border border-slate-200 flex items-center justify-center text-slate-700 disabled:opacity-40 active:scale-95 transition-transform"
                    >
                      <Plus className="w-4 h-4" />
                    </button>
                  </div>
                  <span className="text-xs font-bold tabular-nums text-slate-900" data-testid="per-person-amount">
                    {fmt(billTotal / people)} <span className="font-normal text-slate-500">each</span>
                  </span>
                </motion.div>
              )}
            </motion.section>

            {/* Bill items */}
            <motion.section
              className="bg-white rounded-2xl p-4 border border-slate-100 shadow-sm"
              data-testid="bill-items-section"
              {...fadeUp(0.15)}
            >
              <div className="flex items-center justify-between pb-3 border-b border-slate-100">
                <h2 className="text-sm font-bold tracking-tight text-slate-900">
                  Ordered Items ({billItems.length})
                </h2>
                <span className="text-xs text-slate-400" data-testid="friends-active-label">
                  3 friends active
                </span>
              </div>

              <div className="divide-y divide-slate-100 mt-1">
                {billItems.map((item) => {
                  const disabled = payMode !== "mine";
                  const checked = payMode === "mine" ? selected.has(item.id) : true;
                  const martaHere = martaOnIpa && item.id === "craft-ipa" && !item.diners.some((d) => d.label === "M");
                  const diners = martaHere ? [...item.diners, { label: "M", bg: "bg-amber-100 text-amber-700" }] : item.diners;
                  return (
                    <div
                      key={item.id}
                      className={`flex items-center justify-between py-3 group ${disabled ? "opacity-50" : "cursor-pointer"}`}
                      data-testid={`bill-item-${item.id}`}
                      onClick={() => !disabled && toggleItem(item.id)}
                    >
                      <div className="flex items-center gap-3">
                        <span onClick={(e) => e.stopPropagation()}>
                          <Checkbox
                            checked={checked}
                            onCheckedChange={() => toggleItem(item.id)}
                            disabled={disabled}
                            className="w-5 h-5 rounded-md data-[state=checked]:bg-slate-900 data-[state=checked]:border-slate-900"
                            data-testid={`bill-item-checkbox-${item.id}`}
                          />
                        </span>
                        <div>
                          <p className="text-sm font-semibold text-slate-800 group-hover:text-black transition-colors">
                            {item.name}
                          </p>
                          <div className="flex items-center gap-1.5 mt-0.5">
                            {diners.map((d) => (
                              <span
                                key={d.label}
                                className={`inline-flex items-center justify-center w-5 h-5 rounded-full text-[10px] font-bold ${d.bg}`}
                              >
                                {d.label}
                              </span>
                            ))}
                            {martaHere && (
                              <motion.span
                                initial={{ opacity: 0, x: -6 }}
                                animate={{ opacity: 1, x: 0 }}
                                className="text-[10px] font-semibold text-amber-600"
                                data-testid="marta-selecting-label"
                              >
                                Marta is picking...
                              </motion.span>
                            )}
                          </div>
                        </div>
                      </div>
                      <span className="font-semibold text-sm tabular-nums text-slate-900">{item.price} PLN</span>
                    </div>
                  );
                })}
              </div>
            </motion.section>

            {/* Bill Roulette */}
            {payMode === "roulette" && (
              <motion.section
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
                className="bg-white rounded-2xl p-4 border border-amber-200/70 shadow-[0_0_24px_rgba(245,158,11,0.15)] space-y-3"
                data-testid="roulette-section"
              >
                <div className="flex items-center justify-between">
                  <h2 className="text-sm font-bold tracking-tight text-slate-900">Bill Roulette</h2>
                  <span className="text-[10px] font-bold uppercase tracking-wider text-amber-700 bg-amber-50 border border-amber-200 px-2 py-0.5 rounded-full shadow-[0_0_10px_rgba(245,158,11,0.35)]">
                    🎰 High stakes
                  </span>
                </div>

                {/* Stake sub-modes */}
                <div className="grid grid-cols-3 gap-2" role="radiogroup" data-testid="roulette-stake-selector">
                  {ROULETTE_STAKES.map((s) => {
                    const active = rouletteStake === s.id;
                    return (
                      <button
                        key={s.id}
                        type="button"
                        role="radio"
                        aria-checked={active}
                        disabled={paidViaRoulette !== null}
                        onClick={() => setRouletteStake(s.id)}
                        data-testid={`roulette-stake-${s.id}`}
                        className={`py-2 rounded-xl border text-xs font-semibold transition-colors disabled:opacity-50 ${
                          active ? "bg-slate-900 text-white border-slate-900" : "border-slate-200 text-slate-700 hover:bg-slate-50"
                        }`}
                      >
                        {s.label}
                      </button>
                    );
                  })}
                </div>

                {/* Picks checklist (items stake) */}
                {rouletteStake === "items" && (
                  <div className="rounded-xl border border-slate-200 divide-y divide-slate-100" data-testid="roulette-picks">
                    <p className="px-3 pt-2.5 pb-1.5 text-[11px] font-bold uppercase tracking-wider text-slate-400">
                      Loser pays for these picks
                    </p>
                    {billItems.map((item) => {
                      const checked = roulettePickItems.has(item.id);
                      return (
                        <button
                          key={item.id}
                          type="button"
                          disabled={paidViaRoulette !== null}
                          onClick={() => setRoulettePickItems((prev) => { const n = new Set(prev); if (n.has(item.id)) n.delete(item.id); else n.add(item.id); return n; })}
                          data-testid={`pick-${item.id}`}
                          className="w-full flex items-center justify-between px-3 py-2.5 text-left disabled:opacity-50"
                        >
                          <span className="flex items-center gap-2.5">
                            <span className={`w-4 h-4 rounded-md border flex items-center justify-center ${checked ? "bg-slate-900 border-slate-900" : "border-slate-300"}`}>
                              {checked && <CheckCircle2 className="w-3 h-3 text-white" />}
                            </span>
                            <span className="text-xs font-semibold text-slate-800">{item.name}</span>
                          </span>
                          <span className="text-xs font-semibold tabular-nums text-slate-900">{item.price} PLN</span>
                        </button>
                      );
                    })}
                    <p className="px-3 py-2 text-[11px] text-slate-500">
                      Selected picks total: <span className="font-bold text-slate-900">{fmt(roulettePicksTotal)}</span>
                    </p>
                  </div>
                )}

                {/* Slot-machine strip */}
                <div className="relative overflow-hidden rounded-2xl bg-slate-900 py-3" data-testid="roulette-strip">
                  <div className="pointer-events-none absolute inset-y-0 left-0 w-10 z-10 bg-gradient-to-r from-slate-900 to-transparent" />
                  <div className="pointer-events-none absolute inset-y-0 right-0 w-10 z-10 bg-gradient-to-l from-slate-900 to-transparent" />
                  <div className="flex gap-2 overflow-hidden px-4">
                    {Array.from({ length: Math.max(4, guests.length) }, (_, i) => {
                      const g = guests[i % guests.length];
                      const active = spinning
                        ? i % guests.length === spinIndex % guests.length
                        : loser
                          ? g === loser && i % guests.length === guests.indexOf(loser)
                          : false;
                      const isPaidLoser = paidViaRoulette && g === paidViaRoulette.loser && i % guests.length === guests.indexOf(paidViaRoulette.loser);
                      return (
                        <div
                          key={`${g}-${i}`}
                          className={`shrink-0 flex items-center gap-1.5 px-3 py-2 rounded-full text-xs font-bold transition-all duration-100 ${
                            isPaidLoser
                              ? "bg-emerald-400 text-slate-900 scale-110"
                              : active
                                ? "bg-amber-400 text-slate-900 scale-110"
                                : "bg-slate-800 text-slate-400"
                          }`}
                        >
                          <span
                            className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] ${AVATAR_STYLES[i % AVATAR_STYLES.length]}`}
                          >
                            {initials(g)}
                          </span>
                          {g}
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Guest chips: add / remove */}
                <div className="flex flex-wrap gap-1.5" data-testid="guest-chips">
                  {guests.map((g, i) => (
                    <span
                      key={g}
                      className="inline-flex items-center gap-1.5 pl-1 pr-2 py-1 rounded-full bg-slate-100 border border-slate-200 text-xs font-semibold text-slate-700"
                    >
                      <span className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold ${AVATAR_STYLES[i % AVATAR_STYLES.length]}`}>
                        {initials(g)}
                      </span>
                      {g}
                      {guests.length > 2 && (
                        <button
                          type="button"
                          onClick={() => removeGuest(g)}
                          data-testid={`remove-guest-${g.toLowerCase()}`}
                          className="text-slate-400 hover:text-rose-500 transition-colors"
                          aria-label={`Remove ${g}`}
                        >
                          <X className="w-3 h-3" />
                        </button>
                      )}
                    </span>
                  ))}
                </div>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={newGuest}
                    onChange={(e) => setNewGuest(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && addGuest()}
                    placeholder="Add a guest..."
                    maxLength={12}
                    data-testid="add-guest-input"
                    className="flex-1 min-w-0 px-3 py-2 rounded-xl border border-slate-200 text-xs font-medium text-slate-800 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-slate-900/20"
                  />
                  <button
                    type="button"
                    onClick={addGuest}
                    disabled={!newGuest.trim() || guests.length >= 6}
                    data-testid="add-guest-button"
                    className="px-3 py-2 rounded-xl bg-slate-100 border border-slate-200 text-xs font-bold text-slate-700 disabled:opacity-40 active:scale-95 transition-transform"
                  >
                    Add
                  </button>
                </div>

                {/* Spin button / paid state */}
                {paidViaRoulette ? (
                  <div
                    className="w-full py-3.5 rounded-2xl bg-emerald-500 text-white font-black text-sm tracking-wide text-center"
                    data-testid="roulette-paid-banner"
                  >
                    ✅ {paidViaRoulette.loser} paid {fmt(paidViaRoulette.total)} — table covered!
                  </div>
                ) : (
                  <motion.button
                    type="button"
                    whileTap={{ scale: 0.97 }}
                    onClick={spinWheel}
                    disabled={spinning}
                    data-testid="spin-button"
                    className="w-full py-3.5 rounded-2xl bg-gradient-to-r from-amber-400 to-rose-500 text-white font-black text-sm tracking-wide shadow-lg shadow-amber-500/30 disabled:opacity-70 transition-transform"
                  >
                    {spinning ? "SPINNING..." : "🎰 SPIN THE WHEEL!"}
                  </motion.button>
                )}

                {/* Result + confetti */}
                <AnimatePresence>
                  {loser && !spinning && (
                    <motion.div
                      key={confettiKey}
                      initial={{ opacity: 0, scale: 0.8 }}
                      animate={{ opacity: 1, scale: 1 }}
                      exit={{ opacity: 0 }}
                      className="relative text-center pt-1"
                      data-testid="roulette-result"
                    >
                      {CONFETTI.map((c) => (
                        <motion.span
                          key={c.id}
                          className="absolute left-1/2 top-0 text-sm"
                          initial={{ opacity: 1, x: 0, y: 0, rotate: 0 }}
                          animate={{
                            opacity: [1, 1, 0],
                            x: c.x,
                            y: [0, c.y, c.y + 40],
                            rotate: c.r,
                          }}
                          transition={{ duration: 1.4, delay: c.delay, ease: "easeOut" }}
                          aria-hidden="true"
                        >
                          {c.e}
                        </motion.span>
                      ))}
                      <p className="text-base font-black text-slate-900">
                        🎉 {loser} pays {rouletteStake === "drinks" ? "the round of drinks" : rouletteStake === "items" ? "the picks" : "the bill"}!
                      </p>
                      <p className="text-xs font-semibold text-slate-500 mt-0.5" data-testid="roulette-result-amount">
                        ({fmt(total)})
                      </p>
                    </motion.div>
                  )}
                </AnimatePresence>
              </motion.section>
            )}

            {/* Waiter tip */}
            <motion.section
              className="bg-white rounded-2xl p-4 border border-slate-100 shadow-sm space-y-3"
              data-testid="waiter-tip-card"
              {...fadeUp(0.3)}
            >
              <div className="flex items-center gap-3">
                <Avatar className="w-12 h-12 border border-slate-200">
                  <AvatarImage src={WAITER_PHOTO} alt="Alex, your server" />
                  <AvatarFallback className="bg-slate-100 text-sm font-bold text-slate-700">AL</AvatarFallback>
                </Avatar>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between">
                    <h3 className="text-sm font-bold text-slate-900" data-testid="waiter-name">
                      Alex <span className="text-xs font-normal text-slate-500">• Your server</span>
                    </h3>
                    <span className="text-xs font-semibold text-amber-600">82% of goal</span>
                  </div>
                  <p className="text-xs text-slate-600 truncate mt-0.5">Saving for a trip to Lisbon ✈️</p>
                  <Progress value={82} className="h-1.5 mt-1.5 bg-slate-100 [&>div]:bg-amber-500" data-testid="tip-goal-progress" />
                </div>
              </div>

              <div className="grid grid-cols-4 gap-2 pt-1" role="radiogroup" data-testid="tip-selector">
                {TIP_OPTIONS.map((t) => {
                  const active = tipPercent === t;
                  return (
                    <button
                      key={t}
                      type="button"
                      role="radio"
                      aria-checked={active}
                      onClick={() => setTipPercent(t)}
                      data-testid={`tip-option-${t}`}
                      className={`text-center py-2 rounded-xl border text-xs font-semibold transition-colors ${
                        active
                          ? "bg-slate-900 text-white border-slate-900"
                          : "border-slate-200 text-slate-700 hover:bg-slate-50"
                      }`}
                    >
                      {t}%
                    </button>
                  );
                })}
              </div>
            </motion.section>

            {/* Summary */}
            <motion.section
              className="bg-slate-50 rounded-2xl p-4 border border-slate-200/80 text-xs text-slate-600 space-y-1.5"
              data-testid="bill-summary"
              {...fadeUp(0.45)}
            >
              <div className="flex justify-between">
                <span>{summaryLabel}</span>
                <span className="font-medium tabular-nums text-slate-900" data-testid="summary-subtotal">
                  {fmt(subtotal)}
                </span>
              </div>
              <div className="flex justify-between">
                <span>Service Tip ({tipPercent}%)</span>
                <span className="font-medium tabular-nums text-slate-900" data-testid="summary-tip">
                  {fmt(tipAmount)}
                </span>
              </div>
              <div className="flex justify-between">
                <span>Platform convenience fee</span>
                <span className="font-medium tabular-nums text-slate-900" data-testid="summary-fee">
                  {fmt(PLATFORM_FEE)}
                </span>
              </div>
              <div className="flex justify-between pt-1.5 border-t border-slate-200 font-bold text-slate-900 text-sm">
                <span>Your Total</span>
                <span className="tabular-nums" data-testid="summary-total">
                  {fmt(payTotal)}
                </span>
              </div>
            </motion.section>
          </main>

          {/* Sticky footer */}
          <footer
            className="sticky bottom-0 z-40 bg-white/95 backdrop-blur-md border-t border-slate-200 p-4 rounded-t-3xl shadow-[0_-8px_30px_rgba(0,0,0,0.08)]"
            data-testid="checkout-bar"
          >
            <p className="text-[11px] text-slate-400 mb-1 px-1" data-testid="platform-fee-line">
              Platform convenience fee: {fmt(PLATFORM_FEE)} · included in total
            </p>
            <div className="flex items-center justify-between mb-3 px-1">
              <div>
                <span className="text-xs text-slate-500 uppercase tracking-wider font-medium">To Pay Now</span>
                <p className="text-xl font-bold tracking-tight text-slate-900 tabular-nums" data-testid="footer-total">
                  {fmt(payTotal)}
                </p>
              </div>
              <span className="text-[11px] text-emerald-600 font-semibold bg-emerald-50 px-2 py-0.5 rounded-full">
                Encrypted &amp; Instant
              </span>
            </div>

            <div className="grid grid-cols-2 gap-2.5">
              <motion.button
                type="button"
                whileTap={{ scale: 0.97 }}
                disabled={paying !== null || (payMode === "roulette" && !loser && !paidViaRoulette) || (payMode === "roulette" && paidViaRoulette)}
                onClick={() => handlePay("apple_pay")}
                data-testid="apple-pay-button"
                className="flex items-center justify-center gap-1.5 py-3.5 px-4 bg-black text-white font-semibold text-sm rounded-2xl shadow-md transition-transform disabled:opacity-70"
              >
                {paying === "apple_pay" ? <Loader2 className="w-4 h-4 animate-spin" /> : <Apple className="w-4 h-4 fill-current" />}
                {payMode === "roulette" && paidViaRoulette ? "Paid ✓" : payMode === "roulette" && !loser ? "Spin first" : "Pay"}
              </motion.button>

              <motion.button
                type="button"
                whileTap={{ scale: 0.97 }}
                disabled={paying !== null || (payMode === "roulette" && !loser && !paidViaRoulette) || (payMode === "roulette" && paidViaRoulette)}
                onClick={() => handlePay("blik")}
                data-testid="blik-pay-button"
                className="flex items-center justify-center gap-1.5 py-3.5 px-4 bg-[#eb0045] text-white font-bold text-sm rounded-2xl shadow-md tracking-wide transition-transform disabled:opacity-70"
              >
                {paying === "blik" ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <span className="text-xs uppercase bg-white text-[#eb0045] px-1.5 py-0.5 rounded font-black tracking-normal">
                    BLIK
                  </span>
                )}
                {payMode === "roulette" && paidViaRoulette ? "Paid ✓" : payMode === "roulette" && !loser ? "Spin first" : "Pay Now"}
              </motion.button>
            </div>
          </footer>

          {/* Success drawer */}
          <Drawer open={drawerOpen} onOpenChange={setDrawerOpen}>
            <DrawerContent className="max-w-md mx-auto" data-testid="success-drawer">
              {processing ? (
                <div className="flex flex-col items-center justify-center py-16 gap-4" data-testid="processing-state">
                  <Loader2 className="w-10 h-10 animate-spin text-slate-900" />
                  <p className="text-sm font-semibold text-slate-700">Processing payment...</p>
                </div>
              ) : (
                <>
                  <DrawerHeader className="text-center pt-2">
                    <motion.div
                      initial={{ scale: 0.4, opacity: 0 }}
                      animate={{ scale: 1, opacity: 1 }}
                      transition={{ type: "spring", stiffness: 300, damping: 18 }}
                      className="mx-auto w-16 h-16 rounded-full bg-emerald-50 border border-emerald-200 flex items-center justify-center mb-2"
                    >
                      <motion.div initial={{ scale: 0 }} animate={{ scale: 1 }} transition={{ delay: 0.15, type: "spring", stiffness: 400, damping: 15 }}>
                        <CheckCircle2 className="w-9 h-9 text-emerald-600" />
                      </motion.div>
                    </motion.div>
                    <DrawerTitle className="text-xl font-bold tracking-tight text-slate-900" data-testid="success-title">
                      Paid! Table #12 is closed
                    </DrawerTitle>
                    <DrawerDescription className="text-xs text-slate-500">
                      {receipt?.payment_method === "blik" ? "Paid with BLIK" : "Paid with Apple Pay"} • {receipt?.table_number}
                    </DrawerDescription>
                  </DrawerHeader>

                  {receipt && (
                    <div className="px-6 pb-2 space-y-3 max-h-[55vh] overflow-y-auto" data-testid="receipt-details">
                      <div className="bg-slate-50 rounded-2xl p-4 border border-slate-200/80 text-xs text-slate-600 space-y-1.5">
                        <div className="flex justify-between">
                          <span>Bill subtotal</span>
                          <span className="font-medium tabular-nums text-slate-900">{fmt(receipt.subtotal)}</span>
                        </div>
                        <div className="flex justify-between">
                          <span>Tip for Alex ({receipt.tip_percent}%)</span>
                          <span className="font-medium tabular-nums text-slate-900">{fmt(receipt.tip_amount)}</span>
                        </div>
                        <div className="flex justify-between">
                          <span>Platform convenience fee</span>
                          <span className="font-medium tabular-nums text-slate-900">{fmt(PLATFORM_FEE)}</span>
                        </div>
                        {receipt.roulette_loser && (
                          <p className="text-xs font-semibold text-amber-600 pt-0.5">
                            🎉 {receipt.roulette_loser} pays the bill!
                          </p>
                        )}
                        <div className="flex justify-between pt-1.5 border-t border-slate-200 font-bold text-slate-900 text-sm">
                          <span>Paid</span>
                          <span className="tabular-nums" data-testid="receipt-total">{fmt(receipt.total)}</span>
                        </div>
                      </div>

                      <div className="flex gap-2">
                        <button
                          type="button"
                          onClick={() => toast.success("Receipt downloaded", { description: "receipt-table-12.pdf saved to your device." })}
                          data-testid="download-receipt-button"
                          className="flex-1 flex items-center justify-center gap-1.5 py-2.5 rounded-xl bg-slate-100 border border-slate-200 text-xs font-bold text-slate-800 active:scale-95 transition-transform"
                        >
                          <Download className="w-3.5 h-3.5" /> Download Receipt (PDF)
                        </button>
                        {receipt.roulette_loser && (
                          <button
                            type="button"
                            onClick={() => toast.success("Opening Instagram…", { description: `${receipt.roulette_loser} pays the bill! 🎉` })}
                            data-testid="share-instagram-button"
                            className="flex-1 flex items-center justify-center gap-1.5 py-2.5 rounded-xl bg-gradient-to-r from-fuchsia-500 to-amber-400 text-white text-xs font-bold active:scale-95 transition-transform"
                          >
                            <Camera className="w-3.5 h-3.5" /> Share Roulette Result
                          </button>
                        )}
                      </div>

                      {/* Smart review filter */}
                      <div className="rounded-2xl border border-slate-200/80 p-4 space-y-2.5" data-testid="review-section">
                        <p className="text-xs font-bold text-slate-900 text-center">How was your visit?</p>
                        <div className="flex justify-center gap-1.5" data-testid="star-row">
                          {[1, 2, 3, 4, 5].map((s) => (
                            <button
                              key={s}
                              type="button"
                              onClick={() => { setStars(s); setThanks(s >= 4); }}
                              data-testid={`star-${s}`}
                              className="p-1 active:scale-90 transition-transform"
                              aria-label={`${s} star${s > 1 ? "s" : ""}`}
                            >
                              <Star
                                className={`w-7 h-7 transition-colors ${s <= stars ? "text-amber-400 fill-amber-400" : "text-slate-300"}`}
                              />
                            </button>
                          ))}
                        </div>

                        <AnimatePresence mode="wait">
                          {stars >= 1 && stars <= 3 && (
                            <motion.div
                              key="feedback"
                              initial={{ opacity: 0, y: 8 }}
                              animate={{ opacity: 1, y: 0 }}
                              exit={{ opacity: 0 }}
                              className="space-y-2"
                              data-testid="feedback-box"
                            >
                              <p className="text-xs text-slate-600 text-center">
                                We're sorry! Message the manager directly so we can fix it right now
                              </p>
                              <textarea
                                value={feedback}
                                onChange={(e) => setFeedback(e.target.value)}
                                placeholder="Tell us what went wrong..."
                                rows={2}
                                data-testid="feedback-input"
                                className="w-full px-3 py-2 rounded-xl border border-slate-200 text-xs text-slate-800 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-slate-900/20 resize-none"
                              />
                              <button
                                type="button"
                                disabled={!feedback.trim() || feedbackSent}
                                onClick={() => { setFeedbackSent(true); toast.success("Sent to the manager", { description: "We'll make it right." }); }}
                                data-testid="send-manager-button"
                                className="w-full py-2.5 rounded-xl bg-rose-500 text-white text-xs font-bold disabled:opacity-40 active:scale-95 transition-transform"
                              >
                                {feedbackSent ? "Sent ✓" : "Send to Manager"}
                              </button>
                            </motion.div>
                          )}
                          {stars >= 4 && (
                            <motion.div
                              key="thanks"
                              initial={{ opacity: 0, scale: 0.9 }}
                              animate={{ opacity: 1, scale: 1 }}
                              exit={{ opacity: 0 }}
                              className="space-y-2 text-center"
                              data-testid="thanks-box"
                            >
                              <motion.p
                                initial={{ scale: 0.6 }}
                                animate={{ scale: 1 }}
                                transition={{ type: "spring", stiffness: 300, damping: 12 }}
                                className="text-2xl"
                                aria-hidden="true"
                              >
                                🎉
                              </motion.p>
                              <p className="text-xs font-semibold text-slate-700">Thank you! It means the world to us</p>
                              <button
                                type="button"
                                onClick={() => toast.success("Opening Google Maps…", { description: "Post your 5★ review!" })}
                                data-testid="google-maps-button"
                                className="w-full py-2.5 rounded-xl bg-emerald-500 text-white text-xs font-bold active:scale-95 transition-transform"
                              >
                                Post your 5★ on Google Maps in 1 tap
                              </button>
                            </motion.div>
                          )}
                        </AnimatePresence>
                      </div>

                      {/* Treat a friend perk */}
                      <div className="rounded-2xl border border-amber-200/70 bg-amber-50 p-4 flex items-center gap-3" data-testid="voucher-card">
                        <span className="text-xl" aria-hidden="true">🎁</span>
                        <div className="flex-1 min-w-0">
                          <p className="text-xs font-bold text-slate-900">Treat a Friend to a Coffee/Beer</p>
                          <p className="text-[11px] text-slate-500">Send a digital drink voucher via link</p>
                        </div>
                        <button
                          type="button"
                          disabled={voucherSent}
                          onClick={() => { setVoucherSent(true); toast.success("Voucher link copied!", { description: "Send it to a lucky friend 🍺" }); }}
                          data-testid="send-voucher-button"
                          className="px-3 py-2 rounded-xl bg-slate-900 text-white text-xs font-bold disabled:opacity-50 active:scale-95 transition-transform"
                        >
                          {voucherSent ? "Sent ✓" : "Send"}
                        </button>
                      </div>
                    </div>
                  )}

                  <DrawerFooter>
                    <button
                      type="button"
                      onClick={() => setDrawerOpen(false)}
                      data-testid="done-button"
                      className="w-full py-3.5 bg-slate-900 text-white font-semibold text-sm rounded-2xl active:scale-98 transition-transform"
                    >
                      Done
                    </button>
                  </DrawerFooter>
                </>
              )}
            </DrawerContent>
          </Drawer>
        </div>
      )}
    </div>
  );
}