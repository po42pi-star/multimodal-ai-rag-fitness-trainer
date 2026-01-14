"""
Обработчик текстовых сообщений.
"""
import json
import re
import logging
from typing import Optional, Dict, Any

from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ContextTypes

from services.router import router, user_modes, user_data
from utils.file_utils import save_user_data
from services.openai_client import openai_client
from handlers.voice import send_voice_response as send_voice_tts
from handlers.start import save_profile_handler

logger = logging.getLogger(__name__)

# Клавиатура для сохранения профиля
SAVE_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton("/mode text"), KeyboardButton("/mode voice")],
        [KeyboardButton("/mode image"), KeyboardButton("/mode rag")],
        [KeyboardButton("Сохранить")],
        [KeyboardButton("Заполнить заново")],
    ],
    resize_keyboard=True
)

# Клавиатура после сохранения
AFTER_SAVE_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton("/mode text"), KeyboardButton("/mode voice")],
        [KeyboardButton("/mode image"), KeyboardButton("/mode rag")],
        [KeyboardButton("Получить 1-ую тренировку")],
        [KeyboardButton("Показать мою карту")],
    ],
    resize_keyboard=True
)

# Клавиатура после тренировки
WORKOUT_DONE_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton("/mode text"), KeyboardButton("/mode voice")],
        [KeyboardButton("/mode image"), KeyboardButton("/mode rag")],
        [KeyboardButton("Я закончил тренировку")],
        [KeyboardButton("Показать мою карту")],
    ],
    resize_keyboard=True
)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Основной обработчик текстовых сообщений."""
    user_id = update.message.from_user.id
    text = update.message.text
    
    logger.info(f"Текст от {user_id}: {text}")
    
    # === ОТВЕТЫ НА ЧАСТЫЕ ВОПРОСЫ ===
    # "Зачем кнопка Поехали?" и подобные вопросы
    # Убираем знаки препинания для корректного поиска
    clean_text = text.lower().replace("!", "").replace("?", "").replace(".", "")
    
    if any(phrase in clean_text for phrase in [
        "зачем кнопка поехали", "зачем поехали", "что такое поехали",
        "для чего поехали", "зачем эта кнопка", "что такое поехали",
        "для чего кнопка поехали", "зачем нужна кнопка поехали"
    ]):
        await update.message.reply_text(
            "🏃 **Кнопка \"Поехали!\"** запускает создание твоей персональной карты тренировок!\n\n"
            "После нажатия бот попросит указать:\n"
            "• Возраст, рост, вес\n"
            "• Уровень активности\n"
            "• Цель (похудеть/набрать/поддержание)\n"
            "• Ограничения (если есть)\n\n"
            "На основе этих данных я составлю идеальный план тренировок на 4 недели! 🔥"
        )
        return
    
    # Обрабатываем команды (перехватываются в bot.py)
    if text.startswith("/"):
        return
    
    # === ПРОВЕРКА СПЕЦИАЛЬНЫХ КНОПОК ===
    # "Поехали!" - начать заполнение профиля
    if text == "Поехали!":
        from handlers.start import poehali_callback
        await poehali_callback(update, context)
        return
    
    # "Сохранить" - сохранить профиль
    if text == "Сохранить":
        await save_profile_handler(update, context)
        return
    
    # "Заполнить заново" - перезапуск
    if text == "Заполнить заново":
        from handlers.start import poehali_callback
        await poehali_callback(update, context)
        return
    
    # "Получить 1-ую тренировку" / "Получить следующую" / "Получить тренировку"
    if text in ["Получить 1-ую тренировку", "Получить следующую", "Получить тренировку"]:
        from handlers.rag import handle_get_workout
        await handle_get_workout(update, context)
        return
    
    # "Я закончил тренировку" / "Я закончил 4-х недельную тренировку"
    if text in ["Я закончил тренировку", "Я закончил 4-х недельную тренировку"]:
        from handlers.rag import handle_workout_complete
        await handle_workout_complete(update, context)
        return
    
    # "Показать мою карту"
    if text == "Показать мою карту":
        from handlers.rag import handle_show_card
        await handle_show_card(update, context)
        return
    
    # === ПРОВЕРКА СОСТОЯНИЙ ===
    # Проверяем состояние сбора профиля
    profile_state = user_data.get(user_id, {}).get("profile_state")
    
    if profile_state == "collecting":
        await handle_profile_input(update, context, text)
        return
    
    # Проверяем, заполняет ли пользователь профиль (старый флаг)
    if user_id in user_data and not user_data[user_id].get("profile_complete"):
        await handle_profile_input(update, context, text)
        return
    
    # Проверяем, находится ли пользователь в процессе тренировки
    if user_id in user_data and user_data[user_id].get("in_workout"):
        await handle_workout_feedback(update, context, text)
        return
    
    # === ПРОВЕРКА ЗАПРОСОВ НА ГЕНЕРАЦИЮ УПРАЖНЕНИЙ ===
    from handlers.image_generation import handle_image_generation
    handled = await handle_image_generation(update, context)
    
    # Если запрос на генерацию упражнения был обработан - выходим
    if handled:
        return
    
    # === ОБЫЧНЫЙ ТЕКСТОВЫЙ ЗАПРОС ===
    response = router.route_text_request(user_id, text)
    
    # В режиме voice отправляем голосом, иначе текстом
    if user_modes.get(user_id) == "voice":
        await send_voice_tts(update, response)
    else:
        await update.message.reply_text(response)


async def handle_profile_input(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    """Обрабатывает ввод данных профиля."""
    user_id = update.message.from_user.id
    
    # Инициализируем структуру если нужно
    if "fields" not in user_data[user_id]:
        user_data[user_id]["fields"] = {}
        user_data[user_id]["profile_state"] = "collecting"
    
    fields = user_data[user_id]["fields"]
    
    # Парсим входящие данные с помощью LLM
    profile_data = await parse_profile_with_llm(text, fields)
    
    # Обновляем данные
    if profile_data:
        fields.update(profile_data)
    
    # Проверяем, все ли поля заполнены
    required_fields = ["age", "gender", "height", "weight", "activity_level", "goal"]
    missing_fields = [f for f in required_fields if f not in fields or not fields.get(f)]
    
    if missing_fields:
        # Запрашиваем недостающие поля
        missing_text = ", ".join(missing_fields)
        prompt = f"""
📝 Понял! Но не хватает данных: *{missing_text}*

Пожалуйста, укажи {missing_text[0].lower() + missing_text[1:]}."""
        await update.message.reply_text(prompt, parse_mode="Markdown")
        return
    
    # Все поля заполнены - сохраняем профиль
    user_data[user_id].update(fields)
    user_data[user_id]["profile_complete"] = True
    user_data[user_id]["profile_state"] = "complete"
    
    # Определяем возрастную группу
    age = fields.get("age", 25)
    if age < 18:
        age_group = "under_18"
    elif age < 30:
        age_group = "18-30"
    elif age < 45:
        age_group = "30-45"
    elif age < 60:
        age_group = "45-60"
    else:
        age_group = "60+"
    
    user_data[user_id]["age_group"] = age_group
    user_data[user_id]["workout_day"] = 1
    user_data[user_id]["current_week"] = 1
    user_data[user_id]["in_workout"] = False
    user_data[user_id]["workouts_completed"] = []
    
    # Сохраняем в файл
    save_user_data(user_id, user_data[user_id])
    
    # Показываем карту пользователя
    profile_text = f"""
✅ **Отлично! Профиль заполнен!**

📋 **Твоя карта:**
• Возраст: {fields.get('age')} лет
• Пол: {fields.get('gender')}
• Рост: {fields.get('height')} см
• Вес: {fields.get('weight')} кг
• Активность: {fields.get('activity_level')} уровень
• Ограничения: {fields.get('limitations', 'нет')}
• Цель: {fields.get('goal')}

📅 4 недели × 7 дней = 28 тренировок

🔽 Нажми **"Получить 1-ую тренировку"** чтобы начать!
"""
    
    await update.message.reply_text(
        profile_text,
        reply_markup=AFTER_SAVE_KEYBOARD,
        parse_mode="Markdown"
    )


async def parse_profile_with_llm(text: str, current_fields: dict) -> dict:
    """
    Парсит текст профиля с помощью LLM для извлечения данных.
    """
    required_fields = ["age", "gender", "height", "weight", "activity_level", "limitations", "goal"]
    current_values = {k: v for k, v in current_fields.items() if v}
    
    prompt = f"""
Извлеки данные о пользователе из текста. Верни JSON без markdown.

Уже известно:
{json.dumps(current_values, ensure_ascii=False, indent=2)}

Текст пользователя:
"{text}"

Верни JSON только с НОВЫМИ полями из этого текста. Если поле не упоминается - не включай его.
Поля:
- age: число (лет)
- gender: "male" или "female"
- height: число (см)
- weight: число (кг)
- activity_level: 1-4 (1=сидячий, 2=легкий, 3=средний, 4=высокий)
- limitations: строка или "нет"
- goal: "Набор массы", "Похудение" или "Поддержание формы"

Ответ только JSON:
"""
    
    try:
        response = openai_client.chat_completion([
            {"role": "user", "content": prompt}
        ], temperature=0, max_tokens=500)
        
        # Парсим JSON из ответа
        json_str = response.strip()
        # Убираем markdown блок если есть
        if json_str.startswith("```"):
            json_str = json_str.split("```")[1]
            if json_str.startswith("json"):
                json_str = json_str[4:]
        
        return json.loads(json_str)
    except Exception as e:
        logger.error(f"Ошибка парсинга профиля LLM: {e}")
        # Фоллбек на старый парсер
        return parse_profile_text(text)


def parse_profile_text(text: str) -> dict:
    """Парсит текст профиля и извлекает данные."""
    result = {}
    text_lower = text.lower()
    
    # Возраст
    age_match = re.search(r'(\d{1,3})\s*(лет|год|г\.?)', text_lower)
    if age_match:
        result["age"] = int(age_match.group(1))
    
    # Пол
    if any(w in text_lower for w in ["муж", "мужской", "мальчик"]):
        result["gender"] = "male"
    elif any(w in text_lower for w in ["жен", "женский", "девочка", "девушка"]):
        result["gender"] = "female"
    
    # Рост
    height_match = re.search(r'рост\s*:?\s*(\d{2,3})', text_lower)
    if height_match:
        result["height"] = int(height_match.group(1))
    
    # Вес
    weight_match = re.search(r'(вес|масса)\s*:?\s*(\d{2,3})', text_lower)
    if weight_match:
        result["weight"] = int(weight_match.group(2))
    
    # Уровень активности (число 1-4)
    activity_match = re.search(r'активност.*?(\d)', text_lower)
    if activity_match:
        result["activity_level"] = int(activity_match.group(1))
    
    # Ограничения
    limitations_match = re.search(r'ограничени[яе].*?:?\s*(.+?)(?:\.|,|$)', text_lower)
    if limitations_match:
        result["limitations"] = limitations_match.group(1).strip()
    elif "нет" in text_lower or "без" in text_lower:
        result["limitations"] = "нет"
    else:
        result["limitations"] = "не указаны"
    
    # Цель
    if any(w in text_lower for w in ["набор", "масс", "нарастит"]):
        result["goal"] = "Набор массы"
    elif any(w in text_lower for w in ["похуд", "снизит", "сброс"]):
        result["goal"] = "Похудение"
    elif any(w in text_lower for w in ["поддерж", "сохрани"]):
        result["goal"] = "Поддержание формы"
    
    return result


async def handle_workout_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    """Обрабатывает обратную связь во время/после тренировки."""
    user_id = update.message.from_user.id
    text_lower = text.lower()
    
    if "не понял" in text_lower or "как делать" in text_lower or "не знаю" in text_lower:
        # Генерируем схематичное изображение упражнения
        workout = user_data[user_id].get("current_workout", {})
        exercise_name = workout.get("exercises", [{}])[0].get("name", "Присед")
        
        await update.message.reply_text(
            f"🤔 Не понял, какое упражнение вызвало затруднение?\n\n"
            f"Давай покажу технику: *{exercise_name}*"
        )
        
        # Генерируем изображение
        image_url = router.generate_exercise_image(exercise_name)
        
        if image_url:
            await update.message.reply_photo(image_url)
        else:
            # Если не удалось сгенерировать, отправляем текстовую инструкцию
            await update.message.reply_text(
                f"**Техника выполнения: {exercise_name}**\n\n"
                f"1. Встань, ноги на ширине плеч\n"
                f"2. Спина прямая, взгляд вперед\n"
                f"3. Опускайся медленно, контролируя движение\n"
                f"4. Колени не сгибай сильнее 90 градусов\n"
                f"5. Поднимайся, используя мышцы ног",
                parse_mode="Markdown"
            )
        
        return
    
    # Стандартный ответ
    response = router.route_text_request(user_id, text)
    await update.message.reply_text(response)
