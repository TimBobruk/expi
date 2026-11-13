import json
import random
import uuid
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from engine import (
    WAITER_PIN, MENU_CATALOG, PREDICTIONS_REGULAR, PREDICTIONS_BOSS,
    WAITER_PROFILE, TABLES_STATE, WAITER_ORDERS,
    get_psycho_radar, apply_split_equally, apply_boss_mode, log_event
)

app = FastAPI()

# Дозволяємо підключення з TypeScript фронтенду колеги (React / Vue / Next.js)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ConnectionHub:
    def __init__(self):
        self.table_sockets: dict[int, dict[str, list[WebSocket]]] = {}
        self.waiter_sockets: list[WebSocket] = []

    async def connect_guest(self, ws: WebSocket, table_id: int, user_id: str):
        await ws.accept()
        table_map = self.table_sockets.setdefault(table_id, {})
        table_map.setdefault(user_id, []).append(ws)
        TABLES_STATE[table_id]["online_users"] = list(table_map.keys())
        if TABLES_STATE[table_id]["status"] == "free":
            TABLES_STATE[table_id]["status"] = "occupied"
        await self.broadcast_table(table_id)

    async def disconnect_guest(self, ws: WebSocket, table_id: int, user_id: str):
        table_map = self.table_sockets.get(table_id, {})
        if user_id in table_map and ws in table_map[user_id]:
            table_map[user_id].remove(ws)
            if not table_map[user_id]:
                table_map.pop(user_id, None)
        TABLES_STATE[table_id]["online_users"] = list(table_map.keys())
        await self.broadcast_table(table_id)

    async def connect_waiter(self, ws: WebSocket):
        await ws.accept()
        self.waiter_sockets.append(ws)
        await self.broadcast_waiter()

    def disconnect_waiter(self, ws: WebSocket):
        if ws in self.waiter_sockets:
            self.waiter_sockets.remove(ws)

    async def broadcast_table(self, table_id: int, event_type: str = "update", extra: dict = None):
        payload = json.dumps({
            "event": event_type,
            "state": TABLES_STATE[table_id],
            "waiter": WAITER_PROFILE,
            "extra": extra or {}
        })
        table_map = self.table_sockets.get(table_id, {})
        for uid, sockets in list(table_map.items()):
            for ws in list(sockets):
                try:
                    await ws.send_text(payload)
                except Exception:
                    sockets.remove(ws)
        await self.broadcast_waiter()

    async def broadcast_waiter(self, event_type: str = "update", extra: dict = None):
        enriched_tables = {}
        for tid, t in TABLES_STATE.items():
            copy_t = dict(t)
            copy_t["psycho_radar"] = get_psycho_radar(t)
            enriched_tables[tid] = copy_t

        payload = json.dumps({
            "event": event_type,
            "tables": enriched_tables,
            "waiter": WAITER_PROFILE,
            "orders": WAITER_ORDERS,
            "extra": extra or {}
        })
        for ws in list(self.waiter_sockets):
            try:
                await ws.send_text(payload)
            except Exception:
                self.disconnect_waiter(ws)

hub = ConnectionHub()

@app.websocket("/ws/table/{table_id}/{user_id}")
async def guest_ws(websocket: WebSocket, table_id: int, user_id: str):
    if table_id not in TABLES_STATE:
        await websocket.close()
        return
    await hub.connect_guest(websocket, table_id, user_id)
    try:
        while True:
            msg = json.loads(await websocket.receive_text())
            action = msg.get("action")
            table = TABLES_STATE[table_id]

            # 1. Вибір окремої страви або ділення конкретної позиції з другом
            if action == "toggle_share":
                table["split_mode"] = "custom"
                for item in table["items"]:
                    if item["id"] == msg["item_id"] and user_id not in item["paid_by"]:
                        if user_id in item["sharers"]:
                            item["sharers"].remove(user_id)
                        else:
                            item["sharers"].append(user_id)
                await hub.broadcast_table(table_id)

            # 2. Фіча TypeScript: Поділити весь чек порівну на всіх гостей за столом
            elif action == "split_equally":
                apply_split_equally(table_id)
                log_event(table_id, user_id, "⚖️ Увімкнув розподіл всього рахунку порівну на всіх", "INFO")
                await hub.broadcast_table(table_id)

            # 3. Фіча TypeScript: Закрити весь стіл самому (Boss Mode)
            elif action == "pay_all_myself":
                apply_boss_mode(table_id, user_id)
                log_event(table_id, user_id, "👑 Режим БОСА: хоче закрити весь рахунок столу сам!", "INFO")
                await hub.broadcast_table(table_id)

            # 4. Рулетка Фортуни
            elif action == "spin_roulette":
                users = table["online_users"] or [user_id]
                loser = random.choice(users)
                table["last_roulette"] = f"🎰 Фортуна обрала: нехай платить {loser}!"
                for item in table["items"]:
                    if not item["paid_by"] and not item["sharers"]:
                        item["sharers"] = [loser]
                await hub.broadcast_table(table_id, event_type="roulette", extra={"loser": loser})

            # 5. Повтор напою / страви в 1 клік
            elif action == "repeat_item":
                orig = next((i for i in table["items"] if i["id"] == msg["item_id"]), None)
                if orig:
                    table["items"].append({
                        "id": str(uuid.uuid4())[:6],
                        "name": orig["name"],
                        "price": orig["price"],
                        "sharers": [user_id],
                        "paid_by": []
                    })
                    log_event(table_id, user_id, f"🔄 Повторити: {orig['name']} ({orig['price']/100:.0f} zł)", "NEW")
                    await hub.broadcast_table(table_id)

            # 6. Замовлення з меню
            elif action == "order_from_menu":
                names = []
                for cid in msg.get("items", []):
                    dish = next((m for m in MENU_CATALOG if m["id"] == cid), None)
                    if dish:
                        table["items"].append({
                            "id": str(uuid.uuid4())[:6],
                            "name": dish["name"],
                            "price": dish["price"],
                            "sharers": [user_id],
                            "paid_by": []
                        })
                        names.append(dish["name"])
                if names:
                    log_event(table_id, user_id, f"🍽️ Дозамовлення: {', '.join(names)}", "NEW")
                    await hub.broadcast_table(table_id)

            # 7. Оплата своєї частки + Психологічна винагорода
            elif action == "pay_my_share":
                tip_grosze = int(float(msg.get("tip_pln", 0)) * 100)
                paid_amount = 0
                for item in table["items"]:
                    if user_id in item["sharers"] and user_id not in item["paid_by"]:
                        paid_amount += item["price"] // len(item["sharers"])
                        item["paid_by"].append(user_id)

                if paid_amount > 0 or tip_grosze > 0:
                    WAITER_PROFILE["goal_current"] += tip_grosze
                    WAITER_PROFILE["xp"] += 50
                    is_boss = table["split_mode"] == "boss"
                    prediction = random.choice(PREDICTIONS_BOSS if is_boss else PREDICTIONS_REGULAR)

                    log_event(table_id, user_id, f"💳 Оплатив {paid_amount/100:.2f} zł | Чайові: +{tip_grosze/100:.2f} zł", "PAID")
                    await websocket.send_text(json.dumps({
                        "event": "payment_success",
                        "prediction": prediction,
                        "is_boss": is_boss,
                        "paid_pln": (paid_amount + tip_grosze) / 100
                    }))
                    await hub.broadcast_waiter(event_type="tip_received", extra={"tip_pln": tip_grosze / 100, "user": user_id})
                await hub.broadcast_table(table_id)

    except WebSocketDisconnect:
        await hub.disconnect_guest(websocket, table_id, user_id)

@app.websocket("/ws/waiter/{pin}")
async def waiter_ws(websocket: WebSocket, pin: str):
    if pin != WAITER_PIN:
        await websocket.close(code=1008)
        return
    await hub.connect_waiter(websocket)
    try:
        while True:
            msg = json.loads(await websocket.receive_text())
            action = msg.get("action")
            if action == "accept_order":
                for order in WAITER_ORDERS:
                    if order["id"] == msg["order_id"] and order["status"] == "NEW":
                        order["status"] = "DONE"
                        WAITER_PROFILE["streak"] += 1
                        WAITER_PROFILE["xp"] += 25
                await hub.broadcast_waiter()
            elif action == "reset_table":
                tid = int(msg["table_id"])
                TABLES_STATE[tid]["status"] = "free"
                TABLES_STATE[tid]["items"] = []
                TABLES_STATE[tid]["split_mode"] = "custom"
                await hub.broadcast_table(tid)
    except WebSocketDisconnect:
        hub.disconnect_waiter(websocket)

# Симулятор 3-в-1: відкриває Гостя 1, Гостя 2 і Офіціанта на одному екрані!
@app.get("/dev", response_class=HTMLResponse)
async def dev_simulator():
    return """
    <!DOCTYPE html>
    <html>
    <head><title>🚀 Dev Simulator: 2 Гостя + Офіціант</title></head>
    <body style="margin:0; background:#090a0f; color:#fff; font-family:sans-serif; height:100vh; display:flex; flex-direction:column;">
        <div style="padding:10px 20px; background:#141720; border-bottom:1px solid #222; display:flex; justify-content:space-between; align-items:center;">
            <b>⚡ Режим паралельного тестування (Всі дії синхронізуються миттєво)</b>
            <div style="font-size:13px; color:#aaa;">
                Окремі вкладки: 
                <a href="/test/5/Tim" target="_blank" style="color:#4dabf7; margin-right:10px;">Гість Tim ↗</a>
                <a href="/test/5/Friend" target="_blank" style="color:#4dabf7; margin-right:10px;">Гість Friend ↗</a>
                <a href="/waiter" target="_blank" style="color:#51cf66;">Термінал Офіціанта ↗</a>
            </div>
        </div>
        <div style="flex:1; display:grid; grid-template-columns: 380px 380px 1fr; gap:8px; padding:8px;">
            <iframe src="/test/5/Tim" style="width:100%; height:100%; border:2px solid #339af0; border-radius:14px; background:#fff;"></iframe>
            <iframe src="/test/5/Friend" style="width:100%; height:100%; border:2px solid #f06595; border-radius:14px; background:#fff;"></iframe>
            <iframe src="/waiter" style="width:100%; height:100%; border:2px solid #12b886; border-radius:14px; background:#0f1115;"></iframe>
        </div>
    </body>
    </html>
    """

@app.get("/test/{user_id}", response_class=HTMLResponse)
async def legacy_guest_ui(user_id: str):
    return await guest_table_ui(5, user_id)

@app.get("/test/{table_id}/{user_id}", response_class=HTMLResponse)
async def guest_table_ui(table_id: int, user_id: str):
    menu_json = json.dumps(MENU_CATALOG)
    html = """
    <!DOCTYPE html>
    <html>
    <head><meta name="viewport" content="width=device-width, initial-scale=1"></head>
    <body style="font-family: -apple-system, sans-serif; max-width: 430px; margin: 0 auto; padding: 12px 12px 90px 12px; background: #f4f5f7;">
        
        <div style="background: #111; color: #fff; padding: 12px; border-radius: 14px; margin-bottom: 10px; display:flex; justify-content:space-between; align-items:center;">
            <div>
                <div id="t-title" style="font-weight:bold; font-size:15px;">Стіл №__TID__ • <span style="color:#4dabf7">__USER__</span></div>
                <div id="online" style="font-size:11px; color:#aaa; margin-top:2px;"></div>
            </div>
            <button onclick="spin()" style="background: linear-gradient(90deg,#ff6b6b,#f06595); color:#fff; border:none; padding:8px 12px; border-radius:10px; font-weight:bold; cursor:pointer; font-size:12px;">
                🎰 Рулетка
            </button>
        </div>
        <div id="roulette-banner" style="display:none; background:#fff3bf; color:#d9480f; padding:8px; border-radius:10px; margin-bottom:10px; font-weight:bold; text-align:center; font-size:13px;"></div>

        <!-- Вкладка МЕНЮ (з психологічними тригерами) -->
        <div id="tab-menu" style="display:none;">
            <div id="menu-list"></div>
            <div id="cart-bar" style="display:none; background:#111; color:#fff; padding:12px; border-radius:12px; margin-top:10px; justify-content:space-between; align-items:center;">
                <span id="cart-text">Обрано: 0</span>
                <button onclick="submitOrder()" style="background:#12b886; color:#fff; border:none; padding:8px 14px; border-radius:8px; font-weight:bold; cursor:pointer;">Замовити ➔</button>
            </div>
        </div>

        <!-- Вкладка РАХУНОК (3 режими розділення чека) -->
        <div id="tab-bill">
            <!-- Швидкі кнопки розподілу чека (як у TypeScript колеги) -->
            <div style="display:grid; grid-template-columns: 1fr 1fr; gap:8px; margin-bottom:10px;">
                <button onclick="splitEqually()" style="background:#fff; border:2px solid #339af0; color:#1971c2; padding:10px 8px; border-radius:12px; font-weight:bold; font-size:12px; cursor:pointer;">
                    ⚖️ Поділити чек порівну на всіх
                </button>
                <button onclick="payAllMyself()" style="background:linear-gradient(135deg,#212529,#000); border:none; color:#ffd43b; padding:10px 8px; border-radius:12px; font-weight:bold; font-size:12px; cursor:pointer;">
                    👑 Закрити весь стіл самому
                </button>
            </div>

            <div style="font-size:12px; color:#666; margin-bottom:6px;">Або клікай на окремі страви, щоб обрати чи поділити:</div>
            <div id="items"></div>

            <!-- Психологічна картка офіціанта -->
            <div style="background:#fff; padding:14px; border-radius:16px; margin-top:12px; box-shadow:0 2px 8px rgba(0,0,0,0.05);">
                <div style="display:flex; align-items:center; gap:10px; margin-bottom:8px;">
                    <div style="font-size:28px; background:#f1f3f5; width:44px; height:44px; display:flex; align-items:center; justify-content:center; border-radius:50%;">🧑‍🍳</div>
                    <div style="flex:1;">
                        <div style="font-weight:bold; font-size:14px;" id="w-name">Олексій</div>
                        <div style="font-size:12px; color:#666;" id="w-goal"></div>
                    </div>
                </div>
                <div style="background:#e9ecef; height:8px; border-radius:4px; overflow:hidden; margin-bottom:4px;">
                    <div id="w-progress" style="background:#12b886; height:100%; width:80%; transition: width 0.4s;"></div>
                </div>
                <div id="w-progress-text" style="font-size:11px; color:#868e96; text-align:right; margin-bottom:10px;"></div>

                <div style="display:grid; grid-template-columns: repeat(4, 1fr); gap:6px; margin-bottom:10px;">
                    <button onclick="setTipMode(5)" id="btn-t5" style="padding:8px; border-radius:8px; border:1px solid #dee2e6; background:#fff; cursor:pointer; font-weight:bold; font-size:12px;">5%</button>
                    <button onclick="setTipMode(10)" id="btn-t10" style="padding:8px; border-radius:8px; border:2px solid #12b886; background:#e6fcf5; cursor:pointer; font-weight:bold; font-size:12px;">10% 🔥</button>
                    <button onclick="setTipMode(15)" id="btn-t15" style="padding:8px; border-radius:8px; border:1px solid #dee2e6; background:#fff; cursor:pointer; font-weight:bold; font-size:12px;">15% ❤️</button>
                    <button onclick="setTipMode('custom')" id="btn-tcustom" style="padding:8px; border-radius:8px; border:1px solid #dee2e6; background:#fff; cursor:pointer; font-weight:bold; font-size:12px;">Своя</button>
                </div>
                <input id="custom-tip-input" type="number" placeholder="Сума чайових у zł" oninput="recalcTotal()" style="display:none; width:100%; box-sizing:border-box; padding:8px; border-radius:8px; border:1px solid #ccc; margin-bottom:10px;">

                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
                    <span id="breakdown-text" style="font-size:12px; color:#555;">0 + 0 zł</span>
                    <b id="my-total" style="font-size:19px;">0.00 zł</b>
                </div>
                <button onclick="payNow()" style="width:100%; padding:13px; background:#12b886; color:white; font-size:15px; font-weight:bold; border:none; border-radius:12px; cursor:pointer;">
                     Pay / BLIK — Оплатити свою частку
                </button>
            </div>
        </div>

        <!-- Модалка передбачення -->
        <div id="fortune-modal" style="display:none; position:fixed; inset:0; background:rgba(0,0,0,0.7); align-items:center; justify-content:center; padding:16px; z-index:100;">
            <div style="background:#fff; padding:20px; border-radius:20px; max-width:320px; text-align:center;">
                <div id="fortune-icon" style="font-size:40px; margin-bottom:6px;">🎉</div>
                <h3 style="margin:0 0 6px 0;">Оплачено успішно!</h3>
                <div id="fortune-paid" style="font-size:12px; color:#666; margin-bottom:12px;"></div>
                <div style="background:#fff9db; border:1px dashed #fab005; padding:12px; border-radius:12px; font-size:13px; margin-bottom:14px;">
                    <b>🔮 Твоє передбачення:</b><br><br><span id="fortune-text"></span>
                </div>
                <button onclick="document.getElementById('fortune-modal').style.display='none'" style="width:100%; padding:10px; background:#111; color:#fff; border:none; border-radius:10px; font-weight:bold; cursor:pointer;">Круто!</button>
            </div>
        </div>

        <div style="position:fixed; bottom:0; left:0; right:0; max-width:430px; margin:0 auto; background:#fff; border-top:1px solid #e9ecef; display:grid; grid-template-columns:1fr 1fr; padding:8px 12px; gap:8px;">
            <button id="nav-menu" onclick="switchTab('menu')" style="padding:9px; border-radius:10px; border:none; background:#f1f3f5; font-weight:bold; cursor:pointer;">📖 Меню</button>
            <button id="nav-bill" onclick="switchTab('bill')" style="padding:9px; border-radius:10px; border:none; background:#111; color:#fff; font-weight:bold; cursor:pointer;">🧾 Рахунок</button>
        </div>

        <script>
            const user = "__USER__";
            const tableId = "__TID__";
            const menuCatalog = __MENU__;
            let cart = [], tipMode = 10, mySubtotalPln = 0;

            const ws = new WebSocket("ws://" + location.host + "/ws/table/" + tableId + "/" + user);

            function renderMenu() {
                const list = document.getElementById("menu-list");
                list.innerHTML = "";
                menuCatalog.forEach(m => {
                    list.innerHTML += `
                        <div style="background:#fff; padding:12px; border-radius:12px; margin-bottom:8px; display:flex; justify-content:space-between; align-items:center;">
                            <div>
                                <div style="font-size:11px; color:#e67700; font-weight:bold; margin-bottom:2px;">${m.badge}</div>
                                <div style="font-weight:bold; font-size:14px;">${m.name} — ${(m.price/100).toFixed(0)} zł</div>
                                <div style="font-size:11px; color:#666;">${m.desc}</div>
                            </div>
                            <button onclick="addToCart('${m.id}')" style="background:#111; color:#fff; border:none; padding:8px 12px; border-radius:8px; font-weight:bold; cursor:pointer;">➕</button>
                        </div>`;
                });
            }
            renderMenu();

            function addToCart(id) {
                cart.push(id);
                document.getElementById("cart-bar").style.display = "flex";
                document.getElementById("cart-text").innerText = "У кошику: " + cart.length;
            }
            function submitOrder() {
                ws.send(JSON.stringify({action: "order_from_menu", items: cart}));
                cart = [];
                document.getElementById("cart-bar").style.display = "none";
                switchTab('bill');
            }
            function switchTab(tab) {
                document.getElementById("tab-menu").style.display = tab === 'menu' ? 'block' : 'none';
                document.getElementById("tab-bill").style.display = tab === 'bill' ? 'block' : 'none';
                document.getElementById("nav-menu").style.background = tab === 'menu' ? '#111' : '#f1f3f5';
                document.getElementById("nav-menu").style.color = tab === 'menu' ? '#fff' : '#000';
                document.getElementById("nav-bill").style.background = tab === 'bill' ? '#111' : '#f1f3f5';
                document.getElementById("nav-bill").style.color = tab === 'bill' ? '#fff' : '#000';
            }
            function setTipMode(mode) {
                tipMode = mode;
                ['5', '10', '15', 'custom'].forEach(m => {
                    const btn = document.getElementById('btn-t' + m);
                    const active = String(mode) === m;
                    btn.style.border = active ? '2px solid #12b886' : '1px solid #dee2e6';
                    btn.style.background = active ? '#e6fcf5' : '#fff';
                });
                document.getElementById('custom-tip-input').style.display = mode === 'custom' ? 'block' : 'none';
                recalcTotal();
            }
            function getTipPln() {
                if (tipMode === 'custom') return parseFloat(document.getElementById('custom-tip-input').value || 0);
                return +(mySubtotalPln * (tipMode / 100)).toFixed(2);
            }
            function recalcTotal() {
                const tipPln = getTipPln();
                document.getElementById("breakdown-text").innerText = `Страви: ${mySubtotalPln.toFixed(2)} + Чайові: ${tipPln.toFixed(2)} zł`;
                document.getElementById("my-total").innerText = (mySubtotalPln + tipPln).toFixed(2) + " zł";
            }

            ws.onmessage = (e) => {
                const data = JSON.parse(e.data);
                if (data.event === "payment_success") {
                    document.getElementById("fortune-icon").innerText = data.is_boss ? "👑" : "🎉";
                    document.getElementById("fortune-paid").innerText = `Списано: ${data.paid_pln.toFixed(2)} zł`;
                    document.getElementById("fortune-text").innerText = data.prediction;
                    document.getElementById("fortune-modal").style.display = "flex";
                    return;
                }
                const state = data.state;
                const w = data.waiter;
                document.getElementById("online").innerText = "Онлайн за столом: " + state.online_users.join(", ");
                document.getElementById("w-name").innerText = `${w.name} • 🔥 Streak x${w.streak}`;
                document.getElementById("w-goal").innerText = w.goal_title;
                const pct = Math.min(100, Math.round((w.goal_current / w.goal_target) * 100));
                document.getElementById("w-progress").style.width = pct + "%";
                document.getElementById("w-progress-text").innerText = `${(w.goal_current/100).toFixed(0)} / ${(w.goal_target/100).toFixed(0)} zł (${pct}%)`;

                const rb = document.getElementById("roulette-banner");
                if (state.last_roulette) { rb.style.display = "block"; rb.innerText = state.last_roulette; }

                const container = document.getElementById("items");
                container.innerHTML = "";
                let subtotalGrosze = 0;

                state.items.forEach(item => {
                    const count = item.sharers.length;
                    const sharePrice = count > 0 ? (item.price / count) : item.price;
                    const isMine = item.sharers.includes(user);
                    const iPaid = item.paid_by.includes(user);
                    const allPaid = count > 0 && item.paid_by.length === count;

                    if (isMine && !iPaid) subtotalGrosze += sharePrice;

                    let bg = "#fff", border = "1px solid #e9ecef", statusText = "Вільно — натисни, щоб обрати";
                    if (allPaid) {
                        bg = "#d3f9d8"; statusText = "✅ Оплачено (" + item.paid_by.join(", ") + ")";
                    } else if (count > 0) {
                        bg = isMine ? "#e7f5ff" : "#fff9db";
                        border = isMine ? "2px solid #339af0" : "1px solid #ffd43b";
                        statusText = count === 1 ? "Оплачує: " + item.sharers[0] : `🤝 Ділять на ${count}-х (${item.sharers.join(", ")}) — по ${(sharePrice/100).toFixed(2)} zł`;
                    }

                    container.innerHTML += `
                        <div style="background:${bg}; border:${border}; padding:10px; margin-bottom:6px; border-radius:12px; display:flex; justify-content:space-between; align-items:center;">
                            <div onclick="toggle('${item.id}')" style="flex:1; cursor:pointer;">
                                <div style="font-weight:bold; font-size:14px;">${item.name} — ${(item.price/100).toFixed(0)} zł</div>
                                <div style="font-size:11px; color:#495057;">${statusText}</div>
                            </div>
                            <button onclick="repeatItem('${item.id}')" style="margin-left:8px; background:#212529; color:#fff; border:none; padding:6px 9px; border-radius:8px; font-size:11px; cursor:pointer;">🔄 +1</button>
                        </div>`;
                });
                mySubtotalPln = subtotalGrosze / 100;
                recalcTotal();
            };

            function toggle(id) { ws.send(JSON.stringify({action: "toggle_share", item_id: id})); }
            function splitEqually() { ws.send(JSON.stringify({action: "split_equally"})); }
            function payAllMyself() { ws.send(JSON.stringify({action: "pay_all_myself"})); }
            function spin() { ws.send(JSON.stringify({action: "spin_roulette"})); }
            function repeatItem(id) { ws.send(JSON.stringify({action: "repeat_item", item_id: id})); }
            function payNow() { ws.send(JSON.stringify({action: "pay_my_share", tip_pln: getTipPln()})); }
        </script>
    </body>
    </html>
    """
    return html.replace("__USER__", user_id).replace("__TID__", str(table_id)).replace("__MENU__", menu_json)

@app.get("/waiter", response_class=HTMLResponse)
async def waiter_ui():
    return """
    <!DOCTYPE html>
    <html>
    <head><title>Командний Центр Офіціанта</title></head>
    <body style="font-family: -apple-system, sans-serif; background:#0f1115; color:#fff; padding:15px; margin:0;">
        
        <!-- Дофаміновий тост при чайових -->
        <div id="tip-toast" style="display:none; position:fixed; top:20px; right:20px; background:linear-gradient(135deg,#fab005,#f08c00); color:#000; padding:14px 20px; border-radius:14px; font-weight:bold; box-shadow:0 8px 25px rgba(250,176,5,0.4); z-index:200;"></div>

        <div style="background:#181b20; padding:12px 16px; border-radius:14px; margin-bottom:14px; display:flex; justify-content:space-between; align-items:center;">
            <div>
                <b style="font-size:17px;">🗺️ Радар Залу та Психологічні Підказки</b>
                <div id="waiter-stats" style="font-size:12px; color:#51cf66; margin-top:2px;"></div>
            </div>
            <div id="waiter-wallet" style="background:#212529; padding:8px 12px; border-radius:10px; font-size:13px;"></div>
        </div>

        <div style="display:grid; grid-template-columns: 1.5fr 1fr; gap:14px;">
            <div id="tables-grid" style="display:grid; grid-template-columns: 1fr 1fr; gap:10px;"></div>
            <div style="background:#181b20; padding:14px; border-radius:14px; height:fit-content;">
                <h3 style="margin-top:0; font-size:15px; color:#ff6b6b;">🔔 Жива стрічка дій гостей</h3>
                <div id="orders"></div>
            </div>
        </div>

        <script>
            // Дофаміновий звук монети через Web Audio API (без зовнішніх файлів)
            function playCashSound() {
                try {
                    const ctx = new (window.AudioContext || window.webkitAudioContext)();
                    const osc = ctx.createOscillator();
                    const gain = ctx.createGain();
                    osc.type = "triangle";
                    osc.frequency.setValueAtTime(880, ctx.currentTime);
                    osc.frequency.setValueAtTime(1318.5, ctx.currentTime + 0.09);
                    gain.gain.setValueAtTime(0.2, ctx.currentTime);
                    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.4);
                    osc.connect(gain); gain.connect(ctx.destination);
                    osc.start(); osc.stop(ctx.currentTime + 0.4);
                } catch(e) {}
            }

            // Автоматичний вхід для зручності паралельного тестування (PIN 7777)
            const ws = new WebSocket("ws://" + location.host + "/ws/waiter/7777");

            ws.onmessage = (e) => {
                const data = JSON.parse(e.data);
                const w = data.waiter;

                if (data.event === "tip_received") {
                    playCashSound();
                    const toast = document.getElementById("tip-toast");
                    toast.innerText = `💸 КАЧІНГ! +${data.extra.tip_pln.toFixed(2)} zł чайових від ${data.extra.user}!`;
                    toast.style.display = "block";
                    setTimeout(() => toast.style.display = "none", 4000);
                }

                document.getElementById("waiter-stats").innerHTML = `🔥 Комбо швидкості: <b>x${w.streak}</b> | ⭐ Досвід зміни: <b>${w.xp} XP (PRO)</b>`;
                document.getElementById("waiter-wallet").innerHTML = `🏍️ Ціль: <b style="color:#ffd43b">${(w.goal_current/100).toFixed(2)} / ${(w.goal_target/100).toFixed(0)} zł</b>`;

                const grid = document.getElementById("tables-grid");
                grid.innerHTML = "";
                Object.values(data.tables).forEach(t => {
                    const borderCol = t.status === "occupied" ? "#339af0" : (t.status === "reserved" ? "#f08c00" : "#2c2e33");
                    const totalPln = t.items.reduce((acc, i) => acc + i.price, 0) / 100;
                    const paidCount = t.items.filter(i => i.sharers.length > 0 && i.paid_by.length === i.sharers.length).length;

                    grid.innerHTML += `
                        <div style="background:#181b20; border:2px solid ${borderCol}; padding:12px; border-radius:14px; display:flex; flex-direction:column; justify-content:space-between;">
                            <div>
                                <div style="display:flex; justify-content:space-between;">
                                    <b style="font-size:14px;">${t.name}</b>
                                    <span style="font-size:11px; color:#aaa;">${t.seats} місць</span>
                                </div>
                                <div style="background:#20242d; border-left:3px solid #4dabf7; padding:8px; border-radius:6px; margin-top:8px; font-size:11px; color:#dee2e6;">
                                    🧠 <b>Психо-радар:</b> ${t.psycho_radar}
                                </div>
                                <div style="font-size:12px; margin-top:8px;">
                                    🧾 Чек: <b>${totalPln.toFixed(0)} zł</b> (Оплачено: ${paidCount}/${t.items.length})
                                </div>
                                ${t.online_users.length ? `<div style="font-size:11px; color:#51cf66; margin-top:4px;">📱 За столом: ${t.online_users.join(", ")}</div>` : ""}
                            </div>
                            <button onclick="resetTable(${t.id})" style="margin-top:10px; background:#252830; color:#ccc; border:none; padding:6px; border-radius:6px; font-size:11px; cursor:pointer;">🧹 Закрити / Очистити стіл</button>
                        </div>`;
                });

                const ordersEl = document.getElementById("orders");
                ordersEl.innerHTML = data.orders.length ? "" : "<p style='color:#666; font-size:12px;'>Очікування дій гостей...</p>";
                data.orders.forEach(o => {
                    const bg = o.status === "NEW" ? "#c92a2a" : (o.status === "PAID" ? "#2b8a3e" : "#252830");
                    const btn = o.status === "NEW" ? `<button onclick="accept('${o.id}')" style="background:#fff; color:#000; border:none; padding:4px 8px; border-radius:6px; font-weight:bold; cursor:pointer; font-size:11px;">+25 XP Прийняти</button>` : `<span>✅</span>`;
                    ordersEl.innerHTML += `
                        <div style="background:${bg}; padding:9px; border-radius:8px; margin-bottom:6px; display:flex; justify-content:space-between; align-items:center; font-size:12px;">
                            <div><b>[${o.time}] Стіл №${o.table_id} (${o.user}):</b><br>${o.text}</div>
                            ${btn}
                        </div>`;
                });
            };
            function accept(id) { ws.send(JSON.stringify({action: "accept_order", order_id: id})); }
            function resetTable(tid) { ws.send(JSON.stringify({action: "reset_table", table_id: tid})); }
        </script>
    </body>
    </html>
    """