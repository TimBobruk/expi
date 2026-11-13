import random
import uuid
from datetime import datetime

WAITER_PIN = "7777"

MENU_CATALOG = [
    {"id": "m1", "name": "🍔 Смеш-бургер Трюфельний", "price": 4200, "badge": "🔥 Хіт: замовили 18 разів сьогодні", "desc": "Подвійна яловичина, чеддер, трюфельний айолі"},
    {"id": "m2", "name": "🍟 Батат фрі з пармезаном", "price": 2400, "badge": "⚡ Подача за 5 хв • Ідеально до бургера", "desc": "Подається з соусом манго-чилі"},
    {"id": "m3", "name": "🍹 Коктейль Pornstar Martini", "price": 3800, "badge": "💎 Вибір гостей №1 цього вечора", "desc": "Ванільна горілка, маракуйя, шот просекко"},
    {"id": "m4", "name": "💨 Кальян Darkside (Спільний)", "price": 8000, "badge": "🤝 Найчастіше ділять на компанію", "desc": "Ягідний, цитрусовий або пряний мікс"},
]

PREDICTIONS_REGULAR = [
    "✨ Сьогодні вечір принесе тобі новину, яка зарядить настроєм на весь тиждень!",
    "🚀 Ідея, яку ти обговорював за цим столом — вистрілить. Час діяти!",
    "💸 Гроші, витрачені з кайфом у гарній компанії, повертаються у подвійному розмірі!",
    "🎯 Наступні 48 годин принесуть дуже вигідне знайомство."
]

PREDICTIONS_BOSS = [
    "👑 СТАТУС: ЛЕГЕНДА СТОЛУ! Щедрість такого рівня повертається x10 у карму та гаманець!",
    "🦁 Ти закрив цей стіл як справжній бос. Цього місяця чекай на великий фінансовий прорив!"
]

WAITER_PROFILE = {
    "name": "Олексій (Alex)",
    "role": "Старший зміни",
    "goal_title": "🏍️ Збираю на мотоцикл BMW GS",
    "goal_current": 485000,
    "goal_target": 600000,
    "streak": 3,
    "xp": 340
}

TABLES_STATE = {
    1: {
        "id": 1, "name": "Стіл №1 (Біля вікна)", "seats": 2, "status": "free",
        "online_users": [], "split_mode": "custom", "last_roulette": None,
        "booking": {"time": "19:00", "name": "Марія", "guests": 2, "occasion": "❤️ Побачення", "note": "Поставити свічку", "tg_confirmed": True},
        "items": []
    },
    2: {
        "id": 2, "name": "Стіл №2 (Центр залу)", "seats": 4, "status": "free",
        "online_users": [], "split_mode": "custom", "last_roulette": None,
        "booking": None, "items": []
    },
    3: {
        "id": 3, "name": "Стіл №3 (VIP Дивани)", "seats": 6, "status": "reserved",
        "online_users": [], "split_mode": "custom", "last_roulette": None,
        "booking": {"time": "18:30", "name": "Артем", "guests": 6, "occasion": "🎂 День народження", "note": "Десерт зі свічкою", "tg_confirmed": False},
        "items": []
    },
    5: {
        "id": 5, "name": "Стіл №5 (Лаунж-тераса)", "seats": 4, "status": "occupied",
        "online_users": [], "split_mode": "custom", "last_roulette": None,
        "booking": {"time": "21:00", "name": "Максим", "guests": 4, "occasion": "🍻 Зустріч друзів", "note": "Люблять димний кальян", "tg_confirmed": True},
        "items": [
            {"id": "1", "name": "🍹 Коктейль Негроні", "price": 3600, "sharers": [], "paid_by": []},
            {"id": "2", "name": "🍹 Апероль Шприц", "price": 3400, "sharers": [], "paid_by": []},
            {"id": "3", "name": "🍕 Піца Чотири Сири", "price": 5200, "sharers": [], "paid_by": []},
            {"id": "4", "name": "💨 Кальян Darkside", "price": 8000, "sharers": [], "paid_by": []},
        ]
    }
}

WAITER_ORDERS = []

def get_psycho_radar(table: dict) -> str:
    """Генерує психологічну підказку для офіціанта на основі дій гостей"""
    unpaid = [i for i in table["items"] if not i["paid_by"] or len(i["paid_by"]) < len(i["sharers"])]
    if table["split_mode"] == "boss":
        return "👑 Один гість закриває весь стіл сам! Обов'язково подякуй йому особисто при виході."
    if table["split_mode"] == "equal" and unpaid:
        return "⚖️ Гості поділили чек порівну в телефонах і зараз оплачують — не неси термінал."
    if table["online_users"] and not table["items"]:
        return "👀 Дивляться меню з телефону — підійди через 1 хв і порадь фірмовий коктейль (+30% до чека)."
    if table["online_users"] and any(i["sharers"] for i in unpaid):
        return "📱 Активно обирають свої позиції для оплати онлайн."
    if table["booking"] and "Побачення" in table["booking"]["occasion"]:
        return "❤️ Режим побачення: мінімум втручання, запропонуй два просекко або десерт на двох."
    return "✨ Спокійна посадка — підтримуй візуальний контакт."

def apply_split_equally(table_id: int):
    """Режим 1 (TypeScript фіча): Поділити весь неоплачений чек порівну на всіх онлайн гостей"""
    table = TABLES_STATE[table_id]
    users = table["online_users"] or ["Tim", "Friend"]
    table["split_mode"] = "equal"
    for item in table["items"]:
        if not item["paid_by"]:
            item["sharers"] = list(users)

def apply_boss_mode(table_id: int, boss_user: str):
    """Режим 2 (TypeScript фіча): Закрити весь стіл самому в 1 клік"""
    table = TABLES_STATE[table_id]
    table["split_mode"] = "boss"
    for item in table["items"]:
        if not item["paid_by"]:
            item["sharers"] = [boss_user]

def log_event(table_id: int, user: str, text: str, status: str = "NEW"):
    WAITER_ORDERS.insert(0, {
        "id": str(uuid.uuid4())[:6],
        "time": datetime.now().strftime("%H:%M:%S"),
        "table_id": table_id,
        "user": user,
        "text": text,
        "status": status
    })