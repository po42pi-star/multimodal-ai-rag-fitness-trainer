"""
Обработчик голосовых сообщений.
"""
import os
import logging
from pathlib import Path

from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ContextTypes

from services.router import router, user_modes
from utils.speech_to_text import speech_to_text
from utils.text_to_speech import text_to_speech

logger = logging.getLogger(__name__)

# Временная директория для аудио
TEMP_AUDIO_DIR = Path("temp/audio")
TEMP_AUDIO_DIR.mkdir(parents=True, exist_ok=True)


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает голосовое сообщение."""
    user_id = update.message.from_user.id
    current_mode = user_modes.get(user_id, "text")
    
    # Проверяем режим - если не voice, сообщаем о необходимости переключения
    if current_mode != "voice":
        await update.message.reply_text(
            f"🎤 Сначала переключись в голосовой режим!\n\n"
            f"Текущий режим: **{current_mode.upper()}**\n"
            f"Нажми: **/mode voice** или выбери из меню 👇",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup(
                [[KeyboardButton("/mode voice")], [KeyboardButton("/mode text")]],
                resize_keyboard=True
            )
        )
        return
    
    try:
        # Получаем файл голосового сообщения
        voice_file = await context.bot.get_file(update.message.voice.file_id)
        
        # Скачиваем во временную директорию
        ogg_path = TEMP_AUDIO_DIR / f"{user_id}_{update.message.message_id}.ogg"
        await voice_file.download_to_drive(str(ogg_path))
        
        logger.info(f"Голосовое скачано: {ogg_path}")
        
        # Распознаем текст
        text = speech_to_text(str(ogg_path))
        
        logger.info(f"Распознанный текст: {text}")
        
        # Показываем пользователю, что мы поняли
        await update.message.reply_text(f"🎤 Вы сказали: *{text}*", parse_mode="Markdown")
        
        # Обрабатываем запрос через роутер
        response = router.route_voice_request(user_id, str(ogg_path))
        
        # В режиме voice ОБЯЗАТЕЛЬНО отвечаем голосом
        await send_voice_response(update, response)
        
        # Удаляем временный файл
        ogg_path.unlink(missing_ok=True)
        
    except Exception as e:
        logger.error(f"Ошибка обработки голосового: {e}")
        await update.message.reply_text(
            "😔 Не удалось обработать голосовое сообщение. Попробуйте еще раз или напишите текстом."
        )


async def send_voice_response(update: Update, text: str) -> None:
    """Отправляет ответ голосовым сообщением. В режиме voice - ОБЯЗАТЕЛЬНО голосом."""
    import time
    
    user_id = update.message.from_user.id
    
    for attempt in range(3):  # Попытка 3 раза
        try:
            # Генерируем голос сразу в формате OGG для Telegram
            ogg_path = TEMP_AUDIO_DIR / f"response_{user_id}_{int(time.time())}.ogg"
            text_to_speech(text, voice="alloy", output_path=str(ogg_path))
            
            # Отправляем голосовое
            with open(ogg_path, "rb") as voice_file:
                await update.message.reply_voice(voice_file)

            # Удаляем временный файл
            ogg_path.unlink(missing_ok=True)
            return
            
        except Exception as e:
            logger.error(f"Попытка {attempt + 1}: Ошибка генерации голоса: {e}")
            if attempt == 2:  # После 3 неудачных попыток
                # В режиме voice текстовый ответ ЗАПРЕЩЕН
                await update.message.reply_text(
                    "⚠️ Не удалось озвучить ответ. Попробуйте позже."
                )
    

async def voice_mode_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /voice - выбор голоса."""
    user_id = update.message.from_user.id
    
    if not context.args:
        await update.message.reply_text(
            "🎤 **Выбор голоса для ответов**\n\n"
            "Доступные команды:\n"
            "• `/voice alloy` - нейтральный голос\n"
            "• `/voice echo` - мужской голос\n"
            "• `/voice fable` - мягкий голос\n"
            "• `/voice onyx` - глубокий голос\n\n"
            "Текущий режим голоса: alloy",
            parse_mode="Markdown"
        )
        return
    
    voice_name = context.args[0].lower()
    valid_voices = ["alloy", "echo", "fable", "onyx", "verse", "shimmer"]
    
    if voice_name not in valid_voices:
        await update.message.reply_text(
            f"❌ Голос '{voice_name}' недоступен.\n"
            f"Доступные: {', '.join(valid_voices)}"
        )
        return
    
    # Сохраняем выбор голоса
    if "voice_settings" not in context.user_data:
        context.user_data["voice_settings"] = {}
    
    context.user_data["voice_settings"]["voice"] = voice_name
    
    await update.message.reply_text(f"🎤 Голос изменен на: *{voice_name}*", parse_mode="Markdown")
    logger.info(f"Пользователь {user_id} выбрал голос {voice_name}")