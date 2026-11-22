import asyncio
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ChatMemberUpdated, LabeledPrice
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

import db
import repo
import requests as _requests

TOKEN = os.getenv("BOT_TOKEN", "9189699629:AAGfWNQsQnHJ5KhsUwCYKYNtNvKDV823csA")
GROUP_LINK = os.getenv("GROUP_LINK", "https://t.me/ExtraSMG")
ADMIN_IDS = [x.strip() for x in os.getenv("ADMIN_IDS", os.getenv("ADMIN_ID", "8605631121")).split(",") if x.strip()]

bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

class States(StatesGroup):
    search = State()
    add_friend = State()
    # admin
    adm_user_id = State()
    adm_give_balance = State()
    adm_give_number = State()
    adm_give_product = State()
    adm_give_user = State()
    adm_broadcast = State()
    adm_find = State()
    adm_add_admin = State()

def is_admin(uid):
    return str(uid) in ADMIN_IDS or repo.is_admin(uid)

FIREBASE_URL = os.getenv("FIREBASE_URL", "https://extrasmg-83e16-default-rtdb.europe-west1.firebasedatabase.app")
FIREBASE_SECRET = os.getenv("FIREBASE_SECRET", "")

def firebase_put(path, data):
    try:
        url = f"{FIREBASE_URL}/{path}.json"
        params = {}
        if FIREBASE_SECRET:
            params["auth"] = FIREBASE_SECRET
        resp = _requests.put(url, json=data, params=params, timeout=10)
        if not resp.ok:
            print("firebase_put failed:", path, resp.status_code, resp.text)
            return False
        return True
    except Exception as e:
        print("firebase_put error:", path, e)
        return False

def gen_code():
    import random
    return "".join(str(random.randint(0, 9)) for _ in range(5))

def ensure_code(number, owner=None, typ=None):
    key = number.replace(" ", "")
    data = None
    try:
        r = _requests.get(f"{FIREBASE_URL}/botNumbers/{key}.json", timeout=10)
        if r.ok:
            data = r.json()
    except Exception:
        data = None
    code = gen_code()
    payload = data if isinstance(data, dict) else {}
    payload["code"] = code
    if owner is not None:
        payload.setdefault("owner", owner)
    if typ is not None:
        payload.setdefault("type", typ)
    payload.setdefault("ts", __import__("datetime").datetime.utcnow().isoformat())
    firebase_put(f"botNumbers/{key}", payload)
    return code

def main_menu(uid=None):
    kb = [
        [InlineKeyboardButton(text="📱 Получить номер +39 (бесплатно)", callback_data="free_number")],
        [InlineKeyboardButton(text="📱 Мои номера", callback_data="my_number")],
        [InlineKeyboardButton(text="🛒 Купить номер +888 (75 ⭐)", callback_data="buy_number")],
        [InlineKeyboardButton(text="🛍 Магазин", callback_data="shop")],
        [InlineKeyboardButton(text="🔍 Поиск аккаунтов", callback_data="search")],
        [InlineKeyboardButton(text="👥 Друзья", callback_data="friends")],
        [InlineKeyboardButton(text="📢 Официальный канал", callback_data="group")],
        [InlineKeyboardButton(text="ℹ️ Помощь", callback_data="help")],
    ]
    if uid is not None and is_admin(uid):
        kb.append([InlineKeyboardButton(text="🛠 Админ-панель", callback_data="admin_panel")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def back_kb():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="menu")]])

def admin_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="adm_stats")],
        [InlineKeyboardButton(text="🔍 Найти пользователя", callback_data="adm_find")],
        [InlineKeyboardButton(text="👥 Список пользователей", callback_data="adm_users")],
        [InlineKeyboardButton(text="💰 Выдать баланс", callback_data="adm_givebal")],
        [InlineKeyboardButton(text="📞 Выдать номер", callback_data="adm_givenum")],
        [InlineKeyboardButton(text="🛍 Выдать товар", callback_data="adm_giveprod")],
        [InlineKeyboardButton(text="➕ Выдать доп. юзера", callback_data="adm_giveuser")],
        [InlineKeyboardButton(text="🛡 Управление админами", callback_data="adm_admins")],
        [InlineKeyboardButton(text="➕ Добавить админа", callback_data="adm_addadmin")],
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="adm_broadcast")],
        [InlineKeyboardButton(text="⛔ Бан/разбан", callback_data="adm_ban")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu")],
    ])

# ---------- START ----------
@dp.message(CommandStart())
async def cmd_start(message: Message):
    repo.upsert_user(message.from_user.id, message.from_user.username, message.from_user.first_name, message.from_user.last_name)
    uname = message.from_user.username or f"user{message.from_user.id}"
    repo.ensure_account(message.from_user.id, uname, message.from_user.first_name)
    if is_admin(message.from_user.id):
        try:
            repo.set_admin(message.from_user.id, 1)
        except Exception:
            pass
    await message.answer(
        f"Привет, {message.from_user.first_name or 'друг'}! 👋\n\n"
        "Добро пожаловать в Messenger888.\n"
        "• Бесплатный номер +39\n"
        "• Номер +888 за звёзды\n"
        "• Магазин, друзья, поиск\n\n"
        "Стартовый баланс: 1000 монет.",
        reply_markup=main_menu(message.from_user.id)
    )

@dp.callback_query(F.data == "menu")
async def cb_menu(cb: CallbackQuery):
    await cb.message.edit_text("Главное меню:", reply_markup=main_menu(cb.from_user.id))
    await cb.answer()

# ---------- NUMBERS ----------
@dp.callback_query(F.data == "free_number")
async def cb_free_number(cb: CallbackQuery):
    nums = repo.get_user_numbers(cb.from_user.id)
    existing = [n for n in nums if str(n.get("number","")).startswith("+39")]
    if existing:
        num = existing[0]["number"]
        code = ensure_code(num, cb.from_user.id, "+39")
        await cb.message.edit_text(f"✅ Твой бесплатный номер: {num}\nКод для входа в мессенджер: {code}", reply_markup=back_kb())
        try:
            await bot.send_message(cb.from_user.id, f"✅ Твой бесплатный номер: {num}\nКод для входа в мессенджер: {code}")
        except Exception:
            pass
        await cb.answer()
        return
    num = repo.get_free_number(cb.from_user.id)
    if not num:
        await cb.answer("Нет доступных номеров +39", show_alert=True)
        return
    code = gen_code()
    firebase_put(f"botNumbers/{num['number'].replace(' ','')}", {"owner": cb.from_user.id, "type": "+39", "code": code, "ts": __import__("datetime").datetime.utcnow().isoformat()})
    await cb.message.edit_text(f"✅ Тебе выдан бесплатный номер: {num['number']}\nКод для входа в мессенджер: {code}", reply_markup=back_kb())
    try:
        await bot.send_message(cb.from_user.id, f"✅ Тебе выдан бесплатный номер: {num['number']}\nКод для входа в мессенджер: {code}")
    except Exception:
        pass
    await cb.answer()

@dp.callback_query(F.data == "my_number")
async def cb_my_number(cb: CallbackQuery):
    nums = repo.get_user_numbers(cb.from_user.id)
    if not nums:
        text = "У тебя пока нет номеров.\nПолучи бесплатный +39 или купи +888."
    else:
        lines = []
        for n in nums:
            code = ensure_code(n["number"], cb.from_user.id, n["number"].split()[0] if " " in n["number"] else None)
            lines.append(f"• {n['number']} — код: {code}")
        text = "Твои номера:\n" + "\n".join(lines)
    await cb.message.edit_text(text, reply_markup=back_kb())
    await cb.answer()

@dp.callback_query(F.data == "buy_number")
async def cb_buy_number(cb: CallbackQuery):
    await bot.send_invoice(
        chat_id=cb.from_user.id,
        title="Номер +888",
        description="Случайный номер +888 для мессенджера",
        payload="number",
        currency="XTR",
        prices=[LabeledPrice(label="Номер +888", amount=75)],
        provider_token="",
    )
    await cb.answer()

# ---------- SHOP ----------
@dp.callback_query(F.data == "shop")
async def cb_shop(cb: CallbackQuery):
    products = repo.get_products()
    kb = []
    for p in products:
        stars = p.get("price_stars") or 50
        kb.append([InlineKeyboardButton(text=f"{p['name']} — {stars} ⭐", callback_data=f"buyprod_stars_{p['id']}")])
    kb.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="menu")])
    await cb.message.edit_text("🛍 Магазин (оплата звёздами):", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await cb.answer()

@dp.callback_query(F.data.startswith("buyprod_stars_"))
async def cb_buyprod_stars(cb: CallbackQuery):
    pid = int(cb.data.split("_")[2])
    products = repo.get_products()
    prod = next((p for p in products if p["id"] == pid), None)
    if not prod or prod["stock"] <= 0:
        await cb.answer("Товар закончился", show_alert=True)
        return
    stars = prod.get("price_stars") or 50
    await bot.send_invoice(
        chat_id=cb.from_user.id,
        title=prod["name"],
        description=prod["description"],
        payload=f"product:{pid}",
        currency="XTR",
        prices=[LabeledPrice(label=prod["name"], amount=stars)],
        provider_token="",
    )
    await cb.answer()

# ---------- SEARCH ----------
@dp.callback_query(F.data == "search")
async def cb_search(cb: CallbackQuery, state: FSMContext):
    await state.set_state(States.search)
    await cb.message.edit_text("Введи имя/username для поиска аккаунтов:", reply_markup=back_kb())
    await cb.answer()

@dp.message(States.search)
async def process_search(message: Message, state: FSMContext):
    q = message.text.strip()
    results = repo.search_accounts(q)
    if not results:
        await message.answer("Ничего не найдено.", reply_markup=back_kb())
    else:
        lines = []
        for r in results:
            lines.append(f"• {r['display_name']} (@{r['username']}) — id {r['owner_id']}")
        await message.answer("Результаты:\n" + "\n".join(lines), reply_markup=back_kb())
    await state.clear()

# ---------- FRIENDS ----------
@dp.callback_query(F.data == "friends")
async def cb_friends(cb: CallbackQuery):
    friends = repo.get_friends(cb.from_user.id)
    pending = repo.get_pending_requests(cb.from_user.id)
    text = "👥 Друзья:\n"
    if friends:
        text += "\n".join(f"• {f.get('first_name') or f.get('username')} (id {f['friend_id']})" for f in friends) + "\n"
    else:
        text += "Пока нет друзей.\n"
    kb = [[InlineKeyboardButton(text="➕ Добавить друга", callback_data="add_friend")]]
    if pending:
        text += "\nЗапросы в друзья:\n"
        for p in pending:
            text += f"• {p.get('first_name') or p.get('username')} (id {p['user_id']})\n"
            kb.append([InlineKeyboardButton(text=f"✅ Принять {p['user_id']}", callback_data=f"accept_{p['id']}")])
    kb.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="menu")])
    await cb.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await cb.answer()

@dp.callback_query(F.data == "add_friend")
async def cb_add_friend(cb: CallbackQuery, state: FSMContext):
    await state.set_state(States.add_friend)
    await cb.message.edit_text("Введи Telegram ID друга:", reply_markup=back_kb())
    await cb.answer()

@dp.message(States.add_friend)
async def process_add_friend(message: Message, state: FSMContext):
    try:
        fid = int(message.text.strip())
    except ValueError:
        await message.answer("ID должен быть числом")
        await state.clear()
        return
    repo.upsert_user(fid)
    ok, status = repo.send_friend_request(message.from_user.id, fid)
    if ok:
        await message.answer("Запрос отправлен!", reply_markup=back_kb())
    else:
        await message.answer(f"Не удалось: {status}", reply_markup=back_kb())
    await state.clear()

@dp.callback_query(F.data.startswith("accept_"))
async def cb_accept(cb: CallbackQuery):
    rid = int(cb.data.split("_")[1])
    repo.respond_friend(rid, True)
    await cb.answer("Принято!", show_alert=True)
    await cb_friends(cb)

# ---------- GROUP ----------
@dp.callback_query(F.data == "group")
async def cb_group(cb: CallbackQuery):
    await cb.message.edit_text(f"📢 Официальный канал: {GROUP_LINK}\n\nПрисоединяйся!", reply_markup=back_kb())
    await cb.answer()

@dp.message(Command("setgroup"))
async def cmd_setgroup(message: Message):
    if message.chat.type not in ("group", "supergroup", "channel"):
        await message.answer("Команду нужно выполнить в группе/канале, где бот — админ.")
        return
    if not is_admin(message.from_user.id):
        await message.answer("Только админ.")
        return
    try:
        link = await bot.create_chat_invite_link(message.chat.id, name="Official")
        db.set_setting("group_link", link.invite_link)
        global GROUP_LINK
        GROUP_LINK = link.invite_link
        await message.answer(f"Группа установлена: {link.invite_link}")
    except Exception as e:
        await message.answer(f"Не удалось создать ссылку: {e}")

@dp.my_chat_member()
async def on_bot_added(event: ChatMemberUpdated):
    if event.new_chat_member.status in ("administrator", "member"):
        try:
            link = await bot.create_chat_invite_link(event.chat.id, name="Official")
            db.set_setting("group_link", link.invite_link)
            global GROUP_LINK
            GROUP_LINK = link.invite_link
        except Exception:
            pass

# ---------- PAYMENTS ----------
@dp.pre_checkout_query()
async def pre_checkout(query):
    await query.answer(ok=True)

@dp.message(F.successful_payment)
async def successful_payment(message: Message):
    sp = message.successful_payment
    payload = sp.invoice_payload
    if payload == "number":
        num = repo.buy_number(message.from_user.id)
        if num:
            code = gen_code()
            firebase_put(f"botNumbers/{num['number'].replace(' ','')}", {"owner": message.from_user.id, "type": "+888", "code": code, "ts": __import__("datetime").datetime.utcnow().isoformat()})
            await message.answer(f"✅ Оплата прошла! Тебе выдан номер: {num['number']}\nКод для входа в мессенджер: {code}", reply_markup=back_kb())
        else:
            await message.answer("Оплата прошла, но номеров +888 нет. Обратись к админу.", reply_markup=back_kb())
    elif payload.startswith("product:"):
        pid = int(payload.split(":")[1])
        prod = repo.issue_product(message.from_user.id, pid)
        if prod:
            text = f"✅ Оплата прошла! Куплено: {prod['name']}"
            issued = prod.get("issued_number")
            if issued:
                code = gen_code()
                firebase_put(f"botNumbers/{issued.replace(' ','')}", {"owner": message.from_user.id, "type": "+888", "code": code, "ts": __import__("datetime").datetime.utcnow().isoformat()})
                text += f"\nНомер: {issued}\nКод для входа в мессенджер: {code}"
            await message.answer(text, reply_markup=back_kb())
        else:
            await message.answer("Оплата прошла, но товар не найден.", reply_markup=back_kb())

# ---------- ADMIN PANEL ----------
@dp.callback_query(F.data == "admin_panel")
async def cb_admin_panel(cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        await cb.answer("Нет доступа", show_alert=True)
        return
    await cb.message.edit_text("🛠 Админ-панель:", reply_markup=admin_menu())
    await cb.answer()

@dp.callback_query(F.data == "adm_stats")
async def cb_adm_stats(cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        await cb.answer("Нет доступа", show_alert=True)
        return
    s = repo.get_stats()
    text = (f"📊 Статистика:\n"
            f"Пользователей: {s['users']}\n"
            f"Номеров всего: {s['numbers']}\n"
            f"Продано: {s['sold_numbers']}\n"
            f"Товаров: {s['products']}")
    await cb.message.edit_text(text, reply_markup=admin_menu())
    await cb.answer()

@dp.callback_query(F.data == "adm_find")
async def cb_adm_find(cb: CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        await cb.answer("Нет доступа", show_alert=True)
        return
    await state.set_state(States.adm_find)
    await cb.message.edit_text("Введи ID или username пользователя:", reply_markup=back_kb())
    await cb.answer()

@dp.message(States.adm_find)
async def process_adm_find(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await state.clear(); return
    q = message.text.strip()
    user = None
    try:
        uid = int(q)
        user = repo.get_user(uid)
    except ValueError:
        # search by username in accounts
        res = repo.search_accounts(q)
        if res:
            user = repo.get_user(res[0]["owner_id"])
    if not user:
        await message.answer("Пользователь не найден.", reply_markup=admin_menu())
        await state.clear()
        return
    nums = repo.get_user_numbers(user["id"])
    text = (f"👤 Пользователь:\n"
            f"ID: {user['id']}\n"
            f"Имя: {user.get('first_name')}\n"
            f"Username: {user.get('username')}\n"
            f"Баланс: {user.get('balance',0)} монет\n"
            f"Админ: {bool(user.get('is_admin'))}\n"
            f"Номера: {', '.join(n['number'] for n in nums) if nums else 'нет'}")
    await message.answer(text, reply_markup=admin_menu())
    await state.clear()

@dp.callback_query(F.data == "adm_users")
async def cb_adm_users(cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        await cb.answer("Нет доступа", show_alert=True)
        return
    users = repo.get_all_users(40)
    lines = [f"{u['id']} — {u.get('first_name') or u.get('username') or '?'} (баланс {u.get('balance',0)})" for u in users]
    await cb.message.edit_text("Последние пользователи:\n" + "\n".join(lines), reply_markup=admin_menu())
    await cb.answer()

@dp.callback_query(F.data == "adm_givebal")
async def cb_adm_givebal(cb: CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        await cb.answer("Нет доступа", show_alert=True)
        return
    await state.set_state(States.adm_give_balance)
    await cb.message.edit_text("Введи: <user_id> <amount>", reply_markup=back_kb())
    await cb.answer()

@dp.message(States.adm_give_balance)
async def process_adm_give_balance(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await state.clear(); return
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Формат: <user_id> <amount>")
        await state.clear(); return
    try:
        uid = int(parts[0]); amount = int(parts[1])
    except ValueError:
        await message.answer("Неверные числа")
        await state.clear(); return
    repo.upsert_user(uid)
    repo.add_balance(uid, amount)
    await message.answer(f"✅ Выдано {amount} монет пользователю {uid}", reply_markup=admin_menu())
    await state.clear()

@dp.callback_query(F.data == "adm_givenum")
async def cb_adm_givenum(cb: CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        await cb.answer("Нет доступа", show_alert=True)
        return
    await state.set_state(States.adm_give_number)
    await cb.message.edit_text("Введи: <user_id> [prefix +888/+39]", reply_markup=back_kb())
    await cb.answer()

@dp.message(States.adm_give_number)
async def process_adm_give_number(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await state.clear(); return
    parts = message.text.split()
    if len(parts) < 1:
        await message.answer("Формат: <user_id> [prefix]")
        await state.clear(); return
    try:
        uid = int(parts[0])
    except ValueError:
        await message.answer("Неверный ID")
        await state.clear(); return
    prefix = parts[1] if len(parts) > 1 else "+888"
    repo.upsert_user(uid)
    num = repo.issue_number(uid, prefix)
    code = gen_code()
    firebase_put(f"botNumbers/{num['number'].replace(' ','')}", {"owner": uid, "type": prefix, "code": code, "ts": __import__("datetime").datetime.utcnow().isoformat()})
    await message.answer(f"✅ Выдан номер {num['number']} пользователю {uid}\nКод для входа: {code}", reply_markup=admin_menu())
    try:
        await bot.send_message(uid, f"✅ Вам выдан номер: {num['number']}\nКод для входа в мессенджер: {code}")
    except Exception:
        pass
    await state.clear()

@dp.callback_query(F.data == "adm_giveprod")
async def cb_adm_giveprod(cb: CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        await cb.answer("Нет доступа", show_alert=True)
        return
    await state.set_state(States.adm_give_product)
    await cb.message.edit_text("Введи: <user_id> <product_id>", reply_markup=back_kb())
    await cb.answer()

@dp.message(States.adm_give_product)
async def process_adm_give_product(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await state.clear(); return
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Формат: <user_id> <product_id>")
        await state.clear(); return
    try:
        uid = int(parts[0]); pid = int(parts[1])
    except ValueError:
        await message.answer("Неверные числа")
        await state.clear(); return
    repo.upsert_user(uid)
    prod = repo.issue_product(uid, pid)
    if prod:
        text = f"✅ Выдан товар {prod['name']} пользователю {uid}"
        issued = prod.get("issued_number")
        if issued:
            code = gen_code()
            firebase_put(f"botNumbers/{issued.replace(' ','')}", {"owner": uid, "type": "+888", "code": code, "ts": __import__("datetime").datetime.utcnow().isoformat()})
            text += f"\nНомер: {issued}\nКод для входа: {code}"
            try:
                await bot.send_message(uid, f"✅ Вам выдан номер: {issued}\nКод для входа в мессенджер: {code}")
            except Exception:
                pass
        await message.answer(text, reply_markup=admin_menu())
    else:
        await message.answer("Товар не найден.", reply_markup=admin_menu())
    await state.clear()

@dp.callback_query(F.data == "adm_giveuser")
async def cb_adm_giveuser(cb: CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        await cb.answer("Нет доступа", show_alert=True)
        return
    await state.set_state(States.adm_give_user)
    await cb.message.edit_text("Введи ID нового пользователя для выдачи (доп. юзер):", reply_markup=back_kb())
    await cb.answer()

@dp.message(States.adm_give_user)
async def process_adm_give_user(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await state.clear(); return
    try:
        uid = int(message.text.strip())
    except ValueError:
        await message.answer("ID должен быть числом")
        await state.clear(); return
    repo.upsert_user(uid)
    num = repo.get_free_number(uid)
    uname = f"user{uid}"
    repo.ensure_account(uid, uname, f"User{uid}")
    text = f"✅ Выдан доп. юзер {uid}\nБаланс: 0 монет"
    if num:
        code = gen_code()
        firebase_put(f"botNumbers/{num['number'].replace(' ','')}", {"owner": uid, "type": "+39", "code": code, "ts": __import__("datetime").datetime.utcnow().isoformat()})
        text += f"\nНомер: {num['number']}\nКод для входа: {code}"
        try:
            await bot.send_message(uid, f"✅ Вам выдан номер: {num['number']}\nКод для входа в мессенджер: {code}")
        except Exception:
            pass
    await message.answer(text, reply_markup=admin_menu())
    await state.clear()

@dp.callback_query(F.data == "adm_admins")
async def cb_adm_admins(cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        await cb.answer("Нет доступа", show_alert=True)
        return
    text = "Админы: " + ", ".join(ADMIN_IDS) + "\n\nДобавить: кнопка ниже или /setadmin <id>"
    await cb.message.edit_text(text, reply_markup=admin_menu())
    await cb.answer()

@dp.callback_query(F.data == "adm_addadmin")
async def cb_adm_addadmin(cb: CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        await cb.answer("Нет доступа", show_alert=True)
        return
    await state.set_state(States.adm_add_admin)
    await cb.message.edit_text("Введи Telegram ID нового админа:", reply_markup=back_kb())
    await cb.answer()

@dp.message(States.adm_add_admin)
async def process_adm_add_admin(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await state.clear(); return
    try:
        uid = int(message.text.strip())
    except ValueError:
        await message.answer("ID должен быть числом")
        await state.clear(); return
    repo.upsert_user(uid)
    repo.set_admin(uid, 1)
    if str(uid) not in ADMIN_IDS:
        ADMIN_IDS.append(str(uid))
    await message.answer(f"✅ Пользователь {uid} теперь админ. Он может открыть /admin", reply_markup=admin_menu())
    await state.clear()

@dp.message(Command("setadmin"))
async def cmd_setadmin(message: Message):
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Использование: /setadmin <user_id>")
        return
    try:
        uid = int(parts[1])
    except ValueError:
        await message.answer("Неверный ID")
        return
    repo.upsert_user(uid)
    repo.set_admin(uid, 1)
    if str(uid) not in ADMIN_IDS:
        ADMIN_IDS.append(str(uid))
    await message.answer(f"✅ {uid} теперь админ.")

@dp.callback_query(F.data == "adm_broadcast")
async def cb_adm_broadcast(cb: CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        await cb.answer("Нет доступа", show_alert=True)
        return
    await state.set_state(States.adm_broadcast)
    await cb.message.edit_text("Введи текст рассылки:", reply_markup=back_kb())
    await cb.answer()

@dp.message(States.adm_broadcast)
async def process_adm_broadcast(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await state.clear(); return
    users = repo.get_all_users(10000)
    sent = 0
    for u in users:
        try:
            await bot.send_message(u["id"], f"📢 Рассылка:\n{message.text}")
            sent += 1
        except Exception:
            pass
    await message.answer(f"✅ Отправлено {sent} пользователям.", reply_markup=admin_menu())
    await state.clear()

@dp.callback_query(F.data == "adm_ban")
async def cb_adm_ban(cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        await cb.answer("Нет доступа", show_alert=True)
        return
    await cb.message.edit_text("Используй команды:\n/ban <id>\n/unban <id>", reply_markup=admin_menu())
    await cb.answer()

# ---------- COMMANDS ----------
@dp.message(Command("admin"))
async def cmd_admin(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("Нет доступа.")
        return
    await message.answer("🛠 Админ-панель:", reply_markup=admin_menu())

@dp.message(Command("ban"))
async def cmd_ban(message: Message):
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Использование: /ban <user_id>")
        return
    try:
        uid = int(parts[1])
    except ValueError:
        await message.answer("Неверный ID")
        return
    repo.set_admin(uid, 0)
    await message.answer(f"⛔ Пользователь {uid} заблокирован (админ-права сняты).")

@dp.message(Command("unban"))
async def cmd_unban(message: Message):
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Использование: /unban <user_id>")
        return
    try:
        uid = int(parts[1])
    except ValueError:
        await message.answer("Неверный ID")
        return
    await message.answer(f"✅ Пользователь {uid} разблокирован.")

@dp.message(Command("give_balance"))
async def cmd_give_balance(message: Message):
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split()
    if len(parts) < 3:
        await message.answer("Использование: /give_balance <user_id> <amount>")
        return
    try:
        uid = int(parts[1]); amount = int(parts[2])
    except ValueError:
        await message.answer("Неверные числа")
        return
    repo.upsert_user(uid)
    repo.add_balance(uid, amount)
    await message.answer(f"✅ Выдано {amount} монет {uid}")

@dp.message(Command("give_number"))
async def cmd_give_number(message: Message):
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Использование: /give_number <user_id> [+888/+39]")
        return
    try:
        uid = int(parts[1])
    except ValueError:
        await message.answer("Неверный ID")
        return
    prefix = parts[2] if len(parts) > 2 else "+888"
    repo.upsert_user(uid)
    num = repo.issue_number(uid, prefix)
    code = gen_code()
    firebase_put(f"botNumbers/{num['number'].replace(' ','')}", {"owner": uid, "type": prefix, "code": code, "ts": __import__("datetime").datetime.utcnow().isoformat()})
    await message.answer(f"✅ Выдан номер {num['number']} пользователю {uid}\nКод для входа: {code}")
    try:
        await bot.send_message(uid, f"✅ Вам выдан номер: {num['number']}\nКод для входа в мессенджер: {code}")
    except Exception:
        pass

@dp.message(Command("addfriend"))
async def cmd_addfriend(message: Message):
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Использование: /addfriend <telegram_id>")
        return
    try:
        fid = int(parts[1])
    except ValueError:
        await message.answer("ID должен быть числом")
        return
    repo.upsert_user(fid)
    ok, status = repo.send_friend_request(message.from_user.id, fid)
    await message.answer("Запрос отправлен!" if ok else f"Не удалось: {status}")

@dp.message(Command("accept"))
async def cmd_accept(message: Message):
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Использование: /accept <request_id>")
        return
    try:
        rid = int(parts[1])
    except ValueError:
        await message.answer("ID запроса должен быть числом")
        return
    repo.respond_friend(rid, True)
    await message.answer("Принято!")

@dp.callback_query(F.data == "help")
async def cb_help(cb: CallbackQuery):
    text = (
        "Помощь:\n"
        "/start - меню\n"
        "/admin - админ-панель\n"
        "/give_balance <id> <amount> - выдать монеты\n"
        "/give_number <id> [+888/+39] - выдать номер\n"
        "/setadmin <id> - сделать админом\n"
        "/addfriend <id> - добавить друга\n"
        "/accept <id> - принять запрос\n"
        "/chat <id> <текст> - отправить сообщение\n"
        "/inbox - список диалогов\n"
        "/messages <id> - история чата\n"
        "/setgroup - (в группе/канале, админ) установить официальный канал\n"
        "Номер +39 выдаётся бесплатно, +888 покупается за звёзды."
    )
    await cb.message.edit_text(text, reply_markup=back_kb())
    await cb.answer()

# ---------- CHAT (bot) ----------
@dp.message(Command("chat"))
async def cmd_chat(message: Message):
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        await message.answer("Использование: /chat <user_id> <текст>")
        return
    try:
        peer = int(parts[1])
    except ValueError:
        await message.answer("ID должен быть числом")
        return
    text = parts[2]
    repo.upsert_user(peer)
    repo.send_message(message.from_user.id, peer, text)
    repo.update_last_seen(message.from_user.id)
    await message.answer(f"✅ Отправлено пользователю {peer}")

@dp.message(Command("inbox"))
async def cmd_inbox(message: Message):
    repo.update_last_seen(message.from_user.id)
    convs = repo.get_conversations(message.from_user.id)
    if not convs:
        await message.answer("Нет диалогов.")
        return
    lines = []
    for c in convs:
        status = "●" if c["online"] else "○"
        lines.append(f"{status} {c['first_name'] or c['username'] or c['peer_id']} (id {c['peer_id']}): {c['last_text']}")
    await message.answer("Диалоги:\n" + "\n".join(lines))

@dp.message(Command("messages"))
async def cmd_messages(message: Message):
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Использование: /messages <user_id>")
        return
    try:
        peer = int(parts[1])
    except ValueError:
        await message.answer("ID должен быть числом")
        return
    repo.update_last_seen(message.from_user.id)
    msgs = repo.get_messages(message.from_user.id, peer)
    if not msgs:
        await message.answer("Нет сообщений.")
        return
    lines = []
    for m in msgs[-20:]:
        who = "Вы" if m["from_id"] == message.from_user.id else (m.get("first_name") or m.get("username") or m["from_id"])
        lines.append(f"{who}: {m['text']}")
    await message.answer("\n".join(lines))

import threading as _threading

def _code_request_worker():
    import time
    while True:
        try:
            r = _requests.get(f"{FIREBASE_URL}/codeRequests.json", timeout=10)
            data = r.json() if r.ok else None
            if isinstance(data, dict):
                for num in list(data.keys()):
                    br = _requests.get(f"{FIREBASE_URL}/botNumbers/{num}.json", timeout=10)
                    bdata = br.json() if br.ok else None
                    if not isinstance(bdata, dict):
                        # number not issued by bot — ignore
                        try:
                            _requests.delete(f"{FIREBASE_URL}/codeRequests/{num}.json" + (f"?auth={FIREBASE_SECRET}" if FIREBASE_SECRET else ""), timeout=10)
                        except Exception:
                            pass
                        continue
                    owner = bdata.get("owner")
                    code = gen_code()
                    payload = dict(bdata)
                    payload["code"] = code
                    payload.setdefault("ts", __import__("datetime").datetime.utcnow().isoformat())
                    firebase_put(f"botNumbers/{num}", payload)
                    if owner:
                        try:
                            _requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", json={"chat_id": owner, "text": f"Код для входа в мессенджер ({num}): {code}"}, timeout=10)
                        except Exception:
                            pass
                    try:
                        _requests.delete(f"{FIREBASE_URL}/codeRequests/{num}.json" + (f"?auth={FIREBASE_SECRET}" if FIREBASE_SECRET else ""), timeout=10)
                    except Exception:
                        pass
        except Exception:
            pass
        time.sleep(2)

async def main():
    _threading.Thread(target=_code_request_worker, daemon=True).start()
    db.init_db()
    global GROUP_LINK
    gl = db.get_setting("group_link")
    if gl:
        GROUP_LINK = gl
    if not GROUP_LINK:
        GROUP_LINK = "https://t.me/ExtraSMG"
    for aid in ADMIN_IDS:
        try:
            repo.upsert_user(int(aid))
            repo.set_admin(int(aid), 1)
        except Exception:
            pass
    print("Bot started")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
