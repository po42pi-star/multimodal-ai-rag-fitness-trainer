
"""
Image Handler - анализ изображений еды.
Отправляет ТЕКСТ с описанием, БЖУ и калориями.
"""
import os
import logging
import random
from pathlib import Path
from typing import Optional

from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ContextTypes

from services.router import router, user_modes, user_data

logger = logging.getLogger(__name__)

# Временная директория
TEMP_DIR = Path("temp")
TEMP_DIR.mkdir(exist_ok=True)


async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обрабатывает изображение от пользователя (анализ еды).
    В режиме image отправляет ТЕКСТ с БЖУ и калориями.
    """
    user_id = update.message.from_user.id
    current_mode = user_modes.get(user_id, "text")
    
    # Проверяем режим
    if current_mode != "image":
        await update.message.reply_text(
            f"📸 Для анализа фото переключись в режим **/mode image**!",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup(
                [[KeyboardButton("/mode image")], [KeyboardButton("/mode text")]],
                resize_keyboard=True
            )
        )
        return
    
    try:
        # Получаем файл изображения
        photo = update.message.photo[-1]
        file_id = photo.file_id
        
        # Скачиваем файл
        local_path = await download_image(context.bot, update.message, file_id)
        
        if not local_path:
            await update.message.reply_text("😔 Не удалось загрузить изображение.")
            return
        
        logger.info(f"Изображение загружено: {local_path}")
        
        # Анализируем - еда или нет
        is_food = await check_if_food(local_path)
        
        if not is_food:
            # Не еда - отправляем шутку ТЕКСТОМ
            joke = get_non_food_joke(local_path)
            await update.message.reply_text(joke)
        else:
            # Еда - анализируем БЖУ и калории ТЕКСТОМ
            result = await analyze_food(local_path)
            await update.message.reply_text(result, parse_mode="Markdown")
        
        # Удаляем временный файл
        if os.path.exists(local_path):
            os.remove(local_path)
        
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await update.message.reply_text("😔 Ошибка при анализе изображения.")


async def check_if_food(image_path: str) -> bool:
    """Проверяет, является ли изображение едой."""
    try:
        from services.openai_client import openai_client
        
        result = openai_client.analyze_image(
            image_path,
            prompt="Ответь одним словом: FOOD если на картинке еда/напиток, NOT_FOOD если нет. Только слово."
        )
        return "FOOD" in result.upper()
    except Exception as e:
        logger.error(f"Ошибка проверки еды: {e}")
        return True


async def analyze_food(image_path: str) -> str:
    """Анализирует еду и возвращает ТЕКСТ с БЖУ и калориями."""
    from services.openai_client import openai_client
    
    try:
        result = openai_client.analyze_image(
            image_path,
            prompt="""Проанализируй это блюдо и определи:
1. Что это за блюдо
2. Примерное количество калорий
3. Белки, жиры, углеводы (БЖУ)
4. Краткая оценка для фитнеса

Формат ответа:
🍽️ **Блюдо:** [название]
📊 **Калории:** ~XXX ккал
💪 **Белки:** Xг | **Жиры:** Xг | **Углеводы:** Xг
⭐ **Оценка:** [комментарий]"""
        )
        return result
    except Exception as e:
        logger.error(f"Ошибка анализа еды: {e}")
        return "😔 Не удалось проанализировать блюдо."


def get_non_food_joke(image_path: str) -> str:
    """Возвращает шутку для не-еды."""
    jokes = [
        "😄 Всё имеет калории, но этот кот/пейзаж не очень-то съедобен! Отправь фото еды — посчитаю калории!",
        "🍽️ Красивая картинка, но я фитнес-тренер, а не диетолог! Дай фото блюда!",
        "🤔 Интересное фото! Но я могу помочь только с едой. Это точно не борщ? 🙃",
        "😋 Все имеет калории, но твой кот/предмет вряд ли вкусный!",
        "🏋️ Я фитнес-тренер, а не искусствовед! Фото еды — получишь калории!",
    ]
    return random.choice(jokes)


async def download_image(bot, message, file_id: str) -> Optional[str]:
    """Скачивает изображение."""
    try:
        file_info = await bot.get_file(file_id)
        file_ext = Path(file_info.file_path).suffix or ".jpg"
        filename = f"{message.from_user.id}_{message.message_id}{file_ext}"
        save_path = TEMP_DIR / filename
        await file_info.download_to_drive(str(save_path))
        return str(save_path)
    except Exception as e:
        logger.error(f"Ошибка скачивания: {e}")
        return None
