import json
import random
import uuid
from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

app = FastAPI()

WAITER_PIN = "7777"

MENU_CATALOG = [
    {"id": "m1", "name": "🍔 Смеш-бургер Трюфельний", "price": 4200, "cat": "Кухня", "desc": "Подвійна яловичина, чеддер, трюфельний айолі"},
    {"id": "m2", "name": "🍟 Батат фрі з пармезаном", "price": 2400, "cat": "Кухня", "desc": "Подається з соусом манго-чилі"},
    {"id": "m3", "name": "🍹 Коктейль Pornstar Martini", "price": 3800, "cat": "Бар", "desc": "Ванільна горілка, маракуйя, шот просекко"},
    {"id": "m4", "name": "🥃 Вишневий Сауер", "price": 3500, "cat": "Бар", "desc": "Бурбон, вишня, лимонний фреш, білок"},
]

PREDICTIONS = [
    "✨ Сьогодні вечір принесе тобі несподіване повідомлення, яке підніме настрій на весь тиждень!",
    "🚀 Твоя смілива ідея, яку ти відкладав — вистрілить. Час діяти вже цього тижня!",
    "💸 Гроші, витрачені з кайфом у гарній компанії, повертаються у подвійному розмірі!",
    "🔥 Хтось за цим столом явно думає, що ти душа цієї компанії (і не помиляється).",
    "🎯 Наступні 48 годин — ідеальний час для спонтанних рішень та крутих знайомств."
]

TABLES_STATE = {
    5: {
        "table_name": "Стіл №5 (Лаунж-тераса)",
        "waiter": {
            "name": "Олексій (Alex)",
            "role": "Старший бармен-офіціант",
            "avatar": "🧑‍🍳",
            "goal_title": "🏍️ Збираю на мотоцикл BMW GS",
            "goal_current": 485000,  # 4850.00 zł у грошах
            "goal_target": 600000    # 6000.00 zł
        },
        "online_users": [],
        "last_roulette": None,
        "items": [
            {"id": "1", "name": "🍹 Коктейль Негроні", "price": 3600, "sharers": [], "paid_by": []},
            {"id": "2", "name": "🍕 Піца Чотири Сири (Спільна)", "price": 5200, "sharers": [], "paid_by": []},
            {"id": "3", "name": "💨 Кальян Darkside (Спільний)", "price": 8000, "sharers": [], "paid_by": []},
        ]
    }
}

WAITER_ORDERS = []

class Hub:
    def __init__(self):
        self.table_sockets: dict[int, dict[str, WebSocket]] = {}
        self.waiter_sockets: list[WebSocket] = []

    async def connect_guest(self, ws: WebSocket, table_id: int, user_id: str):
        await ws.accept()
        self.table_sockets.setdefault(table_id, {})[user_id] = ws
        TABLES_STATE[table_id]["online_users"] = list(self.table_sockets[table_id].keys())
        await self.broadcast_all(table_id)

    async def disconnect_guest(self, table_id: int, user_id: str):
        self.table_sockets.get(table_id, {}).pop(user_id, None)
        TABLES_STATE[table_id]["online_users"] = list(self.table_sockets.get(table_id, {}).keys())
        for item in TABLES_STATE[table_id]["items"]:
            if user_id in item["sharers"] and user_id not in item["paid_by"]:
                item["sharers"].remove(user_id)
        await self.broadcast_all(table_id)

    async def connect_waiter(self, ws: WebSocket):
        await ws.accept()
        self.waiter_sockets.append(ws)
        await self.broadcast_waiter()

    def disconnect_waiter(self, ws: WebSocket):
        if ws in self.waiter_sockets:
            self.waiter_sockets.remove(ws)

    async def broadcast_all(self, table_id: int, event_type: str = "update", extra: dict = None):
        payload = {"event": event_type, "state": TABLES_STATE[table_id], "extra": extra or {}}
        for uid, ws in list(self.table_sockets.get(table_id, {}).items()):
            try:
                await ws.send_text(json.dumps(payload))
            except Exception:
                self.table_sockets[table_id].pop(uid, None)
        await self.broadcast_waiter()

    async def broadcast_waiter(self):
        payload = {"table": TABLES_STATE[5], "orders": WAITER_ORDERS}
        for ws in list(self.waiter_sockets):
            try:
                await ws.send_text(json.dumps(payload))
            except Exception:
                self.disconnect_waiter(ws)

hub = Hub()

@app.websocket("/ws/table/{table_id}/{user_id}")
async def guest_ws(websocket: WebSocket, table_id: int, user_id: str):
    await hub.connect_guest(websocket, table_id, user_id)
    try:
        while True:
            msg = json.loads(await websocket.receive_text())
            action = msg.get("action")

            if action == "toggle_share":
                for item in TABLES_STATE[table_id]["items"]:
                    if item["id"] == msg["item_id"] and user_id not in item["paid_by"]:
                        if user_id in item["sharers"]:
                            item["sharers"].remove(user_id)
                        else:
                            item["sharers"].append(user_id)
                await hub.broadcast_all(table_id)

            elif action == "spin_roulette":
                users = TABLES_STATE[table_id]["online_users"]
                if users:
                    loser = random.choice(users)
                    TABLES_STATE[table_id]["last_roulette"] = f"🎰 Фортуна обрала: {loser}!"
                    for item in TABLES_STATE[table_id]["items"]:
                        if not item["paid_by"] and not item["sharers"]:
                            item["sharers"] = [loser]
                    await hub.broadcast_all(table_id, event_type="roulette", extra={"loser": loser, "users": users})

            elif action == "repeat_item":
                orig = next((i for i in TABLES_STATE[table_id]["items"] if i["id"] == msg["item_id"]), None)
                if orig:
                    new_item = {
                        "id": str(uuid.uuid4())[:6],
                        "name": orig["name"],
                        "price": orig["price"],
                        "sharers": [user_id],
                        "paid_by": []
                    }
                    TABLES_STATE[table_id]["items"].append(new_item)
                    WAITER_ORDERS.insert(0, {
                        "id": str(uuid.uuid4())[:6],
                        "time": datetime.now().strftime("%H:%M:%S"),
                        "user": user_id,
                        "text": f"🔄 Повторити: {orig['name']} ({orig['price']/100:.0f} zł)",
                        "status": "NEW"
                    })
                    await hub.broadcast_all(table_id)

            elif action == "order_from_menu":
                cart_ids = msg.get("items", [])
                ordered_names = []
                for cid in cart_ids:
                    dish = next((m for m in MENU_CATALOG if m["id"] == cid), None)
                    if dish:
                        TABLES_STATE[table_id]["items"].append({
                            "id": str(uuid.uuid4())[:6],
                            "name": dish["name"],
                            "price": dish["price"],
                            "sharers": [user_id],
                            "paid_by": []
                        })
                        ordered_names.append(dish["name"])
                if ordered_names:
                    WAITER_ORDERS.insert(0, {
                        "id": str(uuid.uuid4())[:6],
                        "time": datetime.now().strftime("%H:%M:%S"),
                        "user": user_id,
                        "text": f"🍽️ Нове замовлення з меню: {', '.join(ordered_names)}",
                        "status": "NEW"
                    })
                    await hub.broadcast_all(table_id)

            elif action == "pay_my_share":
                tip_grosze = int(float(msg.get("tip_pln", 0)) * 100)
                paid_amount = 0
                for item in TABLES_STATE[table_id]["items"]:
                    if user_id in item["sharers"] and user_id not in item["paid_by"]:
                        paid_amount += item["price"] // len(item["sharers"])
                        item["paid_by"].append(user_id)
                if paid_amount > 0 or tip_grosze > 0:
                    TABLES_STATE[table_id]["waiter"]["goal_current"] += tip_grosze
                    prediction = random.choice(PREDICTIONS)
                    WAITER_ORDERS.insert(0, {
                        "id": str(uuid.uuid4())[:6],
                        "time": datetime.now().strftime("%H:%M:%S"),
                        "user": user_id,
                        "text": f"💳 Оплата рахунку: {paid_amount/100:.2f} zł | Чайові: +{tip_grosze/100:.2f} zł",
                        "status": "PAID"
                    })
                    await websocket.send_text(json.dumps({
                        "event": "payment_success",
                        "prediction": prediction,
                        "paid_pln": (paid_amount + tip_grosze) / 100
                    }))
                await hub.broadcast_all(table_id)

    except WebSocketDisconnect:
        await hub.disconnect_guest(table_id, user_id)

@app.websocket("/ws/waiter/{pin}")
async def waiter_ws(websocket: WebSocket, pin: str):
    if pin != WAITER_PIN:
        await websocket.close(code=1008)
        return
    await hub.connect_waiter(websocket)
    try:
        while True:
            msg = json.loads(await websocket.receive_text())
            if msg.get("action") == "accept_order":
                for order in WAITER_ORDERS:
                    if order["id"] == msg["order_id"]:
                        order["status"] = "DONE"
                await hub.broadcast_waiter()
    except WebSocketDisconnect:
        hub.disconnect_waiter(websocket)

@app.get("/test/{user_id}", response_class=HTMLResponse)
def guest_ui(user_id: str):
    menu_json = json.dumps(MENU_CATALOG)
    html = """
    <!DOCTYPE html>
    <html>
    <head><meta name="viewport" content="width=device-width, initial-scale=1"></head>
    <body style="font-family: -apple-system, sans-serif; max-width: 430px; margin: 0 auto; padding: 15px 15px 90px 15px; background: #f4f5f7;">
        
        <!-- Шапка столу -->
        <div style="background: #111; color: #fff; padding: 14px; border-radius: 16px; margin-bottom: 12px; display:flex; justify-content:space-between; align-items:center;">
            <div>
                <div style="font-weight:bold; font-size:16px;">Стіл №5 • <span style="color:#4dabf7">__USER__</span></div>
                <div id="online" style="font-size:12px; color:#aaa; margin-top:2px;"></div>
            </div>
            <button onclick="spin()" style="background: linear-gradient(90deg,#ff6b6b,#f06595); color:#fff; border:none; padding:8px 12px; border-radius:10px; font-weight:bold; cursor:pointer; font-size:12px;">
                🎰 Рулетка
            </button>
        </div>
        <div id="roulette-banner" style="display:none; background:#fff3bf; color:#d9480f; padding:10px; border-radius:10px; margin-bottom:12px; font-weight:bold; text-align:center; font-size:14px;"></div>

        <!-- Вкладка 1: МЕНЮ ЗАКЛАДУ -->
        <div id="tab-menu" style="display:none;">
            <h3 style="margin: 5px 0 10px 0;">🍔 Меню — замовляй одразу за стіл</h3>
            <div id="menu-list"></div>
            <div id="cart-bar" style="display:none; background:#111; color:#fff; padding:14px; border-radius:14px; margin-top:12px; justify-content:space-between; align-items:center;">
                <span id="cart-text">Обрано: 0</span>
                <button onclick="submitOrder()" style="background:#12b886; color:#fff; border:none; padding:10px 16px; border-radius:10px; font-weight:bold; cursor:pointer;">
                    Замовити на стіл ➔
                </button>
            </div>
        </div>

        <!-- Вкладка 2: РАХУНОК ТА ЧАЙОВІ -->
        <div id="tab-bill">
            <div style="font-size:13px; color:#555; margin-bottom:8px;">
                👇 Натискай на свої страви (або діли з друзями):
            </div>
            <div id="items"></div>

            <!-- Картка Офіціанта з ціллю та прогрес-баром -->
            <div style="background:#fff; padding:15px; border-radius:16px; margin-top:14px; box-shadow:0 2px 8px rgba(0,0,0,0.05);">
                <div style="display:flex; align-items:center; gap:12px; margin-bottom:10px;">
                    <div id="w-avatar" style="font-size:32px; background:#f1f3f5; width:50px; height:50px; display:flex; align-items:center; justify-content:center; border-radius:50%;">🧑‍🍳</div>
                    <div style="flex:1;">
                        <div style="font-weight:bold; font-size:15px;" id="w-name">Олексій</div>
                        <div style="font-size:12px; color:#666;" id="w-goal">🏍️ Збираю на мотоцикл</div>
                    </div>
                </div>
                <div style="background:#e9ecef; height:8px; border-radius:4px; overflow:hidden; margin-bottom:4px;">
                    <div id="w-progress" style="background:#12b886; height:100%; width:80%; transition: width 0.4s;"></div>
                </div>
                <div id="w-progress-text" style="font-size:11px; color:#868e96; text-align:right; margin-bottom:12px;"></div>

                <div style="font-size:13px; font-weight:bold; margin-bottom:8px;">Залишити чайові офіціанту:</div>
                <div style="display:grid; grid-template-columns: repeat(4, 1fr); gap:6px; margin-bottom:10px;">
                    <button onclick="setTipMode(5)" id="btn-t5" style="padding:8px; border-radius:8px; border:1px solid #dee2e6; background:#fff; cursor:pointer; font-weight:bold;">5%</button>
                    <button onclick="setTipMode(10)" id="btn-t10" style="padding:8px; border-radius:8px; border:2px solid #12b886; background:#e6fcf5; cursor:pointer; font-weight:bold;">10% 🔥</button>
                    <button onclick="setTipMode(15)" id="btn-t15" style="padding:8px; border-radius:8px; border:1px solid #dee2e6; background:#fff; cursor:pointer; font-weight:bold;">15%</button>
                    <button onclick="setTipMode('custom')" id="btn-tcustom" style="padding:8px; border-radius:8px; border:1px solid #dee2e6; background:#fff; cursor:pointer; font-weight:bold;">Своя</button>
                </div>
                <input id="custom-tip-input" type="number" placeholder="Введіть суму чайових у zł (напр. 15)" oninput="recalcTotal()" style="display:none; width:100%; box-sizing:border-box; padding:10px; border-radius:8px; border:1px solid #ccc; margin-bottom:10px; font-size:14px;">

                <div style="border-top:1px solid #f1f3f5; padding-top:10px; margin-top:6px;">
                    <div style="display:flex; justify-content:space-between; font-size:14px; color:#555; margin-bottom:4px;">
                        <span>Страви + Чайові:</span>
                        <span id="breakdown-text">0.00 + 0.00 zł</span>
                    </div>
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
                        <span style="font-weight:bold;">Разом до сплати:</span>
                        <b id="my-total" style="font-size:20px; color:#111;">0.00 zł</b>
                    </div>
                    <button onclick="payNow()" style="width:100%; padding:14px; background:#111; color:white; font-size:16px; font-weight:bold; border:none; border-radius:12px; cursor:pointer;">
                         Pay / BLIK — Оплатити в 1 дотик
                    </button>
                </div>
            </div>
        </div>

        <!-- Модальне вікно передбачення як у Сільпо -->
        <div id="fortune-modal" style="display:none; position:fixed; inset:0; background:rgba(0,0,0,0.65); align-items:center; justify-content:center; padding:20px; z-index:100;">
            <div style="background:#fff; padding:24px; border-radius:20px; max-width:340px; text-align:center; box-shadow:0 10px 25px rgba(0,0,0,0.2);">
                <div style="font-size:42px; margin-bottom:8px;">🎉</div>
                <h3 style="margin:0 0 6px 0;">Оплата пройшла успішно!</h3>
                <div id="fortune-paid" style="font-size:13px; color:#666; margin-bottom:14px;"></div>
                <div style="background:#fff9db; border:1px dashed #fab005; padding:14px; border-radius:12px; font-size:14px; line-height:1.4; color:#212529; margin-bottom:16px;">
                    <b>🔮 Твоє передбачення на вечір:</b><br><br>
                    <span id="fortune-text"></span>
                </div>
                <button onclick="document.getElementById('fortune-modal').style.display='none'" style="width:100%; padding:12px; background:#12b886; color:#fff; border:none; border-radius:10px; font-weight:bold; cursor:pointer;">
                    Супер, дякую!
                </button>
            </div>
        </div>

        <!-- Нижній Таб-бар (Навігація) -->
        <div style="position:fixed; bottom:0; left:0; right:0; max-width:430px; margin:0 auto; background:#fff; border-top:1px solid #e9ecef; display:grid; grid-template-columns:1fr 1fr; padding:8px 15px; gap:10px;">
            <button id="nav-menu" onclick="switchTab('menu')" style="padding:10px; border-radius:10px; border:none; background:#f1f3f5; font-weight:bold; cursor:pointer;">
                📖 Меню (Замовити)
            </button>
            <button id="nav-bill" onclick="switchTab('bill')" style="padding:10px; border-radius:10px; border:none; background:#111; color:#fff; font-weight:bold; cursor:pointer;">
                🧾 Рахунок і Оплата
            </button>
        </div>

        <script>
            const user = "__USER__";
            const menuCatalog = __MENU__;
            let cart = [];
            let tipMode = 10;
            let mySubtotalPln = 0;

            const ws = new WebSocket("ws://" + location.host + "/ws/table/5/" + user);

            function renderMenu() {
                const list = document.getElementById("menu-list");
                list.innerHTML = "";
                menuCatalog.forEach(m => {
                    list.innerHTML += `
                        <div style="background:#fff; padding:12px; border-radius:12px; margin-bottom:8px; display:flex; justify-content:space-between; align-items:center;">
                            <div>
                                <div style="font-weight:bold; font-size:15px;">${m.name} — ${(m.price/100).toFixed(0)} zł</div>
                                <div style="font-size:12px; color:#666; margin-top:2px;">${m.desc}</div>
                            </div>
                            <button onclick="addToCart('${m.id}')" style="background:#f1f3f5; border:none; padding:8px 12px; border-radius:8px; font-weight:bold; cursor:pointer;">
                                ➕ Додати
                            </button>
                        </div>`;
                });
            }
            renderMenu();

            function addToCart(id) {
                cart.push(id);
                const bar = document.getElementById("cart-bar");
                bar.style.display = "flex";
                document.getElementById("cart-text").innerText = "У кошику позицій: " + cart.length;
            }

            function submitOrder() {
                if (!cart.length) return;
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
                if (tipMode === 'custom') {
                    return parseFloat(document.getElementById('custom-tip-input').value || 0);
                }
                return +(mySubtotalPln * (tipMode / 100)).toFixed(2);
            }

            function recalcTotal() {
                const tipPln = getTipPln();
                document.getElementById("breakdown-text").innerText = `${mySubtotalPln.toFixed(2)} zł + ${tipPln.toFixed(2)} zł чайові`;
                document.getElementById("my-total").innerText = (mySubtotalPln + tipPln).toFixed(2) + " zł";
            }

            ws.onmessage = (e) => {
                const data = JSON.parse(e.data);

                if (data.event === "payment_success") {
                    document.getElementById("fortune-paid").innerText = `Списано: ${data.paid_pln.toFixed(2)} zł • Чек закрито`;
                    document.getElementById("fortune-text").innerText = data.prediction;
                    document.getElementById("fortune-modal").style.display = "flex";
                    return;
                }

                const state = data.state;
                document.getElementById("online").innerText = "За столом: " + state.online_users.join(", ");

                // Оновлюємо профіль офіціанта
                const w = state.waiter;
                document.getElementById("w-name").innerText = w.name + " • " + w.role;
                document.getElementById("w-goal").innerText = w.goal_title;
                const pct = Math.min(100, Math.round((w.goal_current / w.goal_target) * 100));
                document.getElementById("w-progress").style.width = pct + "%";
                document.getElementById("w-progress-text").innerText = `Зібрано ${(w.goal_current/100).toFixed(0)} zł із ${(w.goal_target/100).toFixed(0)} zł (${pct}%)`;

                // Банер рулетки
                const rb = document.getElementById("roulette-banner");
                if (state.last_roulette) {
                    rb.style.display = "block";
                    rb.innerText = state.last_roulette;
                }

                // Рендеримо страви
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

                    let bg = "#fff";
                    let border = "1px solid #e9ecef";
                    let statusText = "Вільно — натисни, щоб обрати";

                    if (allPaid) {
                        bg = "#d3f9d8"; statusText = "✅ Оплачено (" + item.paid_by.join(", ") + ")";
                    } else if (count > 0) {
                        bg = isMine ? "#e7f5ff" : "#fff9db";
                        border = isMine ? "2px solid #339af0" : "1px solid #ffd43b";
                        statusText = count === 1
                            ? "Обрав: " + item.sharers[0]
                            : "🤝 Ділять на " + count + "-х (" + item.sharers.join(", ") + ") — по " + (sharePrice/100).toFixed(2) + " zł";
                    }

                    container.innerHTML += `
                        <div style="background:${bg}; border:${border}; padding:12px; margin-bottom:8px; border-radius:12px; display:flex; justify-content:space-between; align-items:center;">
                            <div onclick="toggle('${item.id}')" style="flex:1; cursor:pointer;">
                                <div style="font-weight:bold; font-size:15px;">${item.name} — ${(item.price/100).toFixed(0)} zł</div>
                                <div style="font-size:12px; color:#495057; margin-top:3px;">${statusText}</div>
                            </div>
                            <button onclick="repeatItem('${item.id}')" style="margin-left:10px; background:#212529; color:#fff; border:none; padding:8px 10px; border-radius:8px; font-size:12px; cursor:pointer;">
                                🔄 +1
                            </button>
                        </div>`;
                });

                mySubtotalPln = subtotalGrosze / 100;
                recalcTotal();
            };

            function toggle(id) { ws.send(JSON.stringify({action: "toggle_share", item_id: id})); }
            function spin() { ws.send(JSON.stringify({action: "spin_roulette"})); }
            function repeatItem(id) { ws.send(JSON.stringify({action: "repeat_item", item_id: id})); }
            function payNow() { ws.send(JSON.stringify({action: "pay_my_share", tip_pln: getTipPln()})); }
        </script>
    </body>
    </html>
    """
    return html.replace("__USER__", user_id).replace("__MENU__", menu_json)

@app.get("/waiter", response_class=HTMLResponse)
def waiter_ui():
    return """
    <!DOCTYPE html>
    <html>
    <head><title>Захищений Термінал Офіціанта</title></head>
    <body style="font-family: -apple-system, sans-serif; background:#121212; color:#fff; padding:20px;">
        <div id="login-box" style="max-width:320px; margin:80px auto; background:#1e1e1e; padding:24px; border-radius:16px; text-align:center;">
            <h3>🔒 Термінал Персоналу</h3>
            <p style="font-size:13px; color:#aaa;">Введіть PIN-код зміни (тестовий: <b>7777</b>)</p>
            <input id="pin-input" type="password" value="7777" style="width:100%; box-sizing:border-box; padding:10px; border-radius:8px; border:none; text-align:center; font-size:18px; margin-bottom:12px;">
            <button onclick="connectWaiter()" style="width:100%; padding:12px; background:#12b886; color:#fff; border:none; border-radius:8px; font-weight:bold; cursor:pointer;">Увійти в зміну</button>
        </div>

        <div id="pos-grid" style="display:none; grid-template-columns: 1fr 1fr; gap:20px;">
            <div style="background:#1e1e1e; padding:20px; border-radius:14px;">
                <h2 style="margin-top:0; color:#ff6b6b;">🔔 Замовлення з Меню та Оплати</h2>
                <div id="orders"></div>
            </div>
            <div style="background:#1e1e1e; padding:20px; border-radius:14px;">
                <h2 style="margin-top:0; color:#51cf66;">🖥️ Стан Столу №5</h2>
                <div id="summary" style="margin-bottom:15px; font-size:15px; color:#ccc;"></div>
                <div id="table-items"></div>
            </div>
        </div>

        <script>
            let ws;
            function connectWaiter() {
                const pin = document.getElementById("pin-input").value;
                ws = new WebSocket("ws://" + location.host + "/ws/waiter/" + pin);
                ws.onopen = () => {
                    document.getElementById("login-box").style.display = "none";
                    document.getElementById("pos-grid").style.display = "grid";
                };
                ws.onclose = () => alert("Невірний PIN-код або сесію закрито!");
                ws.onmessage = (e) => {
                    const data = JSON.parse(e.data);
                    const ordersEl = document.getElementById("orders");
                    ordersEl.innerHTML = data.orders.length ? "" : "<p style='color:#777'>Очікування дій гостей...</p>";
                    data.orders.forEach(o => {
                        const bg = o.status === "NEW" ? "#c92a2a" : (o.status === "PAID" ? "#2b8a3e" : "#2c2e33");
                        const btn = o.status === "NEW" ? `<button onclick="accept('${o.id}')" style="background:#fff; color:#000; border:none; padding:6px 10px; border-radius:6px; font-weight:bold; cursor:pointer;">Прийняти на кухню</button>` : `<span>✅ Готово</span>`;
                        ordersEl.innerHTML += `
                            <div style="background:${bg}; padding:12px; border-radius:10px; margin-bottom:10px; display:flex; justify-content:space-between; align-items:center;">
                                <div><b>[${o.time}] Гість ${o.user}:</b><br>${o.text}</div>
                                ${btn}
                            </div>`;
                    });
                    const t = data.table;
                    document.getElementById("summary").innerHTML = `Гості онлайн: <b>${t.online_users.join(", ") || "немає"}</b> | Баланс цілі офіціанта: <b style="color:#ffd43b">${(t.waiter.goal_current/100).toFixed(2)} zł</b>`;
                    const itemsEl = document.getElementById("table-items");
                    itemsEl.innerHTML = "";
                    t.items.forEach(i => {
                        const status = (i.sharers.length > 0 && i.paid_by.length === i.sharers.length)
                            ? "🟢 ОПЛАЧЕНО"
                            : (i.sharers.length ? "🟡 Ділять: " + i.sharers.join(", ") : "⚪ Не обрано");
                        itemsEl.innerHTML += `<div style="padding:8px; border-bottom:1px solid #333; display:flex; justify-content:space-between;">
                            <span>${i.name} (${i.price/100} zł)</span><span>${status}</span>
                        </div>`;
                    });
                };
            }
            function accept(id) { ws.send(JSON.stringify({action: "accept_order", order_id: id})); }
        </script>
    </body>
    </html>
    """