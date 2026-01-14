"""
Главный файл Telegram-бота.
"""
import os
import sys
import logging
from pathlib import Path
from typing import Optional

from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)

from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Импорт обработчиков
from handlers.start import (
    start, help_command, reset_command, stats_command, mode_command,
    save_profile_handler, rag_command, index_command
)
from handlers.text import handle_text
from handlers.voice import handle_voice, voice_mode_handler
from handlers.image import handle_image
from handlers.image_generation import handle_image_generation
from handlers.rag import handle_rag_query
from services.router import user_modes, user_data
from utils.file_utils import setup_logging, get_temp_dir

# Клавиатуры
MODES_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton("/mode text"), KeyboardButton("/mode voice")],
        [KeyboardButton("/mode image"), KeyboardButton("/mode rag")],
        [KeyboardButton("Поехали!")],
    ],
    resize_keyboard=True
)

WORKOUT_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton("Получить тренировку")],
        [KeyboardButton("Показать мою карту")],
    ],
    resize_keyboard=True
)

AFTER_SAVE_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton("Получить 1-ую тренировку")],
        [KeyboardButton("Показать мою карту")],
    ],
    resize_keyboard=True
)

WORKOUT_DONE_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton("Я закончил тренировку")],
    ],
    resize_keyboard=True
)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Глобальный обработчик ошибок."""
    logger.error(f"Exception while handling an update: {context.error}")


async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик неизвестных команд."""
    await update.message.reply_text(
        "🤔 Я не понимаю эту команду. Нажмите /help для списка команд."
    )


async def wake_up(application: Application) -> None:
    """Выполняется при запуске бота."""
    logger.info("Бот запускается...")
    
    # Создаем необходимые директории
    get_temp_dir()
    
    # Инициализируем RAG систему для проверки
    try:
        from services.router import router
        rag = router.get_rag_system()
        logger.info("RAG система инициализирована")
    except Exception as e:
        logger.warning(f"Не удалось инициализировать RAG: {e}")


def main() -> None:
    """Запуск бота."""
    # Токен бота
    token = os.getenv("TG_TOKEN")
    
    if not token:
        logger.error("TG_TOKEN не найден в .env файле!")
        sys.exit(1)
    
    # Создаем приложение
    application = Application.builder().token(token).build()
    
    # Выполняем инициализацию
    application.post_init = wake_up
    
    # === Команды ===
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("reset", reset_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("mode", mode_command))
    application.add_handler(CommandHandler("voice", voice_mode_handler))
    application.add_handler(CommandHandler("rag", rag_command))
    application.add_handler(CommandHandler("index", index_command))
    
    # === Текстовые сообщения ===
    text_handler = MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text)
    application.add_handler(text_handler)
    
    # === Голосовые сообщения ===
    voice_handler = MessageHandler(filters.VOICE, handle_voice)
    application.add_handler(voice_handler)
    
    # === Изображения ===
    image_handler = MessageHandler(filters.PHOTO, handle_image)
    application.add_handler(image_handler)
    
    # === Документы ===
    doc_handler = MessageHandler(filters.Document.ALL, handle_document)
    application.add_handler(doc_handler)
    
    # === Неизвестные команды ===
    application.add_handler(MessageHandler(filters.COMMAND, unknown_command))
    
    # === Ошибки ===
    application.add_error_handler(error_handler)
    
    # Запуск бота
    logger.info("Запуск бота...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает загрузку документов (для RAG)."""
    user_id = update.message.from_user.id
    
    # Проверяем, что файл в поддерживаемом формате
    document = update.message.document
    ext = Path(document.file_name).suffix.lower()
    
    supported_formats = {".pdf", ".txt", ".md"}
    
    if ext not in supported_formats:
        await update.message.reply_text(
            f"❌ Формат {ext} не поддерживается.\n"
            "Поддерживаемые форматы: PDF, TXT, MD"
        )
        return
    
    try:
        # Скачиваем документ
        file = await context.bot.get_file(document.file_id)
        file_path = f"temp/{user_id}_{document.file_name}"
        await file.download_to_drive(file_path)
        
        await update.message.reply_text("📄 Документ загружен. Обрабатываю...")
        
        # Индексируем документ
        from handlers.document_upload import index_document
        result = index_document(file_path)
        
        if result.get("success"):
            await update.message.reply_text(
                f"✅ Документ проиндексирован!\n"
                f"📄 Файл: {result['filename']}\n"
                f"📊 Чанков: {result['chunks_indexed']}"
            )
        else:
            await update.message.reply_text(
                f"❌ Ошибка индексации: {result.get('error', 'Неизвестная ошибка')}"
            )
        
        # Удаляем временный файл
        os.remove(file_path)
        
    except Exception as e:
        logger.error(f"Ошибка обработки документа: {e}")
        await update.message.reply_text("😔 Ошибка при обработке документа")


if __name__ == "__main__":
    main()