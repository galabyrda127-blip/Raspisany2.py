import asyncio
import os

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import aiohttp

from aiogram import Bot, Dispatcher
from apscheduler.schedulers.asyncio import AsyncIOScheduler


# =========================
# НАСТРОЙКИ
# =========================

# Токен Telegram-бота
TOKEN = os.getenv("BOT_TOKEN") 

# Ссылка на сервис, который возвращает JSON с расписанием
SCHEDULE_URL = "https://gist.githubusercontent.com/galabyrda127-blip/acf6e4249be8146eb39e5b4f9787767d/raw/4c9c527871eccc74a3ae17dee9f9193786904e46/schedule.json"

# Часовой пояс
TIMEZONE = "Europe/Minsk"

# Дата, с которой начинается 1-я неделя
FIRST_WEEK_DATE = datetime(2026, 9, 7).date()


# =========================
# ПРОВЕРКА TOKEN
# =========================

if not TOKEN:
    raise ValueError(
        "Не задан BOT_TOKEN. "
        "Добавь токен бота в переменную окружения BOT_TOKEN."
    )


# =========================
# TELEGRAM
# =========================

bot = Bot(token=TOKEN)
dp = Dispatcher()


# Сюда будут записываться пользователи,
# которые нажали /start
users = set()


# =========================
# ОПРЕДЕЛЯЕМ НЕДЕЛЮ
# =========================

def get_week_number(date):
    """
    7–13 сентября = 1 неделя
    14–20 сентября = 2 неделя
    21–27 сентября = 1 неделя
    28 сентября–4 октября = 2 неделя
    и т.д.
    """

    difference = (date - FIRST_WEEK_DATE).days

    # Если дата раньше 7 сентября
    if difference < 0:
        return None

    # Чередуем 1 и 2 неделю
    if (difference // 7) % 2 == 0:
        return 1
    else:
        return 2


# =========================
# ПОЛУЧАЕМ JSON С СЕРВЕРА
# =========================

async def get_schedule_from_server():
    """
    Делает HTTP GET запрос к сервису
    и получает JSON.
    """

    try:

        async with aiohttp.ClientSession() as session:

            async with session.get(
                SCHEDULE_URL,
                timeout=10
            ) as response:

                # Если сервер вернул ошибку,
                # например 404 или 500,
                # здесь возникнет исключение
                response.raise_for_status()

                # Получаем JSON
                data = await response.json(content_type=None
                )

                print("JSON успешно получен.")

                return data

    except aiohttp.ClientError as error:

        print(
            f"Ошибка соединения с сервером: {error}"
        )

        return None

    except asyncio.TimeoutError:

        print(
            "Ошибка: сервер слишком долго отвечает."
        )

        return None

    except Exception as error:

        print(
            f"Ошибка при получении JSON: {error}"
        )

        return None


# =========================
# ПОЛУЧАЕМ РАСПИСАНИЕ НА ЗАВТРА
# =========================

async def get_tomorrow_schedule():

    tz = ZoneInfo(TIMEZONE)

    today = datetime.now(tz).date()

    tomorrow = today + timedelta(days=1)


    # Названия дней недели
    weekday_names = {
        0: "Понедельник",
        1: "Вторник",
        2: "Среда",
        3: "Четверг",
        4: "Пятница",
        5: "Суббота",
        6: "Воскресенье"
    }


    # Определяем название завтрашнего дня
    tomorrow_name = weekday_names[tomorrow.weekday()]


    # Определяем неделю
    week = get_week_number(tomorrow)


    # Получаем JSON от сервера
    data = await get_schedule_from_server()


    # Если сервер не ответил
    if data is None:
        return None


    # Получаем список занятий
    lessons = data.get("schedule", [])


    # Здесь будут подходящие пары
    result = []


    # Перебираем все пары из JSON
    for lesson in lessons:

        # Проверяем день недели
        if lesson.get("day") != tomorrow_name:
            continue


        # Какая неделя указана у пары
        lesson_week = lesson.get("week")


        # Если week = null,
        # значит пара каждую неделю
        #
        # Или если номер недели совпадает
        if lesson_week is None or lesson_week == week:

            result.append(lesson)


    # Сортируем пары по времени
    result.sort(
        key=lambda lesson: lesson.get("time", "")
    )


    return (
        tomorrow,
        tomorrow_name,
        week,
        result
    )


# =========================
# ФОРМИРУЕМ СООБЩЕНИЕ
# =========================

async def create_message():

    result = await get_tomorrow_schedule()


    # Если не удалось получить расписание
    if result is None:

        return (
            "⚠️ <b>Не удалось получить расписание.</b>\n\n"
            "Сервер с расписанием недоступен."
        )


    tomorrow, day_name, week, lessons = result


    # Форматируем дату
    date_text = tomorrow.strftime("%d.%m.%Y")


    # Определяем название недели
    if week == 1:

        week_text = "1 неделя"

    elif week == 2:

        week_text = "2 неделя"

    else:

        week_text = "неделя не определена"


    # Начало сообщения
    text = (
        f"📚 <b>Расписание группы 10903723</b>\n\n"
        f"📅 <b>{day_name}, {date_text}</b>\n"
        f"🔄 {week_text}\n\n"
    )


    # Если занятий нет
    if not lessons:

        text += "🎉 <b>Завтра пар нет!</b>"

        return text


    # Выводим только существующие пары
    for number, lesson in enumerate(
        lessons,
        start=1
    ):

        # Время
        text += (
            f"<b>{number}. "
            f"{lesson.get('time', '')}</b>\n"
        )


        # Название предмета
        text += (
            f"📖 {lesson.get('name', '')}\n"
        )


        # Преподаватель
        teacher = lesson.get("teacher")

        if teacher:

            text += (
                f"👨‍🏫 {teacher}\n"
            )


        # Аудитория
        room = lesson.get("room")

        if room:

            text += (
                f"📍 {room}\n"
            )


        text += "\n"


    return text


# =========================
# КОМАНДА /START
# =========================

@dp.message()
async def start_handler(message):

    if message.text == "/start":

        # Запоминаем пользователя
        users.add(message.chat.id)


        await message.answer(
            "👋 Привет!\n\n"
            "Я буду отправлять тебе расписание "
            "группы <b>10903723</b> каждый день "
            "в 18:00 на следующий день.\n\n"
            "Команда /schedule — "
            "посмотреть расписание на завтра.",
            parse_mode="HTML"
        )


    elif message.text == "/schedule":

        # Тоже запоминаем пользователя
        users.add(message.chat.id)


        # Получаем расписание
        text = await create_message()


        # Отправляем расписание
        await message.answer(
            text,
            parse_mode="HTML"
        )


# =========================
# ОТПРАВКА В 18:00
# =========================

async def send_schedule():

    print()
    print("==============================")
    print("Получаю расписание с сервера...")
    print("==============================")


    # Получаем расписание
    text = await create_message()


    print("Расписание сформировано.")
    print("Количество пользователей:", len(users))


    # Отправляем каждому пользователю
    for user_id in users:

        try:

            await bot.send_message(
                user_id,
                text,
                parse_mode="HTML"
            )


            print(
                f"Расписание отправлено: {user_id}"
            )


        except Exception as error:

            print(
                f"Ошибка отправки пользователю "
                f"{user_id}: {error}"
            )


# =========================
# ЗАПУСК
# =========================

async def main():

    # Создаём планировщик
    scheduler = AsyncIOScheduler(
        timezone=TIMEZONE
    )


    # Каждый день в 18:00
    scheduler.add_job(
        send_schedule,
        "cron",
        hour=18,
        minute=0
    )


    # Запускаем планировщик
    scheduler.start()


    print("==============================")
    print("Бот запущен!")
    print("==============================")
    print("Группа: 10903723")
    print("Часовой пояс:", TIMEZONE)
    print("Расписание: каждый день в 18:00")
    print("Источник:", SCHEDULE_URL)
    print("==============================")


    # Запускаем Telegram-бота
    await dp.start_polling(bot)


# =========================
# START
# =========================

if __name__ == "__main__":

    asyncio.run(main())
