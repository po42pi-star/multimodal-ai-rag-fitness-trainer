"""
Обработчик RAG - работа с базой знаний тренировок.
"""
import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any

from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ContextTypes

from services.router import router, user_data
from utils.file_utils import save_user_data

logger = logging.getLogger(__name__)

# Клавиатура для продолжения тренировок
WORKOUT_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton("/mode text"), KeyboardButton("/mode voice")],
        [KeyboardButton("/mode image"), KeyboardButton("/mode rag")],
        [KeyboardButton("Получить следующую")],
        [KeyboardButton("Показать мою карту")],
    ],
    resize_keyboard=True
)

# Клавиатура после завершения тренировки
WORKOUT_DONE_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton("/mode text"), KeyboardButton("/mode voice")],
        [KeyboardButton("/mode image"), KeyboardButton("/mode rag")],
        [KeyboardButton("Я закончил тренировку")],
        [KeyboardButton("Показать мою карту")],
    ],
    resize_keyboard=True
)

# Клавиатура завершения программы
COMPLETE_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton("/mode text"), KeyboardButton("/mode voice")],
        [KeyboardButton("/mode image"), KeyboardButton("/mode rag")],
        [KeyboardButton("Я закончил 4-х недельную тренировку")],
        [KeyboardButton("Показать мою карту")],
    ],
    resize_keyboard=True
)

# Клавиатура после завершения программы
FINISHED_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton("/mode text"), KeyboardButton("/mode voice")],
        [KeyboardButton("/mode image"), KeyboardButton("/mode rag")],
        [KeyboardButton("Купить подписку")],
        [KeyboardButton("Начать заново")],
    ],
    resize_keyboard=True
)


async def handle_rag_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает запросы в режиме RAG."""
    user_id = update.message.from_user.id
    query = update.message.text
    
    logger.info(f"RAG запрос от {user_id}: {query}")
    
    # Ищем в базе знаний
    response = router.route_rag_request(user_id, query)
    
    try:
        await update.message.reply_text(response, parse_mode="Markdown")
    except Exception:
        # Если Markdown не парсится - отправляем без разметки
        await update.message.reply_text(response)


async def handle_get_workout(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает запрос на получение тренировки."""
    user_id = update.message.from_user.id
    
    if user_id not in user_data:
        await update.message.reply_text("❌ Профиль не заполнен. Нажмите 'Поехали!'")
        return
    
    profile = user_data[user_id]
    workout_day = profile.get("workout_day", 1)
    current_week = profile.get("current_week", 1)
    
    # Проверяем, завершена ли программа
    if workout_day > 28:
        await show_completion_message(update)
        return
    
    # Получаем предыдущую тренировку
    previous_workout = profile.get("last_workout", {})
    
    # Генерируем тренировку
    workout_text = router.generate_workout(
        user_id=user_id,
        week=current_week,
        day=workout_day,
        previous_workout=previous_workout
    )
    
    # Сохраняем текущую тренировку
    profile["last_workout"] = {
        "week": current_week,
        "day": workout_day,
        "text": workout_text
    }
    profile["in_workout"] = True
    
    save_user_data(user_id, profile)
    
    # Формируем сообщение с кнопкой
    message_text = f"{workout_text}\n\n🔽 Нажмите кнопку когда закончите:"
    
    # Выбираем правильную клавиатуру
    if workout_day >= 28:
        keyboard = COMPLETE_KEYBOARD
    else:
        keyboard = WORKOUT_DONE_KEYBOARD
    
    try:
        await update.message.reply_text(
            message_text,
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
    except Exception:
        # Если Markdown не парсится - отправляем без разметки
        await update.message.reply_text(
            message_text,
            reply_markup=keyboard
        )
    
    logger.info(f"Отправлена тренировка {current_week}.{workout_day} пользователю {user_id}")


async def handle_workout_complete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает завершение тренировки."""
    user_id = update.message.from_user.id
    
    if user_id not in user_data:
        await update.message.reply_text("❌ Профиль не заполнен. Нажмите 'Поехали!'")
        return
    
    profile = user_data[user_id]
    workout_day = profile.get("workout_day", 1)
    current_week = profile.get("current_week", 1)
    
    # Добавляем тренировку в историю
    if "workouts_completed" not in profile:
        profile["workouts_completed"] = []
    
    profile["workouts_completed"].append({
        "week": current_week,
        "day": workout_day,
        "completed_at": str(datetime.now())
    })
    
    # Обновляем счетчик
    profile["in_workout"] = False
    
    if workout_day < 28:
        profile["workout_day"] = workout_day + 1
        
        # Обновляем неделю
        if workout_day % 7 == 0:
            profile["current_week"] = current_week + 1
        
        save_user_data(user_id, profile)
        
        # Поздравляем и предлагаем следующую
        completed_percent = int((workout_day / 28) * 100)
        
        try:
            await update.message.reply_text(
                f"🎉 Отлично! Тренировка {current_week}.{workout_day} завершена!\n\n"
                f"📊 Прогресс: {completed_percent}% (день {workout_day} из 28)\n"
                f"📅 Неделя: {current_week} из 4\n\n"
                f"🔽 Нажмите 'Получить следующую' для продолжения!",
                reply_markup=WORKOUT_KEYBOARD,
                parse_mode="Markdown"
            )
        except Exception:
            await update.message.reply_text(
                f"🎉 Отлично! Тренировка {current_week}.{workout_day} завершена!\n\n"
                f"📊 Прогресс: {completed_percent}% (день {workout_day} из 28)\n"
                f"📅 Неделя: {current_week} из 4\n\n"
                f"🔽 Нажмите 'Получить следующую' для продолжения!",
                reply_markup=WORKOUT_KEYBOARD
            )
    else:
        # Программа завершена
        await show_completion_message(update)


async def show_completion_message(update: Update) -> None:
    """Показывает сообщение о завершении программы."""
    message = """
🏆 Поздравляем! Вы завершили 4-недельную программу тренировок!

Вы прошли все 28 тренировок и значительно улучшили свою форму!

💪 Результаты:
• Приобрели регулярность тренировок
• Освоили базовые упражнения
• Улучшили физическую подготовку

🔄 Хотите продолжить? Оформите подписку на 1 месяц всего за 600 рублей!
Это всего 20 рублей за тренировку — гораздо дешевле фитнес-зала!

📲 Оформить подписку: /subscribe
🔄 Начать заново: /start
"""
    
    try:
        await update.message.reply_text(
            message,
            reply_markup=FINISHED_KEYBOARD,
            parse_mode="Markdown"
        )
    except Exception:
        await update.message.reply_text(
            message,
            reply_markup=FINISHED_KEYBOARD
        )


async def handle_show_card(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает карту пользователя."""
    user_id = update.message.from_user.id
    
    if user_id not in user_data:
        await update.message.reply_text("❌ Профиль не заполнен. Нажмите 'Поехали!'")
        return
    
    profile = user_data[user_id]
    completed = len(profile.get("workouts_completed", []))
    total = 28
    
    card_text = f"""
📋 Ваша карта тренировок

Профиль:
• Возраст: {profile.get('age', 'не указан')} лет
• Пол: {profile.get('gender', 'не указан')}
• Рост: {profile.get('height', 'не указан')} см
• Вес: {profile.get('weight', 'не указан')} кг
• Уровень активности: {profile.get('activity_level', 'не указан')}
• Цель: {profile.get('goal', 'не указана')}

Прогресс:
• Тренировок: {completed} из {total}
• Неделя: {profile.get('current_week', 1)} из 4
• Процент: {int((completed/total)*100)}%
"""
    
    await update.message.reply_text(card_text, parse_mode="Markdown")
