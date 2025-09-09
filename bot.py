import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto, ReplyKeyboardMarkup, \
    KeyboardButton, ReplyKeyboardRemove
from datetime import datetime, timedelta
from telebot import TeleBot, types
from PIL import Image
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import os
import pytesseract
import io
import threading
import time as time_module
import json
import pickle

Image.MAX_IMAGE_PIXELS = None
TOKEN = '8481637092:AAGCiPigSex59wCj76Y_OavkjwH398riVeA'
ADMIN_IDS = [765569580, 62365950]
GROUP_CHAT_ID = -1002700176212  # Замените на правильный ID группы
CHAT_LINK = "https://t.me/+E3ry20qfkBgxOWEy"
CURATOR_LINK = "https://t.me/yourcurator"
MEDIA_PATH = "/root/TG-Bot/assets/"

bot = telebot.TeleBot(TOKEN)

# --- Словари для хранения данных ---
user_data = {}
user_states = {}
user_join_dates = {}
user_progress = {}
user_bonus_selected = {}
user_recipe_schedule = {}
photo_submitters = {}
baking_offer_timers = {}
plov_timers = {}
photo_push_timers = {}
course_offer_timers = {}
plov_offer_timers = {}

# --- Сеты для состояний ---
marathon_started_users = set()
stopped_users = set()

# --- Сеты для офферов/действий ---
baking_offer_sent_users = set()
course_offer_sent_users = set()
plov_offer_sent_users = set()
after_plov_scheduled = set()
after_plov_push_14_sent = set()
after_plov_push_18_sent = set()
after_plov_push_20_sent = set()
photo_push_sent_users = set()

# --- Сеты для готовности блюд ---
dish_done_users = set()
lagman_done_users = set()
samsa_done_users = set()
plov_done_users = set()
first_recipe_received_users = set()

# --- Сеты для покупок ---
purchased_users = set()

# Подключение к Google Sheets
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("service_account.json", scope)
client = gspread.authorize(creds)

# Открываем таблицу
sheet = client.open_by_key("1_w25el26-ivrOG4vLdTpkO55HWgvtf4okrJBIy4w3T4").worksheet("Лист1")

def save_participant(name, phone, bot_name, amount):
    """Сохраняет данные об участнике в Google Таблицу"""
    date = datetime.now().strftime("%d.%m.%Y %H:%M")
    month = datetime.now().strftime("%Y-%m")  # для сортировки по месяцам

    row = [name, phone, date, bot_name, amount, month]
    sheet.append_row(row, value_input_option="USER_ENTERED")
    print(f"✅ Добавлен участник: {row}")



def start_marathon_flow(user_id: int, username: str = None):
    """Единый сценарий запуска марафона для кнопок/текста."""
    # Проверяем доступ
    if not check_access(user_id):
        try:
            bot.send_message(user_id, "⏰ Время марафона истекло!")
        except Exception:
            pass
        return

    if user_id in marathon_started_users:
        try:
            bot.send_message(user_id, "Ты уже начала марафон 🎉")
        except Exception:
            pass
        return

    marathon_started_users.add(user_id)

    send_ingredients(user_id)
    send_recipe_buttons(user_id)
    safe_notify_admins(f"👋 Пользователь @{username or user_id} начал марафон!")
    schedule_day_pushes(user_id)


def send_gift_by_count(user_id: int, count: int) -> bool:
    """Отправляет подарок (2 или 4 фото) в ЛС. Возвращает True при успехе."""
    try:
        if count == 2:
            print(f"🎁 Отправляем сборник салатов пользователю {user_id}")
            with open(MEDIA_PATH + "Сборник салатов.pdf", "rb") as doc:
                bot.send_message(user_id,
                                 "🎉 Поздравляем! Ты получила сборник салатов! 🥗",
                                 parse_mode="Markdown")
                bot.send_document(user_id, doc)
            print(f"✅ Сборник салатов успешно отправлен пользователю {user_id}")
            return True
        elif count == 4:
            print(f"🎁 Отправляем сборник ужинов пользователю {user_id}")
            with open(MEDIA_PATH + "Сборник ужинов.pdf", "rb") as doc:
                bot.send_message(user_id,
                                 "🎊 Поздравляем! Ты получила сборник ужинов! 🍽️",
                                 parse_mode="Markdown")
                bot.send_document(user_id, doc)
            print(f"✅ Сборник ужинов успешно отправлен пользователю {user_id}")
            return True
        return False
    except Exception as e:
        print(f"❌ Ошибка при отправке подарка пользователю {user_id}: {e}")
        return False


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def is_stopped(user_id: int) -> bool:
    return user_id in stopped_users or user_states.get(user_id) == "PAID" or user_id in purchased_users


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def safe_send_group(text: str):
    try:
        bot.send_message(GROUP_CHAT_ID, text)
    except Exception as e:
        pass  # Убрано отладочное сообщение


def safe_notify_admins(text: str):
    """Отправляет служебное уведомление всем администраторам в личку."""
    for admin_id in ADMIN_IDS:
        try:
            bot.send_message(admin_id, text)
        except Exception:
            pass


def _get_username_display(user_id: int) -> str:
    """Возвращает удобное имя пользователя для уведомлений админам."""
    try:
        member = bot.get_chat_member(GROUP_CHAT_ID, user_id)
        u = member.user
        if getattr(u, 'username', None):
            return f"@{u.username}"
        if getattr(u, 'first_name', None) or getattr(u, 'last_name', None):
            return f"{u.first_name or ''} {u.last_name or ''}".strip()
    except Exception:
        pass
    # Последняя попытка — прямой get_chat
    try:
        u = bot.get_chat(user_id)
        if getattr(u, 'username', None):
            return f"@{u.username}"
        if getattr(u, 'first_name', None) or getattr(u, 'last_name', None):
            return f"{u.first_name or ''} {u.last_name or ''}".strip()
    except Exception:
        pass
    return f"ID{user_id}"


@bot.message_handler(commands=['start'])
def start(message):
    # Проверяем, что команда отправлена в личном чате
    if message.chat.type != 'private':
        bot.reply_to(message, "❌ Команда /start работает только в личных сообщениях с ботом")
        return

    user_id = message.from_user.id

    # Проверяем доступ для существующих пользователей
    if user_id in user_join_dates:
        if not check_access(user_id):
            return  # Доступ истек, пользователь удален

    # 1️⃣ Отправляем видеокружочек
    try:
        with open(MEDIA_PATH + 'welcome video.mp4', 'rb') as video:
            bot.send_video_note(message.chat.id, video)
        pass  # Убрано отладочное сообщение
    except Exception as e:
        pass  # Убрано отладочное сообщение

    # 2️⃣ Приветственное сообщение
    welcome_text = (
        "Сания: добро пожаловать в наш *4-х дневный марафон по восточной кухне* 👩🏻‍🍳\n\n"
        "Каждый день в 11:00 тебе будет приходить новый рецепт ❤️\n\n"
        "*📌 В программе:*\n\n"
        "День 1: Лазджи сяй (курица с овощами и специями в восточном стиле).\n"
        "День 2: Гуйру лагман (гуйру цомян).\n"
        "День 3: Слоеная самса.\n"
        "День 4: Шах-плов — праздничный плов в тесте\n\n"
        "*‼️ Доступ к марафона ровно 14 дней*\n\n"
        "Как только будешь готова начать марафон, нажми кнопку внизу 👇"
    )
    # Inline кнопки (без нижней клавиатуры)
    inline_kb = InlineKeyboardMarkup()
    inline_kb.add(InlineKeyboardButton("🍽 Начать 4-дневный марафон", callback_data="start_marathon"))

    with open(MEDIA_PATH + 'marathon_program.PNG', 'rb') as photo:
        bot.send_photo(message.chat.id, photo, caption=welcome_text, parse_mode='Markdown', reply_markup=inline_kb)
    user_join_dates[user_id] = datetime.now()

    # Планируем удаление через 14 дней (это не зависит от начала марафона)
    threading.Timer(14 * 24 * 3600, remove_from_group, args=[user_id]).start()

    # Планируем напоминания (они будут проверять статус в момент отправки)
    threading.Timer(24 * 3600, remind_start, args=[user_id]).start()
    threading.Timer(48 * 3600, remind_second_day, args=[user_id]).start()





@bot.message_handler(commands=['status'])
def admin_status(message):
    """Команда для администратора - показывает статус пользователей"""
    # Проверяем, что команда отправлена в личном чате
    if message.chat.type != 'private':
        bot.reply_to(message, "❌ Административные команды работают только в личных сообщениях с ботом")
        return

    if not is_admin(message.from_user.id):
        return

    now = datetime.now()
    total_users = len(user_join_dates)
    active_users = 0
    expired_users = 0

    # Подсчитываем статистику по блюдам
    users_with_2_dishes = 0
    users_with_4_dishes = 0

    for user_id, count in photo_submitters.items():
        if count >= 2:
            users_with_2_dishes += 1
        if count >= 4:
            users_with_4_dishes += 1

    for user_id, join_date in user_join_dates.items():
        days_passed = (now - join_date).days
        if days_passed < 14:
            active_users += 1
        else:
            expired_users += 1

    status_text = (
        f"📊 *Статус марафона:*\n\n"
        f"👥 Всего участников: {total_users}\n"
        f"✅ Активных (до 14 дней): {active_users}\n"
        f"⏰ Истекших (14+ дней): {expired_users}\n"
        f"🍽 Начали марафон: {len(marathon_started_users)}\n"
        f"📖 Получили рецепты: {len(first_recipe_received_users)}\n"
        f"📸 Отправили фото: {len(photo_submitters)}\n\n"
        f"🎁 *Статистика подарков:*\n"
        f"🥗 Получили сборник салатов (2 блюда): {users_with_2_dishes}\n"
        f"🍽 Получили сборник ужинов (4 блюда): {users_with_4_dishes}\n\n"
        f"🕐 Текущее время: {now.strftime('%d.%m.%Y %H:%M')}"
    )

    bot.reply_to(message, status_text, parse_mode="Markdown")


@bot.message_handler(commands=['remove'])
def admin_remove_user(message):
    """Команда для администратора - удаляет пользователя по ID"""
    # Проверяем, что команда отправлена в личном чате
    if message.chat.type != 'private':
        bot.reply_to(message, "❌ Административные команды работают только в личных сообщениях с ботом")
        return

    if not is_admin(message.from_user.id):
        return

    try:
        # Парсим команду: /remove 123456789
        parts = message.text.split()
        if len(parts) != 2:
            bot.reply_to(message, "❌ Использование: /remove <user_id>")
            return

        user_id = int(parts[1])
        if user_id in user_join_dates:
            remove_from_group(user_id)
            bot.reply_to(message, f"✅ Пользователь {user_id} удален из марафона")
        else:
            bot.reply_to(message, f"❌ Пользователь {user_id} не найден")

    except ValueError:
        bot.reply_to(message, "❌ Неверный ID пользователя")
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")


@bot.message_handler(commands=['user'])
def admin_user_info(message):
    """Команда для администратора - показывает информацию о конкретном пользователе"""
    # Проверяем, что команда отправлена в личном чате
    if message.chat.type != 'private':
        bot.reply_to(message, "❌ Административные команды работают только в личных сообщениях с ботом")
        return

    if not is_admin(message.from_user.id):
        return

    try:
        # Парсим команду: /user 123456789
        parts = message.text.split()
        if len(parts) != 2:
            bot.reply_to(message, "❌ Использование: /user <user_id>")
            return

        user_id = int(parts[1])
        if user_id not in user_join_dates:
            bot.reply_to(message, f"❌ Пользователь {user_id} не найден")
            return

        join_date = user_join_dates[user_id]
        days_passed = (datetime.now() - join_date).days
        photos_count = photo_submitters.get(user_id, 0)
        marathon_started = user_id in marathon_started_users
        first_recipe = user_id in first_recipe_received_users

        # Определяем статус подарков
        gift_status = "❌ Нет подарков"
        if photos_count >= 4:
            gift_status = "🎁 Сборник ужинов (4 блюда)"
        elif photos_count >= 2:
            gift_status = "🥗 Сборник салатов (2 блюда)"

        user_info = (
            f"👤 *Информация о пользователе {user_id}:*\n\n"
            f"📅 Дата регистрации: {join_date.strftime('%d.%m.%Y %H:%M')}\n"
            f"⏰ Дней в марафоне: {days_passed}\n"
            f"🍽 Начал марафон: {'✅' if marathon_started else '❌'}\n"
            f"📖 Получил первый рецепт: {'✅' if first_recipe else '❌'}\n"
            f"📸 Отправлено фото: {photos_count}\n"
            f"🎁 Статус подарков: {gift_status}\n\n"
            f"⏳ Доступ истекает через: {14 - days_passed} дней"
        )

        bot.reply_to(message, user_info, parse_mode="Markdown")

    except ValueError:
        bot.reply_to(message, "❌ Неверный ID пользователя")
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")


@bot.message_handler(commands=['photos'])
def admin_photos_info(message):
    """Команда для администратора - показывает всех пользователей, отправивших фото"""
    # Проверяем, что команда отправлена в личном чате
    if message.chat.type != 'private':
        bot.reply_to(message, "❌ Административные команды работают только в личных сообщениях с ботом")
        return

    if not is_admin(message.from_user.id):
        return

    if not photo_submitters:
        bot.reply_to(message, "📸 Пока никто не отправил фото")
        return

    # Сортируем по количеству фото
    sorted_users = sorted(photo_submitters.items(), key=lambda x: x[1], reverse=True)

    photos_info = "📸 *Пользователи, отправившие фото:*\n\n"

    for user_id, count in sorted_users:
        username = "Неизвестно"
        try:
            user_info = bot.get_chat_member(GROUP_CHAT_ID, user_id)
            if user_info.user.username:
                username = f"@{user_info.user.username}"
            else:
                username = f"{user_info.user.first_name or 'Пользователь'}"
        except:
            username = f"ID{user_id}"

        gift_status = ""
        if count >= 4:
            gift_status = " 🎁 (4 блюда - сборник ужинов)"
        elif count >= 2:
            gift_status = " 🥗 (2 блюда - сборник салатов)"

        photos_info += f"👤 {username}: {count} фото{gift_status}\n"

    bot.reply_to(message, photos_info, parse_mode="Markdown")


@bot.message_handler(commands=['send_gift'])
def admin_send_gift(message):
    """Команда для администратора - принудительно отправляет подарок пользователю"""
    # Проверяем, что команда отправлена в личном чате
    if message.chat.type != 'private':
        bot.reply_to(message, "❌ Административные команды работают только в личных сообщениях с ботом")
        return

    if not is_admin(message.from_user.id):
        return

    try:
        # Парсим команду: /send_gift 123456789 2 или /send_gift 123456789 4
        parts = message.text.split()
        if len(parts) != 3:
            bot.reply_to(message, "❌ Использование: /send_gift <user_id> <2|4>")
            return

        user_id = int(parts[1])
        gift_type = int(parts[2])

        if gift_type not in [2, 4]:
            bot.reply_to(message, "❌ Тип подарка должен быть 2 или 4")
            return

        if user_id not in user_join_dates:
            bot.reply_to(message, f"❌ Пользователь {user_id} не найден")
            return

        username = "Неизвестно"
        try:
            user_info = bot.get_chat_member(GROUP_CHAT_ID, user_id)
            if user_info.user.username:
                username = f"@{user_info.user.username}"
            else:
                username = f"{user_info.user.first_name or 'Пользователь'}"
        except:
            username = f"ID{user_id}"

        try:
            if gift_type == 2:
                # Отправляем сборник салатов
                with open(MEDIA_PATH + "Сборник салатов.pdf", "rb") as doc:
                    bot.send_message(user_id,
                                     "🎉 *Поздравляем! Ты получаешь сборник салатов!* 🎉\n\n"
                                     "Ты получаешь *письменный сборник салатов* — 25 пошаговых рецептов! 🥗\n\n"
                                     "Продолжай готовить с удовольствием и радовать своих родных! ❤️",
                                     parse_mode="Markdown")
                    bot.send_document(user_id, doc)

                # Поздравление в общем чате
                safe_send_group(
                    f"🎉 *Поздравляем {username}!* 🎉\n\n"
                    f"Она получила *крутой сборник салатов*, чтобы радовать своих родных! 🥗✨\n\n"
                    f"Так держать! Продолжай готовить с удовравольствием! 👩‍🍳"
                )

                bot.reply_to(message, f"✅ Сборник салатов отправлен пользователю {user_id}")

            elif gift_type == 4:
                # Отправляем сборник ужинов
                with open(MEDIA_PATH + "Сборник ужинов.pdf", "rb") as doc:
                    bot.send_message(user_id,
                                     "🎊 *Поздравляем! Ты получаешь сборник ужинов!* 🎊\n\n"
                                     "Ты получаешь *письменный сборник 10 ужинов для семьи и гостей*! 🍽️\n\n"
                                     "Теперь ты можешь накрывать шикарный стол и удивлять всех своими кулинарными талантами! 🌟",
                                     parse_mode="Markdown")
                    bot.send_document(user_id, doc)

                # Поздравление в общем чате
                safe_send_group(
                    f"🔥 *Поздравляем {username}!* 🔥\n\n"
                    f"Она получила *сборник 10 ужинов для семьи и гостей*! 🍽️✨\n\n"
                    f"Ты настоящая восточная хозяйка! Продолжай радовать близких! 👑"
                )

                bot.reply_to(message, f"✅ Сборник ужинов отправлен пользователю {user_id}")

        except Exception as e:
            bot.reply_to(message, f"❌ Ошибка при отправке подарка: {e}")

    except ValueError:
        bot.reply_to(message, "❌ Неверный ID пользователя или тип подарка")
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")


@bot.callback_query_handler(func=lambda call: call.data in ["start_marathon", "get_first_recipe", "dish_done"])
def callback_query(call):
    user_id = call.from_user.id

    # Проверяем доступ
    if not check_access(user_id):
        bot.answer_callback_query(call.id, text="⏰ Время марафона истекло!", show_alert=True)
        return

    if call.data == "start_marathon":
        bot.answer_callback_query(call.id)
        start_marathon_flow(user_id, username=call.from_user.username)

    elif call.data == "get_first_recipe":
        bot.answer_callback_query(call.id)

        if user_id in first_recipe_received_users:
            return  # Уже получил рецепт

        first_recipe_received_users.add(user_id)
        send_first_recipe(user_id)

        # --- Лагман в 11:00 следующего дня, только если ещё не в расписании ---
        if user_id not in user_recipe_schedule or user_recipe_schedule[user_id].get("next_recipe") != "lagman":
            next_lagman_time = (datetime.now() + timedelta(days=1)).replace(hour=11, minute=0, second=0, microsecond=0)
            delay_lagman = (next_lagman_time - datetime.now()).total_seconds()

            threading.Timer(delay_lagman, send_lagman_recipe, args=[user_id]).start()

            user_recipe_schedule[user_id] = {
                "next_recipe": "lagman",
                "next_recipe_time": next_lagman_time
            }

            print(f"📅 Лагман добавлен в расписание для пользователя {user_id} на {next_lagman_time.strftime('%d.%m.%Y %H:%M')}")
        else:
            print(f"⚠️ Лагман уже запланирован для {user_id}, повторно не добавляем")

    elif call.data == "dish_done":
        bot.answer_callback_query(call.id)

        if user_id in dish_done_users:
            return

        dish_done_users.add(user_id)

        # Убираем кнопку и пишем "✅ Блюдо готово"
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="✅ Блюдо готово"
        )

        message = (
            "🎉 <b>Ух ты, ты уже приготовила первое блюдо марафона! Я тебя поздравляю, очень круто!</b>\n\n"
            "Поделись своими впечатлениями, как тебе? 💬\n\n"
            f"💌 Вот ссылка на наш чат: <a href=\"{CHAT_LINK}\">Перейти в чат</a>\n\n"
            "🎁 <b>Ты автоматически участвуешь в конкурсе!</b>\n"
            "Готовь блюда, отправляй фото в чат, по желанию публикуй в Instagram с отметкой @saniya_iminova.\n"
            "<b>Больше готовых блюд — больше подарков!</b>"
        )

        bot.send_message(user_id, message, parse_mode="HTML", disable_web_page_preview=True)


@bot.callback_query_handler(func=lambda call: call.data == "choose_recipe")
def choose_recipe_handler(call):
    user_id = call.from_user.id

    # Проверяем доступ
    if not check_access(user_id):
        bot.answer_callback_query(call.id, text="⏰ Время марафона истекло!", show_alert=True)
        return

    bot.answer_callback_query(call.id)

    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("🥢 Лагман", callback_data="recipe_lagman"),
        InlineKeyboardButton("🥟 Самса", callback_data="recipe_samsa"),
        InlineKeyboardButton("🍚 Плов", callback_data="recipe_plov")
    )
    bot.send_message(user_id, "Выбери рецепт, к которому хочешь вернуться:", reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith("recipe_"))
def send_selected_recipe(call):
    bot.answer_callback_query(call.id)
    user_id = call.from_user.id

    # Проверяем доступ
    if not check_access(user_id):
        return
    recipe = call.data.split("_")[1]

    if recipe == "lagman":
        # При возврате кружок не отправляем
        send_lagman_recipe(user_id, send_video=False)
    elif recipe == "samsa":
        send_samsa_recipe(user_id)
    elif recipe == "plov":
        send_final_recipe(user_id)


def send_ingredients(user_id):
    if is_stopped(user_id):
        return
    bot.send_message(user_id, "🚂 Вот список продуктов, которые понадобятся:")
    try:
        with open(MEDIA_PATH + 'sauce.jpg', 'rb') as photo1, open(MEDIA_PATH + 'vinegar.jpg', 'rb') as photo2:
            bot.send_media_group(user_id, [
                telebot.types.InputMediaPhoto(photo1),
                telebot.types.InputMediaPhoto(photo2)
            ])

        text = (
            "Соевый соус и китайский уксус можно приобрести в крупных маркетах, таких как Magnum, Small, Toimart.\n"
            "Также их можно найти на продуктовых базарах и в магазине у дома.\n"
            "Если не найдете китайский уксус, замените его на яблочный или обычный 6%.\n"
            "Соевый соус можете использовать любой."
        )
        bot.send_message(user_id, text)

        with open(MEDIA_PATH + 'Список_Продуктов.pdf', 'rb') as file:
            bot.send_document(user_id, file)

    except:
        pass  # Убрано отладочное сообщение


def send_recipe_buttons(user_id):
    if is_stopped(user_id):
        return
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("📖 Получить первый рецепт", callback_data="get_first_recipe"),
        InlineKeyboardButton("💬 Задать вопрос куратору", url=CHAT_LINK)
    )
    bot.send_message(
        user_id,
        "Как только будешь готова получить свой первый рецепт, нажимай кнопку ниже ⬇️\n\n"
        "А также обязательно присоединяйся к нашему чату в тг, чтобы быть с теми, кто тоже готовит❤️",
        reply_markup=markup
    )


def send_first_recipe(user_id):
    if is_stopped(user_id):
        return
    bot.send_message(
        user_id,
        "🍽 *ПЕРВОЕ БЛЮДО В РАМКАХ ВОСТОЧНОГО МАРАФОНА*",
        parse_mode="Markdown"
    )

    with open(MEDIA_PATH + 'Лазджи сяй.jpg', 'rb') as photo:
        caption = (
            "🍗 *Лазджи Сяй* — курица в восточном стиле с овощами и специями.\n"
            "Пикантное, сытное, очень легкое в приготовлении блюдо.\n\n"
            "🥗 Его можно подавать как горячий/холодный салат или как основное блюдо. "
            "На гарнир идеально подходит рис и пюре.\n\n"
            "🎥 *Длительность урока:* 2 минуты\n\n"
            "👨‍🍳 *Рекомендации от повара:*\n"
            "1. Для приготовления Лазджи Сяя используйте именно филе курицы — так вкус получается более нежным, а блюдо готовится быстро.\n"
            "2. Внимательно изучите видеоурок.\n"
            "3. Подготовьте все ингредиенты — нарежьте по тарелочкам и начинайте готовить с прекрасным настроением 😉"
        )
        bot.send_photo(user_id, photo, caption=caption, parse_mode="Markdown")

    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("✅ Блюдо готово", callback_data="dish_done"),
        InlineKeyboardButton("💬 Есть вопрос", url=CHAT_LINK)
    )

    try:
        bot.send_message(
            user_id,
            '<a href="https://www.youtube.com/watch?v=5yAqlp2KN7U">▶ Лазджи Сяй</a>',
            parse_mode="HTML",
            disable_web_page_preview=False  # Если хочешь, чтобы было превью видео
        )
    except Exception as e:
        bot.send_message(user_id, f"⚠️ Ссылка не отправлена: {e}")

    try:
        with open(MEDIA_PATH + 'Рецепт Лазджи сяй.pdf', 'rb') as doc:
            bot.send_document(user_id, doc)
    except Exception as e:
        bot.send_message(user_id, f"⚠️ Не удалось отправить рецепт: {e}")

    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("✅ Блюдо готово", callback_data="dish_done"),
        InlineKeyboardButton("💬 Есть вопрос", url=CHAT_LINK)
    )
    bot.send_message(user_id, "Когда приготовишь — нажми кнопку!", reply_markup=markup)

    # Запланировать отправку бонусных рецептов через 5 часов
    threading.Timer(5 * 3600, send_bonus_recipes_offer, args=[user_id]).start()


def send_bonus_recipes_offer(user_id):
    # Проверяем, не выбирал ли уже пользователь бонусный рецепт
    if is_stopped(user_id):
        return
    if user_id in user_bonus_selected:
        return

    with open(MEDIA_PATH + 'бонус.png', 'rb') as photo:
        caption = (
            "🎁 В честь первого участия — подарок! Выбери рецепт:\n\n"
            "— *Пияз нан* (луковый хлеб)\n"
            "— *Манпар* (сытный суп)\n"
            "— *Тухум сяй* (яйца с джусаем)\n"
            "— *Лазджан* (острая приправа)\n\n"
            "Каждое блюдо дополнит восточный обед!"
        )

        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton("🥯 Пияз нан", callback_data="bonus_piyaz_nan"),
            InlineKeyboardButton("🍲 Манпар", callback_data="bonus_manpar")
        )
        markup.add(
            InlineKeyboardButton("🍳 Тухум сяй", callback_data="bonus_tuhum_syay"),
            InlineKeyboardButton("🌶 Лазджан", callback_data="bonus_lazjan")
        )

        bot.send_photo(user_id, photo, caption=caption, parse_mode="Markdown", reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith("bonus_"))
def handle_bonus_recipe(call):
    user_id = call.from_user.id

    # Проверяем доступ
    if not check_access(user_id):
        bot.answer_callback_query(call.id, text="⏰ Время марафона истекло!", show_alert=True)
        return

    # Проверяем, не выбирал ли уже пользователь бонусный рецепт
    if user_id in user_bonus_selected:
        bot.answer_callback_query(call.id, text="Вы уже выбрали подарок.")
        return

    # Сопоставляем callback_data с названиями рецептов и путями к файлам
    recipe_map = {
        "bonus_piyaz_nan": ("Пияз нан", MEDIA_PATH + "Пияз_нан.pdf"),
        "bonus_manpar": ("Манпар", MEDIA_PATH + "Манпар.pdf"),
        "bonus_tuhum_syay": ("Тухум сяй", MEDIA_PATH + "Тухум_сай.pdf"),
        "bonus_lazjan": ("Лазджан", MEDIA_PATH + "Лазджан.pdf"),
    }

    recipe_name, file_path = recipe_map.get(call.data, (None, None))

    if recipe_name and file_path:
        # Сохраняем информацию о выбранном рецепте
        user_bonus_selected[user_id] = recipe_name

        try:
            # Удаляем кнопки после выбора
            bot.edit_message_reply_markup(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=None
            )
        except:
            pass

        try:
            # Отправляем выбранный рецепт
            with open(file_path, 'rb') as file:
                bot.send_message(user_id, f"✅ Отличный выбор! Вот рецепт: *{recipe_name}*", parse_mode="Markdown")
                bot.send_document(user_id, file)
        except Exception as e:
            bot.send_message(user_id, f"⚠️ Не удалось отправить файл. Свяжись с куратором. Ошибка: {str(e)}")
    else:
        bot.answer_callback_query(call.id, text="⚠️ Рецепт не найден.")


def send_lagman_recipe(user_id, send_video=True):
    if is_stopped(user_id):
        return
    try:
        if send_video:
            with open(MEDIA_PATH + '2 день.mp4', 'rb') as video:
                bot.send_video_note(user_id, video)

        with open(MEDIA_PATH + 'лагман.JPG', 'rb') as photo:
            caption = (
                "Доброе утро!\n\n"
                "Сегодня в меню у нас — *Лагман* ✨\n\n"
                "Пожалуйста, внимательно ознакомься со всеми файлами и видео перед началом процесса готовки. "
                "И настройся на отличный результат, потому что это половина успеха ❤️"
            )
            bot.send_photo(user_id, photo, caption=caption, parse_mode="Markdown")

        # Документы
        with open(MEDIA_PATH + 'Лагман - урок про тесто.pdf', 'rb') as file1, \
             open(MEDIA_PATH + 'Тесто для лагмана.pdf', 'rb') as file2, \
             open(MEDIA_PATH + 'Гуйру лагман.pdf', 'rb') as file3, \
             open(MEDIA_PATH + 'Гуйру цомян.pdf', 'rb') as file4:
            bot.send_document(user_id, file1)
            bot.send_document(user_id, file2)
            bot.send_document(user_id, file3)
            bot.send_document(user_id, file4)

        # Видео-текст
        video_text = (
            "<b>ЛАПША ДЛЯ ЛАГМАНА</b>\n\n"
            "На этом уроке ты на практике закрепишь то, что узнала из теоретического урока «Про тесто».\n\n"
            "Мы рекомендуем несколько раз просмотреть видео, прежде чем начинать готовить.\n\n"
            "Выдели 40–60 минут свободного времени, чтобы в спокойной обстановке всё приготовить. "
            "Включай приятную музыку и поехали😉\n\n"
            "🎥 <a href='https://www.youtube.com/watch?v=ckIX5NDnrKY'>Лапша для лагмана </a>"
        )
        bot.send_message(user_id, video_text, parse_mode="HTML")

        # Рекомендации
        message_text = (
            "Мы рекомендуем:\n"
            "• Внимательно просмотреть видео-урок.\n"
            "• Подготовить все ингредиенты.\n"
            "• Нарезать всё заранее.\n"
            "• Начинать готовить.\n\n"
            "Успехов и ждём твоё готовое блюдо ❤️\n"
            "🎥 <a href='https://www.youtube.com/watch?v=MP7q9R7beDg'>Гуйру Лагман </a>"
        )

        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton("✅ Блюдо готово", callback_data="lagman_done"),
            InlineKeyboardButton("💬 Есть вопрос", url=CHAT_LINK)
        )
        bot.send_message(user_id, message_text, parse_mode="HTML", reply_markup=markup)

        # 📸 Фото-пуш (15:00, только один раз)
        if user_id not in photo_push_sent_users and user_id not in photo_push_timers:
            next_time = datetime.now().replace(hour=15, minute=0, second=0, microsecond=0)
            if datetime.now() >= next_time:
                next_time = (datetime.now() + timedelta(days=1)).replace(
                    hour=15, minute=0, second=0, microsecond=0
                )

            delay = (next_time - datetime.now()).total_seconds()
            timer = threading.Timer(delay, send_lagman_photos_push, args=[user_id])
            timer.start()
            photo_push_timers[user_id] = timer
            print(f"📸 Фото-пуш запланирован для {user_id} на {next_time.strftime('%d.%m.%Y %H:%M')}")

        # 🎁 Курс-оффер (20:00, только один раз)
        if user_id not in course_offer_sent_users and user_id not in course_offer_timers:
            next_offer_time = datetime.now().replace(hour=20, minute=0, second=0, microsecond=0)
            if datetime.now() >= next_offer_time:
                next_offer_time = (datetime.now() + timedelta(days=1)).replace(
                    hour=20, minute=0, second=0, microsecond=0
                )

            delay = (next_offer_time - datetime.now()).total_seconds()
            timer = threading.Timer(delay, send_course_offer, args=[user_id])
            timer.start()
            course_offer_timers[user_id] = timer
            print(f"🎁 Курс-оффер запланирован для {user_id} на {next_offer_time.strftime('%d.%m.%Y %H:%M')}")


        # ✅ Самса (остается как у тебя)
        if user_id not in user_recipe_schedule or user_recipe_schedule[user_id].get("next_recipe") != "samsa":
            next_samsa_time = (datetime.now() + timedelta(days=1)).replace(hour=11, minute=0, second=0, microsecond=0)
            delay_samsa = (next_samsa_time - datetime.now()).total_seconds()
            threading.Timer(delay_samsa, send_samsa_recipe, args=[user_id]).start()
            user_recipe_schedule[user_id] = {"next_recipe": "samsa", "next_recipe_time": next_samsa_time}
            print(f"📅 Самса запланирована для {user_id} на {next_samsa_time.strftime('%d.%m.%Y %H:%M')}")

    except Exception as e:
        print(f"❌ Ошибка при отправке лагмана пользователю {user_id}: {e}")



def send_lagman_photos_push(user_id):
    if is_stopped(user_id):
        return
    try:
        photo_paths = [
            MEDIA_PATH + 'отзыв.jpg',
            MEDIA_PATH + 'отзыв2.jpg',
            MEDIA_PATH + 'отзыв3.jpg',
            MEDIA_PATH + 'отзыв4.jpg',
            MEDIA_PATH + 'отзыв5.jpg',
        ]

        text = (
            "📸 Посмотри, как у других участниц получился лагман!\n"
            "Если ты ещё не начала — скорее приступай!\n\n"
            "Многие готовили лагман впервые и вот какие классные результаты у них получились 💫\n\n"
            "Ты тоже справишься — начни сейчас, чтобы не отставать!"
        )

        media = []
        for i, path in enumerate(photo_paths):
            with open(path, 'rb') as file:
                photo_bytes = io.BytesIO(file.read())
                if i == 0:
                    media.append(types.InputMediaPhoto(photo_bytes, caption=text))
                else:
                    media.append(types.InputMediaPhoto(photo_bytes))

        bot.send_media_group(user_id, media)

        # ✅ отмечаем, что пуш отправлен
        photo_push_sent_users.add(user_id)
        if user_id in photo_push_timers:
            del photo_push_timers[user_id]

    except Exception as e:
        bot.send_message(user_id, f"⚠️ Не удалось отправить фото: {e}")


def send_course_offer(user_id):
    if is_stopped(user_id):
        return

    if user_id in course_offer_sent_users:
        print(f"ℹ️ Оффер курса уже был отправлен пользователю {user_id}")
        return

    try:
        with open(MEDIA_PATH + 'Коллаж.png', 'rb') as photo:
            caption = (
                "Кстати, лагман идеально дополняет эти 4 блюда, и всё это есть в нашем курсе — *Восточная хозяйка* 😍\n\n"
                "Хочешь накрыть шикарный стол и удивить родных? Тогда скорее присоединяйся!\n\n"
                "*104 блюда восточной кухни — всего за 4990₸!*"
            )

            markup = InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("📋 Посмотреть программу", url="https://saniyaiminova.kz/4course"))

            bot.send_photo(user_id, photo, caption=caption, parse_mode="Markdown", reply_markup=markup)

            # ✅ сохраняем состояние
            user_states[user_id] = "AWAITING_RECEIPT"

            # ✅ отмечаем, что оффер отправлен
            course_offer_sent_users.add(user_id)
            if user_id in course_offer_timers:
                del course_offer_timers[user_id]

            print(f"✅ Оффер курса отправлен пользователю {user_id}")

    except Exception:
        pass

@bot.callback_query_handler(func=lambda call: call.data == "lagman_done")
def handle_lagman_done(call):
    user_id = call.from_user.id

    # Проверяем доступ
    if not check_access(user_id):
        bot.answer_callback_query(call.id, text="⏰ Время марафона истекло!", show_alert=True)
        return

    if user_id in lagman_done_users:
        return  # Уже нажимал — ничего не делаем

    lagman_done_users.add(user_id)
    dish_done_users.add(user_id)

    # Убираем кнопку и пишем "✅ Блюдо готово"
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text="✅ Блюдо готово"
    )

    message = (
        "🌟 <b>Отлично! Ты приготовила лагман!</b> 🌟\n\n"
        "Как тебе новый рецепт? Поделись своими впечатлениями! 💬\n\n"
        f"💌 Вот ссылка на наш чат: <a href=\"{CHAT_LINK}\">Перейти в чат</a>\n\n"
        "🎁 <b>Не забывай — ты участвуешь в конкурсе!</b>\n"
        "Отправляй фото готовых блюд в чат и получай подарки:\n"
        "• 2 блюда — сборник салатов 🥗\n"
        "• 4 блюда — сборник ужинов 🍽️"
    )

    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("📸 Поделиться в чате", url=CHAT_LINK))
    bot.send_message(user_id, message, parse_mode="HTML", reply_markup=markup)


def send_samsa_recipe(user_id):
    if is_stopped(user_id):
        return

    try:
        with open(MEDIA_PATH + 'Самса.jpg', 'rb') as photo:
            bot.send_photo(user_id, photo,
                           caption="Доброе утро!\n\nСегодня у нас — *Слоеная самса* ✨",
                           parse_mode="Markdown")

        with open(MEDIA_PATH + 'Рецепт самсы.pdf', 'rb') as doc:
            bot.send_document(user_id, doc)

        text = ("🎥 <a href='https://www.youtube.com/watch?v=_JduX_PoAC4'>Самса</a>")
        bot.send_message(user_id, text, parse_mode="HTML")

        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton("✅ Блюдо готово", callback_data="samsa_done"),
            InlineKeyboardButton("💬 Есть вопрос", url=CHAT_LINK)
        )
        bot.send_message(user_id, "Когда приготовишь — нажми кнопку!", reply_markup=markup)

        # --- Оффер выпечки (20:00, только один раз) ---
        if user_id not in baking_offer_sent_users and user_id not in baking_offer_timers:
            offer_time = datetime.now().replace(hour=20, minute=0, second=0, microsecond=0)
            if datetime.now() >= offer_time:
                offer_time = (datetime.now() + timedelta(days=1)).replace(hour=20, minute=0, second=0, microsecond=0)

            delay_offer = (offer_time - datetime.now()).total_seconds()
            timer = threading.Timer(delay_offer, send_baking_offer, args=[user_id])
            timer.start()
            baking_offer_timers[user_id] = timer
            print(f"⏰ send_baking_offer запланирован на {offer_time.strftime('%d.%m.%Y %H:%M')}")

        # --- Плов (на следующий день 11:00, только если не стоит в расписании) ---
        if user_id not in plov_timers and (user_id not in plov_timers or not plov_timers[user_id].is_alive()):
            plov_time = (datetime.now() + timedelta(days=1)).replace(hour=11, minute=0, second=0, microsecond=0)
            delay_plov = (plov_time - datetime.now()).total_seconds()
            timer = threading.Timer(delay_plov, send_final_recipe, args=[user_id])
            timer.start()
            plov_timers[user_id] = timer
            user_recipe_schedule[user_id] = {"next_recipe": "plov", "next_recipe_time": plov_time}
            print(f"📅 Плов запланирован на {plov_time.strftime('%d.%m.%Y %H:%M')}")
        else:
            print(f"⚠️ Плов уже запланирован для {user_id}, повторно не добавляем")




    except Exception as e:
        print(f"❌ Ошибка при отправке самсы: {e}")


def send_baking_offer(user_id):
    """Отправляет оффер про выпечку после самсы один раз"""
    if is_stopped(user_id):
        return

    if user_id in baking_offer_sent_users:
        print(f"ℹ️ Оффер выпечки уже отправлен пользователю {user_id}")
        return

    try:
        with open(MEDIA_PATH + 'Выпечка.png', 'rb') as photo:
            caption = (
                "Кстати, у нас есть ещё варианты вкусной и быстрой домашней выпечки! 🥐\n\n"
                "Посмотри на этот коллаж из 4 блюд — и все они есть в нашем курсе *Восточная хозяйка* 😍\n\n"
                "Хочешь научиться готовить такую красивую и вкусную выпечку? Тогда скорее присоединяйся!\n\n"
                "*104 блюда восточной кухни — всего за 4990₸!*"
            )
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("📋 Посмотреть программу", url="https://saniyaiminova.kz/4course"))

            bot.send_photo(user_id, photo, caption=caption, parse_mode="Markdown", reply_markup=markup)

            user_states[user_id] = "AWAITING_RECEIPT"
            baking_offer_sent_users.add(user_id)
            print(f"✅ Оффер выпечки отправлен пользователю {user_id}")

    except Exception as e:
        bot.send_message(user_id, f"⚠️ Ошибка при отправке оффера: {e}")


@bot.callback_query_handler(func=lambda call: call.data == "samsa_done")
def handle_samsa_done(call):
    user_id = call.from_user.id

    # Проверяем доступ
    if not check_access(user_id):
        bot.answer_callback_query(call.id, text="⏰ Время марафона истекло!", show_alert=True)
        return

    if user_id in samsa_done_users:
        return  # Уже нажимал — ничего не делаем

    samsa_done_users.add(user_id)

    dish_done_users.add(user_id)
    # Убираем кнопку и пишем "✅ Блюдо готово"
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text="✅ Блюдо готово"
    )

    message = (
        "🌟 <b>Wow! Ты просто космос!</b> 🌟\n\n"
        "Ты уже приготовила <b>восточную самсу!</b> Уверена, твои родные оценили по достоинству твои старания 😊\n"
        "И наверняка ты гордишься собой — ведь так приятно готовить вкусно и радовать близких!\n\n"
        "💬 <b>Поделись, как тебе новый рецепт?</b>\n"
        "(А если поделишься в чате, автоматически участвуешь в конкурсе! 🏆)"
    )

    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("📸 Поделиться в чате", url=CHAT_LINK))
    bot.send_message(user_id, message, parse_mode="HTML", reply_markup=markup)


def send_final_recipe(user_id):
    if is_stopped(user_id):
        return
    try:
        with open(MEDIA_PATH + 'Плов.png', 'rb') as photo:
            caption = (
                "🍽 <b>Сегодня заключительный день марафона!</b>\n\n"
                "Лови последний рецепт — <b>Шах плов</b> ❤️\n\n"
                "Как круто, что ты прошла весь марафон! Ты молодец!"
            )
            bot.send_photo(user_id, photo, caption=caption, parse_mode="HTML")

        text = (
            "✨ <b>Представьте:</b> хрустящее тесто, красочная ароматная начинка из мяса, "
            "рассыпчатого риса, красивой моркови и разнообразие специй!\n\n"
            "Мы предлагаем адаптированный вариант плова — не менее красивый и вкусный! 😍\n"
            "А ещё вас ждут <b>2 варианта теста</b>, с которыми справится любая хозяйка.\n"
            "<i>Удивление и восторг в глазах родных гарантирован!</i> 🥰\n\n"
            "🎥 <a href='https://www.youtube.com/watch?v=3cD5wCf4c4o'>Шах Плов</a>"
        )
        bot.send_message(user_id, text, parse_mode="HTML")

        # PDF с рецептом
        try:
            with open(MEDIA_PATH + 'Шах плов.pdf', 'rb') as file:
                bot.send_document(user_id, file)
        except Exception as e:
            bot.send_message(user_id, f"⚠️ Не удалось отправить рецепт: {e}")

        # Кнопки
        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton("✅ Блюдо готово", callback_data="plov_done"),
            InlineKeyboardButton("💬 Есть вопрос", url=CHAT_LINK)
        )
        bot.send_message(user_id, "Когда приготовишь — нажми кнопку ниже:", reply_markup=markup)

    except Exception as e:
        bot.send_message(user_id, f"⚠️ Ошибка при отправке рецепта плова: {e}")

    # --- Планируем plov_offer в 20:00 (только для тех, кто НЕ купил курс) ---
    if user_id not in purchased_users and user_id not in plov_offer_sent_users and user_id not in plov_offer_timers:
        try:
            next_offer_time = datetime.now().replace(hour=20, minute=0, second=0, microsecond=0)

            # Если уже прошло 20:00 → переносим на следующий день
            if datetime.now() >= next_offer_time:
                next_offer_time = (datetime.now() + timedelta(days=1)).replace(
                    hour=20, minute=0, second=0, microsecond=0
                )

            delay_offer = (next_offer_time - datetime.now()).total_seconds()
            timer = threading.Timer(delay_offer, send_plov_offer, args=[user_id])
            timer.start()

            plov_offer_timers[user_id] = timer  # сохраняем активный таймер

            print(f"⏰ Запланировано: send_plov_offer для пользователя {user_id} на "
                  f"{next_offer_time.strftime('%d.%m.%Y %H:%M')}")

        except Exception as e:
            print(f"⚠️ Ошибка при планировании plov_offer для пользователя {user_id}: {e}")



@bot.callback_query_handler(func=lambda call: call.data == "plov_done")
def handle_plov_done(call):
    user_id = call.from_user.id

    # Проверяем доступ
    if not check_access(user_id):
        bot.answer_callback_query(call.id, text="⏰ Время марафона истекло!", show_alert=True)
        return

    bot.answer_callback_query(call.id)

    if user_id in plov_done_users:
        return  # Уже нажимал — ничего не делаем

    plov_done_users.add(user_id)

    dish_done_users.add(user_id)
    # Убираем кнопку и пишем "✅ Блюдо готово"
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text="✅ Блюдо готово"
    )

    text = (
        "✅ <b>Блюдо готово — ну что, поздравляю!</b>\n\n"
        "Самое праздничное, роскошное и вкусное блюдо готово! 🎉\n"
        "Ты умничка, что с такой лёгкостью проходишь марафон!\n\n"
        "✨ Делись своими впечатлениями в Instagram, отмечай мою страничку и участвуй в розыгрыше призов!\n"
        "И конечно, не забудь написать девочкам в чате, как тебе <b>шах-плов</b> 😍"
    )

    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("📸 Поделиться в чате", url=CHAT_LINK))
    bot.send_message(user_id, text, parse_mode="HTML", reply_markup=markup)

@bot.message_handler(content_types=['photo'])
def handle_group_photo(message):
    """Обрабатывает фото в группе: считает, выдает подарки в ЛС."""
    print(f"📸 Получено фото от {message.from_user.id} в чате {message.chat.id}")
    print(f"📸 Ожидаемый ID группы: {GROUP_CHAT_ID}")

    try:
        if message.chat and message.chat.id != GROUP_CHAT_ID:
            print(f"❌ Фото не в нужной группе: {message.chat.id} != {GROUP_CHAT_ID}")
            return  # реагируем только в групповом чате

        user_id = message.from_user.id
        # Игнорируем ботов
        if message.from_user.is_bot:
            print(f"🤖 Игнорируем бота: {user_id}")
            return

        print(f"✅ Обрабатываем фото от пользователя {user_id}")

        # Увеличиваем счетчик фото
        current = photo_submitters.get(user_id, 0) + 1
        photo_submitters[user_id] = current
        print(f"📊 Пользователь {user_id}: {current} фото")

        # Регистрируем дату участия, если еще не было
        if user_id not in user_join_dates:
            user_join_dates[user_id] = datetime.now()
            print(f"📅 Зарегистрирована дата участия для пользователя {user_id}")

        # Дарим подарки по достижению 2 и 4 фото (один раз каждую ступень)
        if current in (2, 4):
            print(f"🎁 Проверяем подарок для {current} фото")
            ok = send_gift_by_count(user_id, current)
            # Сообщаем АДМИНАМ о результате, в группу не пишем
            username_disp = _get_username_display(user_id)
            if ok:
                if current == 2:
                    safe_notify_admins(f"🎁 {username_disp} получил(а) подарок: Сборник салатов 🥗")
                else:
                    safe_notify_admins(f"🎁 {username_disp} получил(а) подарок: Сборник ужинов 🍽️")
            else:
                safe_notify_admins(f"⚠️ {username_disp}: не удалось отправить подарок в ЛС — нет /start")

    except Exception as e:
        print(f"❌ Ошибка в handle_group_photo: {e}")
        try:
            bot.reply_to(message, f"⚠️ Ошибка обработки фото: {e}")
        except Exception:
            pass


def send_plov_offer(user_id):
    if is_stopped(user_id):
        return
    try:
        with open(MEDIA_PATH + 'Праздничные блюда.PNG', 'rb') as photo:
            caption = (
                "Что ещё приготовить праздничного для гостей? 🎉\n\n"
                "Лови подборку из 4-х вкусных блюд, которые точно удивят даже самых привередливых гостей!\n"
                "Кстати, все эти рецепты есть в курсе *Восточная хозяйка* 😍"
            )
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("🌟 Восточный курс", url="https://saniyaiminova.kz/4course"))
            bot.send_photo(user_id, photo, caption=caption, parse_mode="Markdown", reply_markup=markup)
    except Exception as e:
        print(f"Ошибка в send_plov_offer: {e}")

    # Фиксируем, что оффер отправлен
    plov_offer_sent_users.add(user_id)

    # Убираем активный таймер, если есть
    if user_id in plov_offer_timers:
        del plov_offer_timers[user_id]

    # Запуск дожимов
    schedule_after_plov_pushes(user_id)

    # Удаляем из расписания рецептов
    if user_id in user_recipe_schedule:
        del user_recipe_schedule[user_id]


# === Дожимные сообщения ===
def after_plov_push_14(user_id):
    if is_stopped(user_id) or user_id in after_plov_push_14_sent:
        print(f"⏸ Пользователь {user_id} — push 14:00 не отправляется (остановлен или уже отправлен)")
        return

    after_plov_push_14_sent.add(user_id)
    print(f"🍚 Отправляем push 14:00 после плова пользователю {user_id}")
    text = (
        "Представь на минуту:\n\n"
        "— ты готовишь в кайф, с полной уверенностью, что получится вкусно\n"
        "— вечером ты слышишь благодарности и комплименты от родных\n"
        "— ты тратишь на готовку минимум времени, потому что рецепты такие подробные и чёткие\n"
        "— ты легко можешь накрыть шикарный дастархан и встретить достойно гостей\n\n"
        "И всё это возможно вместе с нами!\n\n"
        "🌟 Всего за 4990₸ ты получаешь:\n"
        "— доступ к 104 проверенным рецептам\n"
        "— поддержку от кураторов\n"
        "— тёплое комьюнити женщин, которые вдохновляют готовить и кайфовать на своей кухне ❤️"
    )
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("👑 Стать Восточной Хозяйкой", url="https://saniyaiminova.kz/4course"))
    try:
        with open(MEDIA_PATH + 'Хозяйка.JPG', 'rb') as photo:
            bot.send_photo(user_id, photo, caption=text, reply_markup=markup)
    except Exception as e:
        print(f"Ошибка при отправке фото: {e}")


def after_plov_push_18(user_id):
    if is_stopped(user_id) or user_id in after_plov_push_18_sent:
        print(f"⏸ Пользователь {user_id} — push 18:00 не отправляется (остановлен или уже отправлен)")
        return

    after_plov_push_18_sent.add(user_id)
    print(f"🍚 Отправляем push 18:00 после плова пользователю {user_id}")
    caption = (
        "⏰ Осталось 3 часа!\n\n"
        "Через 3 часа закончится самая выгодная цена на клуб! 🔥\n\n"
        "Ты можешь упустить:\n"
        "— 4 кулинарных курса от шеф-поваров\n"
        "— базу из 104 восточных рецептов\n"
        "— женское сообщество и поддержку\n"
        "— участие в розыгрыше подарков 🎁\n\n"
        "Поторопись, чтобы занять своё место!"
    )
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("🌟 Стать Восточной Хозяйкой", url="https://saniyaiminova.kz/4course"),
        InlineKeyboardButton("❓ Есть вопрос", url=CHAT_LINK)
    )
    try:
        with open(MEDIA_PATH + '3 часа.PNG', 'rb') as photo:
            bot.send_photo(user_id, photo, caption=caption, parse_mode="Markdown", reply_markup=markup)
    except Exception as e:
        print(f"Ошибка при отправке фото: {e}")


def after_plov_push_20(user_id):
    if is_stopped(user_id) or user_id in after_plov_push_20_sent:
        print(f"⏸ Пользователь {user_id} — push 20:00 не отправляется (остановлен или уже отправлен)")
        return

    after_plov_push_20_sent.add(user_id)
    print(f"🍚 Отправляем push 20:00 после плова пользователю {user_id}")
    text = (
        "🕵️ Пора раскрыть тебе тайну…\n\n"
        "Уже через 1 час самая выгодная цена сгорит! 🔥\n\n"
        "Если ты захочешь присоединиться позже, стоимость подписки *«Восточная Хозяйка»* будет уже 14 990₸ 😔\n\n"
        "Раскрываю сразу все карты, чтобы ты потом не сожалела, что не успела!\n\n"
        "Если ты хочешь шикарно готовить и кайфовать на своей кухне — сейчас самое время присоединиться ✨"
    )
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("🌟 Стать Восточной Хозяйкой", url="https://saniyaiminova.kz/4course"),
        InlineKeyboardButton("❓ Есть вопрос", url=CHAT_LINK)
    )
    bot.send_message(user_id, text, parse_mode="Markdown", reply_markup=markup)


# === Расписание дожимных сообщений ===
def schedule_after_plov_pushes(user_id):
    if is_stopped(user_id):
        print(f"⏸ Пользователь {user_id} остановлен - дожимные сообщения после плова не планируются")
        return

    if user_id in after_plov_scheduled:
        print(f"⚠️ Дожимные сообщения для {user_id} уже запланированы, повтор не нужен")
        return

    after_plov_scheduled.add(user_id)

    print(f"🍚 Планируем дожимные сообщения после плова для пользователя {user_id}")
    now = datetime.now()

    # --- Время дожимов ---
    plov_14 = now.replace(hour=14, minute=0, second=0, microsecond=0)
    plov_18 = now.replace(hour=18, minute=0, second=0, microsecond=0)
    plov_20 = now.replace(hour=20, minute=0, second=0, microsecond=0)

    if now >= plov_14:
        plov_14 += timedelta(days=1)
    if now >= plov_18:
        plov_18 += timedelta(days=1)
    if now >= plov_20:
        plov_20 += timedelta(days=1)

    delay_14 = (plov_14 - now).total_seconds()
    delay_18 = (plov_18 - now).total_seconds()
    delay_20 = (plov_20 - now).total_seconds()

    threading.Timer(delay_14, after_plov_push_14, args=[user_id]).start()
    threading.Timer(delay_18, after_plov_push_18, args=[user_id]).start()
    threading.Timer(delay_20, after_plov_push_20, args=[user_id]).start()

    print(f"⏰ Запланировано после плова для пользователя {user_id}:")
    print(f"   📅 14:00 через {delay_14 / 3600:.1f} часов ({plov_14.strftime('%d.%m.%Y %H:%M')})")
    print(f"   📅 18:00 через {delay_18 / 3600:.1f} часов ({plov_18.strftime('%d.%m.%Y %H:%M')})")
    print(f"   📅 20:00 через {delay_20 / 3600:.1f} часов ({plov_20.strftime('%d.%m.%Y %H:%M')})")

# === Дожимные сообщения по дням ===
def send_day6_push(user_id):
    """День 6: Напоминание о конкурсных условиях"""
    if is_stopped(user_id):
        print(f"⏸ Пользователь {user_id} остановлен - день 6 не отправляется")
        return
    if photo_submitters.get(user_id, 0) >= 2:
        print(f"🎁 Пользователь {user_id} уже получил подарок - день 6 не отправляется")
        return

    print(f"📅 Отправляем день 6 пользователю {user_id}")
    try:
        caption = (
            "Привет, дорогая! 💛 Уже прошло 6 дней марафона!\n\n"
            "У тебя получилось приготовить что-то новенькое? Поделись с нами — и получи приз 🎁\n\n"
            "✨ Напоминаю:\n"
            "– за 2 блюда — сборник салатов 🎁\n"
            "– за 4 блюда — сборник 10 ужинов для гостей 🍽️\n\n"
            f"[Перейти в чат]({CHAT_LINK})\n\n"
            "Всё получится — даже если начнёшь сегодня 🌸"
        )
        with open(MEDIA_PATH + '6 день.PNG', 'rb') as photo:
            bot.send_photo(user_id, photo, caption=caption, parse_mode="Markdown")
    except Exception as e:
        bot.send_message(user_id, f"⚠️ Ошибка при отправке сообщения: {e}")


def send_day8_offer(user_id):
    """День 8: Предложение курса"""
    if is_stopped(user_id):
        print(f"⏸ Пользователь {user_id} остановлен - день 8 не отправляется")
        return

    print(f"📅 Отправляем день 8 пользователю {user_id}")
    text = (
        "🎯 *Половина позади — всё ещё можно догнать!*\n\n"
        "До конца марафона осталось 6 дней 🔥\n"
        "Успевай приготовить блюда и порадовать близких, а ещё — забрать наш подарок! 🎁\n\n"
        "Кстати, если тебе понравился марафон, в нашем большом курсе *«Восточная Хозяйка»* тебя ждут ещё *104 восточных рецептов*:\n"
        "— выпечка, супы, закуски, горячее и многое другое 🍽️\n\n"
        "🌟 Хочешь продолжить готовить вкусно и легко? Переходи по кнопке:"
    )
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("👑 Посмотреть курс", url="https://saniyaiminova.kz/4course"))
    bot.send_message(user_id, text, reply_markup=markup, parse_mode="Markdown")


def send_day10_push(user_id):
    """День 10: Последний шанс по старой цене"""
    if is_stopped(user_id):
        print(f"⏸ Пользователь {user_id} остановлен - день 10 не отправляется")
        return

    print(f"📅 Отправляем день 10 пользователю {user_id}")
    text = (
        "⏳ *4 дня до окончания марафона!*\n\n"
        "А это значит — осталось совсем немного, чтобы приготовить и получить подарок 🎁\n\n"
        "Посмотри, какие блюда готовили другие участницы — [ссылка на коллаж/чат]\n\n"
        "Вдохновляйся и действуй 💪\n\n"
        "Если хочешь продолжить готовить в нашем клубе не только восточную кухню, "
        "но и грузинскую, итальянскую, турецкую, ПП, тортики, завтраки, выпечку и многое другое — "
        "напиши мне, я расскажу подробности!"
    )
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🍽 Узнать о клубе", url=CHAT_LINK))
    bot.send_message(user_id, text, reply_markup=markup, parse_mode="Markdown")


def send_day12_check_in(user_id):
    """День 12: Проверка активности"""
    if is_stopped(user_id):
        print(f"⏸ Пользователь {user_id} остановлен - день 12 не отправляется")
        return
    if photo_submitters.get(user_id, 0) > 0:
        print(f"📸 Пользователь {user_id} уже отправлял фото - день 12 не отправляется")
        return

    print(f"📅 Отправляем день 12 пользователю {user_id}")
    text = (
        "💬 *Ты не одна — мы рядом!*\n\n"
        "Видим, что ты давно не заходила — всё ли в порядке?\n"
        "Иногда не хватает вдохновения или времени, и это нормально.\n\n"
        "Но ты можешь вернуться в любой момент — рецепты у тебя всё ещё доступны.\n"
        "Просто нажми кнопку и продолжи марафон — мы с тобой 🤍"
    )
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("🍽 Вернуться к рецептам", callback_data="choose_recipe"),
        InlineKeyboardButton("💬 Задать вопрос куратору", url=CHAT_LINK)
    )
    bot.send_message(user_id, text, parse_mode="Markdown", reply_markup=markup)


def send_day13_reminder(user_id):
    """День 13: Напоминания + Продление участия"""
    if is_stopped(user_id):
        print(f"⏸ Пользователь {user_id} остановлен - день 13 не отправляется")
        return

    print(f"📅 Отправляем день 13 (напоминание) пользователю {user_id}")
    text = (
        "📢 *Завтра — последний день!*\n\n"
        "Уже завтра завершается наш восточный марафон 🍽️\n"
        "Ещё есть время — успей выложить блюдо и получить сборник рецептов! 🎁\n\n"
        "Участницы, кто приготовил 2 или 4 блюда и поделился фото — получают подарки ✨"
    )
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("✅ Я приготовила блюдо", callback_data="dish_done"),
        InlineKeyboardButton("💬 Перейти в чат", url=CHAT_LINK)
    )
    bot.send_message(user_id, text, parse_mode="Markdown", reply_markup=markup)


def send_day13_no_activity(user_id):
    """День 13: Для неактивных пользователей"""
    if is_stopped(user_id):
        print(f"⏸ Пользователь {user_id} остановлен - день 13 (неактивность) не отправляется")
        return
    if photo_submitters.get(user_id, 0) >= 2:
        print(f"🎁 Пользователь {user_id} уже получил подарок - день 13 (неактивность) не отправляется")
        return

    print(f"📅 Отправляем день 13 (неактивность) пользователю {user_id}")
    try:
        caption = (
            "👋 Привет! Вижу, ты не успела приготовить ни одно блюдо из нашего марафона 🥺\n"
            "Очень жаль — видимо, на то были свои обстоятельства.\n\n"
            "Хочешь продлить участие ещё на *14 дней* — всего за *1000₸*?\n"
            "Ты сможешь снова пройти марафон и порадовать себя вкусными блюдами 🍽️"
        )
        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton("🔥 Хочу продлить участие", url="https://wa.me/+77070578182"),
            InlineKeyboardButton("❌ Нет, спасибо", callback_data="no_thanks")
        )
        with open(MEDIA_PATH + '13 день.PNG', 'rb') as photo:
            bot.send_photo(user_id, photo, caption=caption, parse_mode="Markdown", reply_markup=markup)
    except Exception as e:
        bot.send_message(user_id, f"⚠️ Ошибка при отправке сообщения: {e}")


def send_day14_final(user_id):
    """День 14: Финал марафона"""
    if is_stopped(user_id):
        print(f"⏸ Пользователь {user_id} остановлен - день 14 не отправляется")
        return

    print(f"📅 Отправляем день 14 (финал) пользователю {user_id}")
    try:
        if user_states.get(user_id) == "PAID":
            caption = (
                "💛 Спасибо, что прошла с нами марафон!\n"
                "Ты невероятная — уже потому, что выбрала заботиться о себе и своих близких!\n\n"
                "🌟 Увидимся в нашем клубе!\n"
                "Добро пожаловать в курс *Восточная хозяйка* 🍽️"
            )
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("💬 Написать в чат", url=CHAT_LINK))
        else:
            caption = (
                "💛 Спасибо, что прошла с нами марафон!\n"
                "Ты невероятная — уже просто потому, что выбрала заботиться о себе и своих близких!\n\n"
                "Если тебе понравился формат, у нас есть *курс «Восточная хозяйка»*:\n"
                "104 восточных блюда на любой случай — с подробными рецептами и поддержкой.\n\n"
                "Присоединяйся, пока действуют лучшие условия!"
            )
            markup = InlineKeyboardMarkup()
            markup.add(
                InlineKeyboardButton("🌟 Перейти к курсу", url="https://saniyaiminova.kz/4course"),
                InlineKeyboardButton("💬 Есть вопрос", url=CHAT_LINK)
            )
        with open(MEDIA_PATH + '14 день.PNG', 'rb') as photo:
            bot.send_photo(user_id, photo, caption=caption, parse_mode="Markdown", reply_markup=markup)
    except Exception as e:
        bot.send_message(user_id, f"⚠️ Ошибка при отправке финального сообщения: {e}")


def schedule_day_pushes(user_id):
    """Планирует дожимные сообщения по дням"""
    if is_stopped(user_id):
        print(f"⏸ Пользователь {user_id} остановлен - дожимные сообщения не планируются")
        return

    print(f"📅 Планируем дожимные сообщения для пользователя {user_id}")
    now = datetime.now()

    day_pushes = [
        (send_day6_push, 6),   # через 6 дней
        (send_day8_offer, 8),  # через 8 дней
        (send_day10_push, 10), # через 10 дней
        (send_day12_check_in, 12), # через 12 дней
        (send_day13_reminder, 13), # через 13 дней в 11:00
        (send_day13_no_activity, 13.5), # через 13.5 дней в 17:00
        (send_day14_final, 14), # через 14 дней
    ]

    for func, days in day_pushes:
        if days == 13.5:
            send_time = (now + timedelta(days=int(days))).replace(
                hour=17, minute=0, second=0, microsecond=0
            )
        else:
            send_time = (now + timedelta(days=int(days))).replace(
                hour=11, minute=0, second=0, microsecond=0
            )

        delay = (send_time - now).total_seconds()
        if delay > 0:
            threading.Timer(delay, func, args=[user_id]).start()
            print(f"⏰ Запланировано: {func.__name__} для {user_id} на {send_time.strftime('%d.%m.%Y %H:%M')}")
        else:
            print(f"⚠️ Время уже прошло для {func.__name__} пользователя {user_id}")


def check_scheduled_recipes():
    """Проверяет и отправляет рецепты по расписанию автоматически"""
    now = datetime.now()

    if not user_recipe_schedule:
        return

    for user_id, schedule_info in list(user_recipe_schedule.items()):
        if is_stopped(user_id):
            continue

        recipe = schedule_info["next_recipe"]
        next_time = schedule_info["next_recipe_time"]

        if now >= next_time:
            try:
                if recipe == "lagman":
                    send_lagman_recipe(user_id, send_video=True)

                elif recipe == "samsa":
                    send_samsa_recipe(user_id)

                elif recipe == "plov":
                    send_final_recipe(user_id)
                    del user_recipe_schedule[user_id]

            except Exception as e:
                print(f"❌ Ошибка при отправке рецепта {recipe} пользователю {user_id}: {e}")



def check_expired_access():
    """Проверяет всех пользователей на истечение доступа (14 дней)"""
    now = datetime.now()
    expired_users = []

    for user_id, join_date in list(user_join_dates.items()):
        if is_stopped(user_id):
            continue
        days_passed = (now - join_date).days
        if days_passed >= 14:
            expired_users.append(user_id)

    # Удаляем пользователей с истекшим доступом
    for user_id in expired_users:
        remove_from_group(user_id)

    if expired_users:
        pass  # Убрано отладочное сообщение


@bot.message_handler(commands=['help'])
def admin_help(message):
    """Команда для администратора - показывает все доступные команды"""
    # Проверяем, что команда отправлена в личном чате
    if message.chat.type != 'private':
        bot.reply_to(message, "❌ Административные команды работают только в личных сообщениях с ботом")
        return

    if not is_admin(message.from_user.id):
        return

    help_text = (
        "🔧 *Команды администратора:*\n\n"
        "/status - Статистика марафона\n"
        "/users - Список всех участников с ID\n"
        "/user <user_id> - Информация о пользователе\n"
        "/photos - Список пользователей с фото\n"
        "/send_gift <user_id> <2|4> - Отправить подарок\n"
        "/remove <user_id> - Удалить пользователя\n"
        "/stop_user <user_id> - Остановить бота для пользователя\n"
        "/resume_user <user_id> - Возобновить бота для пользователя\n"
        "/mark_paid <user_id> - Пометить как оплаченного\n"


        "/help - Показать эту справку\n\n"
        "📊 *Примеры использования:*\n"
        "/users - посмотреть всех участников\n"
        "/schedule - проверить расписание рецептов\n"
        "/user 123456789 - посмотреть инфо о пользователе\n"
        "/send_gift 123456789 2 - отправить сборник салатов\n"
        "/send_gift 123456789 4 - отправить сборник ужинов\n"
        "/check_group - проверить ID группы\n"
        "/remove 123456789 - удалить пользователя\n"
        "/stop_user 123456789 - остановить бота\n"
        "/resume_user 123456789 - возобновить бота\n"
        "/mark_paid 123456789 - пометить как оплаченного"
    )

    bot.reply_to(message, help_text, parse_mode="Markdown")


@bot.message_handler(commands=['schedule'])
def admin_check_schedule(message):
    """Команда для администратора - показывает текущее расписание рецептов"""
    # Проверяем, что команда отправлена в личном чате
    if message.chat.type != 'private':
        bot.reply_to(message, "❌ Административные команды работают только в личных сообщениях с ботом")
        return

    if not is_admin(message.from_user.id):
        return

    if not user_recipe_schedule:
        bot.reply_to(message, "📅 Расписание рецептов пусто")
        return

    now = datetime.now()
    schedule_info = "📅 *Текущее расписание рецептов:*\n\n"

    for user_id, schedule in user_recipe_schedule.items():
        recipe = schedule["next_recipe"]
        next_time = schedule["next_recipe_time"]

        # Получаем имя пользователя
        username = "Неизвестно"
        try:
            user_info = bot.get_chat(user_id)
            if user_info.username:
                username = f"@{user_info.username}"
            elif user_info.first_name:
                username = user_info.first_name
            else:
                username = f"ID{user_id}"
        except:
            username = f"ID{user_id}"

        # Вычисляем время до отправки
        time_left = next_time - now
        if time_left.total_seconds() > 0:
            hours_left = time_left.total_seconds() / 3600
            if hours_left > 24:
                days_left = hours_left / 24
                time_str = f"через {days_left:.1f} дней"
            else:
                time_str = f"через {hours_left:.1f} часов"
        else:
            time_str = "🔴 ПРОСРОЧЕНО!"

        schedule_info += (
            f"👤 *{username}*\n"
            f"🆔 ID: `{user_id}`\n"
            f"🍽 Рецепт: {recipe}\n"
            f"⏰ Время: {next_time.strftime('%d.%m.%Y %H:%M')}\n"
            f"⏳ Статус: {time_str}\n\n"
        )

        # Ограничиваем длину сообщения
        if len(schedule_info) > 3000:
            schedule_info += "... (список обрезан из-за длины)"
            break

    schedule_info += f"📊 *Всего запланировано:* {len(user_recipe_schedule)} рецептов"

    bot.reply_to(message, schedule_info, parse_mode="Markdown")


@bot.message_handler(commands=['users'])
def admin_users_list(message):
    """Команда для администратора - показывает список всех участников с их ID"""
    # Проверяем, что команда отправлена в личном чате
    if message.chat.type != 'private':
        bot.reply_to(message, "❌ Административные команды работают только в личных сообщениях с ботом")
        return

    if not is_admin(message.from_user.id):
        return

    if not user_join_dates:
        bot.reply_to(message, "📝 Пока нет участников")
        return

    now = datetime.now()
    users_info = "👥 *Список всех участников:*\n\n"

    # Сортируем по дате регистрации
    sorted_users = sorted(user_join_dates.items(), key=lambda x: x[1])

    for user_id, join_date in sorted_users:
        days_passed = (now - join_date).days
        photos_count = photo_submitters.get(user_id, 0)
        marathon_started = user_id in marathon_started_users
        first_recipe = user_id in first_recipe_received_users

        # Получаем имя пользователя
        username = "Неизвестно"
        try:
            # Пытаемся получить информацию о пользователе напрямую
            user_info = bot.get_chat(user_id)
            if user_info.username:
                username = f"@{user_info.username}"
            elif user_info.first_name:
                username = user_info.first_name
            elif user_info.last_name:
                username = f"{user_info.first_name} {user_info.last_name}"
            else:
                username = "Пользователь"
        except:
            # Если не удалось получить информацию, показываем ID
            username = f"ID{user_id}"

        # Статус активности
        if days_passed >= 14:
            status = "⏰ Истек"
        elif marathon_started:
            status = "✅ Активен"
        else:
            status = "🔄 Не начал"

        users_info += (
            f"👤 *{username}*\n"
            f"🆔 ID: `{user_id}`\n"
            f"📅 Регистрация: {join_date.strftime('%d.%m.%Y %H:%M')}\n"
            f"⏰ Дней: {days_passed}/14\n"
            f"📸 Фото: {photos_count}\n"
            f"🍽 Статус: {status}\n\n"
        )

        # Ограничиваем длину сообщения
        if len(users_info) > 3000:
            users_info += "... (список обрезан из-за длины)"
            break

    # Добавляем общую статистику
    total_users = len(user_join_dates)
    active_users = sum(1 for _, join_date in user_join_dates.items() if (now - join_date).days < 14)
    expired_users = total_users - active_users

    users_info += f"\n📊 *Итого:* {total_users} участников\n"
    users_info += f"✅ Активных: {active_users}\n"
    users_info += f"⏰ Истекших: {expired_users}"

    bot.reply_to(message, users_info, parse_mode="Markdown")


@bot.message_handler(commands=['stop_user'])
def admin_stop_user(message):
    # Проверяем, что команда отправлена в личном чате
    if message.chat.type != 'private':
        bot.reply_to(message, "❌ Административные команды работают только в личных сообщениях с ботом")
        return

    if not is_admin(message.from_user.id):
        return
    parts = message.text.split()
    if len(parts) != 2:
        bot.reply_to(message, "❌ Использование: /stop_user <user_id>")
        return
    try:
        uid = int(parts[1])
        stopped_users.add(uid)
        # также очищаем расписание рецептов
        if uid in user_recipe_schedule:
            del user_recipe_schedule[uid]
        bot.reply_to(message, f"⏸ Остановлен бот для пользователя {uid}")
        try:
            bot.send_message(uid, "⏸ Ваши уведомления остановлены администратором. Если это ошибка, напишите куратору.")
        except Exception:
            pass
    except ValueError:
        bot.reply_to(message, "❌ Неверный ID пользователя")


@bot.message_handler(commands=['resume_user'])
def admin_resume_user(message):
    # Проверяем, что команда отправлена в личном чате
    if message.chat.type != 'private':
        bot.reply_to(message, "❌ Административные команды работают только в личных сообщениях с ботом")
        return

    if not is_admin(message.from_user.id):
        return
    parts = message.text.split()
    if len(parts) != 2:
        bot.reply_to(message, "❌ Использование: /resume_user <user_id>")
        return
    try:
        uid = int(parts[1])
        stopped_users.discard(uid)
        # Не восстанавливаем автоматически расписания, чтобы не дублировать; админ может переслать нужный рецепт вручную
        bot.reply_to(message, f"▶ Возобновлен бот для пользователя {uid}")
        try:
            bot.send_message(uid, "▶ Уведомления снова включены. Рады видеть вас!")
        except Exception:
            pass
    except ValueError:
        bot.reply_to(message, "❌ Неверный ID пользователя")


@bot.message_handler(commands=['mark_paid'])
def admin_mark_paid(message):
    # Проверяем, что команда отправлена в личном чате
    if message.chat.type != 'private':
        bot.reply_to(message, "❌ Административные команды работают только в личных сообщениях с ботом")
        return

    if not is_admin(message.from_user.id):
        return
    parts = message.text.split()
    if len(parts) != 2:
        bot.reply_to(message, "❌ Использование: /mark_paid <user_id>")
        return
    try:
        uid = int(parts[1])
        user_states[uid] = "PAID"
        purchased_users.add(uid)
        stopped_users.add(uid)
        if uid in user_recipe_schedule:
            del user_recipe_schedule[uid]
        bot.reply_to(message, f"💳 Пользователь {uid} помечен как оплаченный, уведомления остановлены")
        try:
            bot.send_message(uid, "💳 Оплата подтверждена. Спасибо! Сообщения марафона для вас остановлены.")
        except Exception:
            pass
    except ValueError:
        bot.reply_to(message, "❌ Неверный ID пользователя")


@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    """Обработчик всех сообщений для отладки"""
    if message.from_user.id in ADMIN_IDS:
        print(f"📨 Сообщение от админа {message.from_user.id}:")
        print(f"   Чат ID: {message.chat.id}")
        print(f"   Тип: {message.content_type}")
        print(f"   Текст: {message.text if message.text else 'Нет текста'}")
        print(f"   Фото: {'Есть' if message.photo else 'Нет'}")
        print(f"   Документ: {'Есть' if message.document else 'Нет'}")
        print("---")



@bot.callback_query_handler(func=lambda call: call.data == "no_thanks")
def handle_no_thanks(call):
    user_id = call.from_user.id

    # Проверяем доступ
    if not check_access(user_id):
        bot.answer_callback_query(call.id, text="⏰ Время марафона истекло!", show_alert=True)
        return

    bot.answer_callback_query(call.id)

    # Убираем кнопки
    try:
        bot.edit_message_reply_markup(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=None
        )
    except:
        pass

    # Отправляем финальное сообщение
    bot.send_message(user_id,
                     "💛 Понятно! Спасибо, что была с нами в марафоне!\n\n"
                     "Если передумаешь, всегда можешь присоединиться к нашему курсу "
                     "*«Восточная хозяйка»* — там тебя ждут 104 потрясающих рецепта! 🍽️\n\n"
                     "Удачи и до встречи! ✨")


def start_schedule_checker():
    def loop():
        while True:
            try:
                check_scheduled_recipes()
                check_expired_access()  # Проверяем истекший доступ
            except Exception as e:
                print(f"❌ Ошибка в планировщике: {e}")
            time_module.sleep(60)  # проверка каждую минуту

    threading.Thread(target=loop, daemon=True).start()


def remind_start(user_id):
    """Отправляет напоминание только тем, кто не начал марафон"""
    try:
        # Проверяем, начал ли пользователь марафон
        if user_id in marathon_started_users:
            print(f"⏭️ Пользователь {user_id} уже начал марафон - напоминание не отправляем")
            return

        bot.send_message(user_id, "🕑 Напоминаем: начни марафон, чтобы успеть всё приготовить вовремя!")
        print(f"📢 Напоминание отправлено пользователю {user_id}")
    except Exception as e:
        print(f"❌ Ошибка при отправке напоминания пользователю {user_id}: {e}")


def remind_second_day(user_id):
    """Отправляет второе напоминание на 2-й день только тем, кто не начал марафон"""
    try:
        # Проверяем, начал ли пользователь марафон
        if user_id in marathon_started_users:
            print(f"⏭️ Пользователь {user_id} уже начал марафон - второе напоминание не отправляем")
            return

        message = (
            "❓ <b>Ты не начала марафон — почему? Всё ли ок?</b>\n\n"
            "Прошло уже 2 дня, а ты ещё не начала готовить... 🤔\n\n"
            "Возможно:\n"
            "• Не хватает времени? ⏰\n"
            "• Есть вопросы по рецептам? 💬\n"
            "• Что-то не получается? 😕\n\n"
            "Напиши мне в личку — я помогу! 💛\n"
            "Или просто нажми кнопку ниже и начни прямо сейчас:"
        )

        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🍽 Начать марафон сейчас", callback_data="start_marathon"))

        bot.send_message(user_id, message, parse_mode="HTML", reply_markup=markup)
        print(f"📢 Второе напоминание отправлено пользователю {user_id}")
    except Exception as e:
        print(f"❌ Ошибка при отправке второго напоминания пользователю {user_id}: {e}")


def check_access(user_id):
    """Проверяет, не истек ли доступ пользователя к марафону"""
    if user_id not in user_join_dates:
        return False

    join_date = user_join_dates[user_id]
    days_passed = (datetime.now() - join_date).days

    if days_passed >= 14:
        # Доступ истек - удаляем пользователя
        remove_from_group(user_id)
        return False

    return True


def remove_from_group(user_id):
    """Удаляет пользователя из группы и закрывает доступ к боту после 14 дней"""
    try:
        # Удаляем из группы
        bot.kick_chat_member(GROUP_CHAT_ID, user_id)
        bot.unban_chat_member(GROUP_CHAT_ID, user_id)

        # Отправляем финальное сообщение
        try:
            bot.send_message(user_id,
                             "⏰ *Время марафона истекло!*\n\n"
                             "Доступ к материалам закрыт.\n"
                             "Если хочешь продолжить обучение, присоединяйся к курсу *«Восточная хозяйка»*:\n"
                             "https://saniyaiminova.kz/4course\n\n"
                             "Спасибо за участие! 💛",
                             parse_mode="Markdown")
        except:
            pass

        # Очищаем все данные пользователя
        if user_id in user_join_dates:
            del user_join_dates[user_id]
        if user_id in user_recipe_schedule:
            del user_recipe_schedule[user_id]
        if user_id in marathon_started_users:
            marathon_started_users.remove(user_id)
        if user_id in first_recipe_received_users:
            first_recipe_received_users.remove(user_id)
        if user_id in dish_done_users:
            dish_done_users.remove(user_id)
        if user_id in lagman_done_users:
            lagman_done_users.remove(user_id)
        if user_id in samsa_done_users:
            samsa_done_users.remove(user_id)
        if user_id in plov_done_users:
            plov_done_users.remove(user_id)
        if user_id in user_bonus_selected:
            del user_bonus_selected[user_id]
        if user_id in photo_submitters:
            del photo_submitters[user_id]
        if user_id in user_states:
            del user_states[user_id]

        print(f"✅ Пользователь {user_id} удален из марафона (14 дней истекли)")

    except Exception as e:
        print(f"❌ Ошибка при удалении пользователя {user_id}: {e}")


# Запуск бота
print("\u2705 Бот запущен...")
start_schedule_checker()
bot.infinity_polling()


