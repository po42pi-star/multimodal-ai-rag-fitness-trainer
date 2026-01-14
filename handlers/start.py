"""
Обработчик команд: /start, /help, /reset, /stats, /mode
"""
import os
import logging
from typing import Optional

from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ContextTypes

from services.router import router, user_modes, user_data
from utils.file_utils import load_user_data, save_user_data

logger = logging.getLogger(__name__)

# Клавиатура режимов
MODES_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton("/mode text"), KeyboardButton("/mode voice")],
        [KeyboardButton("/mode image"), KeyboardButton("/mode rag")],
        [KeyboardButton("Поехали!")],
    ],
    resize_keyboard=True
)

# Клавиатура действий после прохождения тренировок
WORKOUT_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton("/mode text"), KeyboardButton("/mode voice")],
        [KeyboardButton("/mode image"), KeyboardButton("/mode rag")],
        [KeyboardButton("Получить тренировку")],
        [KeyboardButton("Показать мою карту")],
    ],
    resize_keyboard=True
)

# Клавиатура подтверждения
CONFIRM_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton("/mode text"), KeyboardButton("/mode voice")],
        [KeyboardButton("/mode image"), KeyboardButton("/mode rag")],
        [KeyboardButton("Сохранить")],
        [KeyboardButton("Заполнить заново")],
    ],
    resize_keyboard=True
)


def get_welcome_message(current_mode: str = "text") -> str:
    """Возвращает приветственное сообщение с указанием текущего режима."""
    mode_indicator = {
        "text": "📝",
        "voice": "🎤",
        "image": "📸",
        "rag": "📚"
    }
    icon = mode_indicator.get(current_mode, "📝")
    
    mode_names = {
        "text": "текстовый",
        "voice": "голосовой",
        "image": "анализ фото",
        "rag": "база тренировок"
    }
    
    return f"""
🏋️ **Привет! Я твой персональный фитнес-тренер для улучшения физической формы с тренировками каждый день!**

{icon} **Текущий режим:** {mode_names.get(current_mode, current_mode)}

📝 **Текстовые запросы** - спрашивай что угодно
🎤 **Голосовые сообщения** - транскрибация голоса и синтез речи
📸 **Изображения** - режим анализа блюд и генерации схем упражнений
📚 **База тренировок (RAG)** - отправь день тренировки, получишь упражнения

🔑 **Основные команды:**
/start - перезапуск
/help - список команд
/reset - очистка истории
/text - текстовый режим
/voice - голосовой режим
/image - режим фото
/rag - база тренировок

🔽 Нажми **"Поехали!"** для начала тренировки!
"""


def get_help_message(current_mode: str = "text") -> str:
    """Возвращает сообщение помощи с указанием текущего режима."""
    mode_indicator = {
        "text": "📝",
        "voice": "🎤",
        "image": "📸",
        "rag": "📚"
    }
    icon = mode_indicator.get(current_mode, "📝")
    
    mode_names = {
        "text": "текстовый",
        "voice": "голосовой",
        "image": "анализ фото",
        "rag": "база тренировок"
    }
    
    return f"""
🏋️ **Помощь по боту** {icon} ({mode_names.get(current_mode, current_mode)})

📝 **Текстовые запросы** - спроси что угодно о тренировках
🎤 **Голосовые сообщения** - транскрибация голоса и синтез речи
📸 **Изображения** - фото блюда → калории и БЖУ / вопрос по упражнениям → схема
📚 **База тренировок (RAG)** - напиши день (например "3 день") → упражнения

🔑 **Команды:**
/start - перезапуск
/help - это сообщение
/reset - очистка истории
/text - текстовый режим
/voice - голосовой режим
/image - режим анализа блюд и генерации схем упражнений
/rag - база тренировок

🔽 Нажми **"Поехали!"** для начала тренировки!
"""


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /start."""
    user_id = update.message.from_user.id
    
    # Сбрасываем данные пользователя
    user_modes[user_id] = "text"
    
    await update.message.reply_text(
        get_welcome_message(current_mode="text"),
        reply_markup=MODES_KEYBOARD,
        parse_mode="Markdown"
    )
    
    logger.info(f"Пользователь {user_id} запустил бота")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /help."""
    user_id = update.message.from_user.id
    current_mode = user_modes.get(user_id, "text")
    
    await update.message.reply_text(
        get_help_message(current_mode=current_mode),
        parse_mode="Markdown"
    )
    

async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /reset - очищает историю и профиль."""
    user_id = update.message.from_user.id
    
    # Удаляем файл данных пользователя
    from utils.file_utils import get_user_data_path
    user_data_path = get_user_data_path(user_id)
    if os.path.exists(user_data_path):
        os.remove(user_data_path)
        logger.info(f"Файл данных удален: {user_data_path}")
    
    # Очищаем данные из памяти
    if user_id in user_data:
        del user_data[user_id]
    if user_id in user_modes:
        user_modes[user_id] = "text"
    
    await update.message.reply_text(
        "🔄 История и профиль очищены. Начнем сначала!\n\nНажми **/start** для перезапуска.",
        parse_mode="Markdown"
    )
    
    logger.info(f"Пользователь {user_id} сбросил данные")


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /stats - показывает статус базы знаний."""
    try:
        rag = router.get_rag_system()
        collections_info = []
        
        if rag.collections:
            for name, collection in rag.collections.items():
                count = collection.count()
                collections_info.append(f"  • {name}: {count} документов")
        else:
            collections_info.append("  • Коллекции еще не созданы")
        
        persist_dir = rag.persist_dir if hasattr(rag, 'persist_dir') else "vector_store"
        
        message = f"""
📊 **Статус базы знаний:**

📁 Директория: `{persist_dir}`
✅ База готова к использованию

**Коллекции:**
{chr(10).join(collections_info) if collections_info else "  • Нет данных"}

💡 Для работы с базой переключитесь в режим: `/mode rag`
"""
        await update.message.reply_text(message, parse_mode="Markdown")
        
    except Exception as e:
        await update.message.reply_text(
            f"⚠️ Ошибка получения статуса: {e}",
            parse_mode="Markdown"
        )


async def mode_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /mode - переключение режимов."""
    user_id = update.message.from_user.id
    
    if not context.args:
        # Показываем текущий режим
        current_mode = user_modes.get(user_id, "text")
        mode_descriptions = {
            "text": "📝 Текстовый режим - бот отвечает текстом",
            "voice": "🎤 Голосовой режим - бот отвечает голосом",
            "image": "📸 Режим изображений - анализ фото еды",
            "rag": "📚 Режим RAG - поиск по базе тренировок"
        }
        
        await update.message.reply_text(
            f"Текущий режим: **{current_mode.upper()}**\n\n"
            f"{mode_descriptions.get(current_mode, '')}\n\n"
            "Выберите режим:\n"
            "• `/mode text` - текст\n"
            "• `/mode voice` - голос\n"
            "• `/mode image` - фото\n"
            "• `/mode rag` - база тренировок",
            parse_mode="Markdown"
        )
        return
    
    # Переключаем режим
    new_mode = context.args[0].lower()
    
    if new_mode not in ["text", "voice", "image", "rag"]:
        await update.message.reply_text(
            "❌ Неизвестный режим. Доступные: text, voice, image, rag"
        )
        return
    
    user_modes[user_id] = new_mode
    
    mode_messages = {
        "text": "📝 Переключен в текстовый режим",
        "voice": "🎤 Переключен в голосовой режим",
        "image": "📸 Переключен в режим изображений",
        "rag": "📚 Переключен в режим RAG"
    }
    
    await update.message.reply_text(mode_messages[new_mode])
    logger.info(f"Пользователь {user_id} переключился на режим {new_mode}")


async def index_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /index - переиндексация базы знаний."""
    await update.message.reply_text("🔄 Переиндексация базы знаний...")
    
    try:
        # Создаем новую RAG систему (она автоматически загрузит данные)
        router._rag_system = None  # Сбрасываем кэш
        rag = router.get_rag_system()
        
        status = rag.get_status()
        
        message = f"✅ **База знаний обновлена!**\n\n"
        message += f"📄 Документов: {status['documents_count']}\n"
        
        for name, info in status['collections'].items():
            count = info.get('count', 0)
            message += f"  • {name}: {count}\n"
        
        await update.message.reply_text(message, parse_mode="Markdown")
        logger.info(f"Пользователь {update.message.from_user.id} обновил RAG")
        
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")
        logger.error(f"Ошибка индексации RAG: {e}")


async def rag_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /rag - объяснение работы с базой тренировок."""
    user_id = update.message.from_user.id
    current_mode = user_modes.get(user_id, "text")
    
    message = """
📚 **База тренировок (RAG)**

Это твоя персональная библиотека упражнений! 

**Как работает:**
1. Переключись в режим RAG: **/mode rag**
2. Напиши номер дня (1-28) или неделю (1 неделя, 2 неделя...)
3. Получишь подробный план упражнений с:
   • Списком упражнений
   • Количеством подходов и повторений
   • Поясняющими изображениями

**Примеры запросов:**
• "1 день" - первая тренировка
• "День 7" - последний день первой недели
• "2 неделя" - все дни второй недели
• "тренировка на грудь" - поиск по типу тренировки

**После заполнения профиля (/start → Поехали!)**
Бот будет генерировать персонализированные тренировки с учётом твоего уровня, цели и ограничений!

🔽 Переключиться: **/mode rag**
"""
    
    await update.message.reply_text(message, parse_mode="Markdown")


async def poehali_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик кнопки 'Поехали!' - начало заполнения профиля."""
    user_id = update.message.from_user.id
    
    # Инициализируем данные пользователя с состоянием сбора профиля
    user_data[user_id] = {
        "profile_state": "collecting",
        "profile_complete": False,
        "workout_day": 0,
        "current_week": 0,
        "workouts_completed": [],
        "fields": {}
    }
    
    prompt = """
🏃 **Давай создадим твою персональную карту тренировок!**

Пожалуйста, сообщи следующие данные (можно голосом 📝):

1. **Возраст** - сколько полных лет
2. **Пол** - мужской/женский
3. **Рост** - в сантиметрах
4. **Вес** - в килограммах
5. **Уровень активности:**
   • 1 - сидячий образ жизни
   • 2 - легкая активность (1-3 раза в неделю)
   • 3 - средняя активность (3-5 раз в неделю)
   • 4 - высокая активность (6-7 раз в неделю)
6. **Ограничения** - если есть (больная спина, проблемы с суставами и т.д.), иначе "нет"
7. **Цель:**
   • набор массы
   • похудение
   • поддержание формы

⏱️ Пример: "Мне 30 лет, рост 180, вес 80, уровень активности 3, ограничений нет, цель - набор массы"

Или просто ответь на вопросы по порядку! 🎯
"""
    
    await update.message.reply_text(prompt, parse_mode="Markdown")

    logger.info(f"Пользователь {user_id} начал заполнение профиля")


async def save_profile_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик кнопки 'Сохранить' - сохранение профиля."""
    user_id = update.message.from_user.id
    
    if user_id not in user_data or not user_data[user_id].get("profile_complete"):
        await update.message.reply_text("❌ Профиль не заполнен. Нажмите 'Поехали!'")
        return
    
    profile = user_data[user_id]
    
    # Формируем карту пользователя
    profile_text = f"""
✅ **Твоя карта тренировок сохранена!**

📋 **Профиль:**
• Возраст: {profile.get('age', 'не указан')} лет
• Пол: {profile.get('gender', 'не указан')}
• Рост: {profile.get('height', 'не указан')} см
• Вес: {profile.get('weight', 'не указан')} кг
• Уровень активности: {profile.get('activity_level', 'не указан')}
• Ограничения: {profile.get('limitations', 'нет')}
• Цель: {profile.get('goal', 'не указана')}

📅 План: 4 недели по 7 дней = 28 тренировок

💡 Сохрани это сообщение или карту, чтобы не потерять!

🔽 Нажми **"Получить тренировку"** чтобы начать!
"""
    
    await update.message.reply_text(
        profile_text,
        reply_markup=WORKOUT_KEYBOARD,
        parse_mode="Markdown"
    )