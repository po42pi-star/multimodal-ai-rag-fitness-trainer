"""
Image Generation Handler - генерация схем упражнений.
Отправляет ТОЛЬКО ИЗОБРАЖЕНИЯ со схемами упражнений.
"""
import os
import re
import logging
import time
import base64
from pathlib import Path
from io import BytesIO
from typing import Optional

from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ContextTypes

from services.router import router, user_modes

logger = logging.getLogger(__name__)

# Временная директория
TEMP_DIR = Path("temp")
TEMP_DIR.mkdir(exist_ok=True)


# Ключевые слова для генерации упражнений
EXERCISE_KEYWORDS = [
    "как делать", "как выполнять", "техника", "покажи", "схема",
    "упражнение", "упр", "присед", "жим", "подтяг", "отжим",
    "тяга", "планка", "пресс", "отжимание", "подтягивание",
    "становая", "выпады", "махи", "скручивания", "подъём",
    "берпи", "бёрпи", "прыжок", "сгенерируй", "дай схему", "скручивание"
]


async def handle_image_generation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Обрабатывает запросы на генерацию изображений упражнений.
    В режиме image отправляет ТОЛЬКО ИЗОБРАЖЕНИЕ со схемой упражнения.
    
    Returns:
        bool: True если запрос был обработан (изображение отправлено или ошибка),
              False если это не запрос на генерацию упражнения
    """
    user_id = update.message.from_user.id
    text = update.message.text or ""
    text_lower = text.lower()
    current_mode = user_modes.get(user_id, "text")
    
    logger.info(f"[IMAGE_GEN] Пользователь {user_id}, текст: '{text}', режим: {current_mode}")
    
    # Проверяем, есть ли ключевые слова упражнения
    if not any(kw in text_lower for kw in EXERCISE_KEYWORDS):
        logger.info(f"[IMAGE_GEN] Ключевые слова не найдены, выходим")
        return False  # Не запрос на генерацию упражнения
    
    # Извлекаем название упражнения
    exercise_name = extract_exercise_name(text)
    logger.info(f"[IMAGE_GEN] Извлечено название: '{exercise_name}'")
    
    if not exercise_name:
        # Не удалось извлечь название
        if current_mode == "image":
            await update.message.reply_text(
                "❓ Не понял, какое упражнение. Напиши: 'как делать присед' или 'схема жима лёжа'"
            )
        else:
            await update.message.reply_text(
                "📸 Для генерации схемы упражнения переключись в режим **/mode image**!",
                parse_mode="Markdown",
                reply_markup=ReplyKeyboardMarkup(
                    [[KeyboardButton("/mode image")], [KeyboardButton("/mode text")]],
                    resize_keyboard=True
                )
            )
        return True  # Запрос обработан
    
    # Проверяем режим
    if current_mode != "image":
        await update.message.reply_text(
            f"📸 Переключись в режим **/mode image** для генерации схемы *{exercise_name}*!",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup(
                [[KeyboardButton("/mode image")], [KeyboardButton("/mode text")]],
                resize_keyboard=True
            )
        )
        return True  # Запрос обработан
    
    # Генерируем изображение
    try:
        logger.info(f"[IMAGE_GEN] Начинаем генерацию изображения для: '{exercise_name}'")
        
        image_url = router.generate_exercise_image(exercise_name)
        logger.info(f"[IMAGE_GEN] Результат generate_exercise_image: {image_url}")
        
        if image_url:
            logger.info(f"[IMAGE_GEN] Отправляем фото пользователю {user_id}")
            # Отправляем ТОЛЬКО ИЗОБРАЖЕНИЕ - без текста!
            # Поддерживаем и URL, и base64
            if image_url.startswith("data:image"):
                # base64 изображение
                header, b64_data = image_url.split(",", 1)
                image_bytes = base64.b64decode(b64_data)
                await update.message.reply_photo(photo=BytesIO(image_bytes))
            else:
                # URL изображение
                await update.message.reply_photo(photo=image_url)
            logger.info(f"[IMAGE_GEN] Фото отправлено успешно")
            return True  # Запрос обработан
        else:
            # Если не удалось сгенерировать
            logger.warning(f"[IMAGE_GEN] Не удалось сгенерировать изображение для: {exercise_name}")
            await update.message.reply_text(
                f"😔 Не удалось создать изображение для: *{exercise_name}*",
                parse_mode="Markdown"
            )
            return True  # Запрос обработан
            
    except Exception as e:
        logger.error(f"[IMAGE_GEN] Ошибка генерации упражнения: {e}", exc_info=True)
        await update.message.reply_text("😔 Ошибка при генерации изображения.")
        return True  # Запрос обработан


def extract_exercise_name(text: str) -> Optional[str]:
    """Извлекает название упражнения из текста."""
    text_lower = text.lower()
    
    # Список известных упражнений
    known_exercises = {
        "присед": ["присед", "приседания", "приседать", "squat"],
        "жим лёжа": ["жим лёжа", "жим на грудь", "bench press", "жим"],
        "подтягивание": ["подтягивание", "подтягивания", "подтягиваться", "pull up", "подтяг"],
        "отжимание": ["отжимание", "отжимания", "отжиматься", "push up"],
        "становая тяга": ["становая тяга", "deadlift"],
        "выпады": ["выпады", "выпады вперёд", "lunges"],
        "планка": ["планка", "plank"],
        "пресс": ["пресс", "crunch"],
        "скручивания": ["скручивания", "скручивание"],
        "махи": ["махи", "махи руками", "махи ногами", "lateral raise"],
        "тяга": ["тяга", "тяга штанги", "тяга гантели", "rowing"],
        "подъём ног": ["подъём ног", "leg raise"],
        "берпи": ["берпи", "burpee", "burpees", "берп", "бёрпи"],
        "подъём": ["подъём", "подъём штанги", "подъём гантелей"],
        "приседания со штангой": ["приседания со штангой", "front squat"],
        "тяга в наклоне": ["тяга в наклоне", "bent over row"],
    }
    
    # Ищем точное совпадение
    for exercise, keywords in known_exercises.items():
        if any(kw in text_lower for kw in keywords):
            return exercise
    
    # Пробуем извлечь из фразы "как делать X"
    match = re.search(r'как\s+(?:делать|выполнять)\s+([а-яё]+)', text_lower)
    if match:
        found_word = match.group(1)
        stop_words = ["это", "такое", "мне", "тебе", "ему", "ей", "нас", "вас", "них", "что", "когда", "где", "как", "его"]
        if found_word not in stop_words:
            return found_word
    
    # Извлекаем после "упражнение"
    match = re.search(r'упражнен(?:ие|я|ении)\s+(?:на\s+)?(?:для\s+)?(?:мышц\s+)?([а-яё]+)', text_lower)
    if match:
        return match.group(1).strip()
    
    return None