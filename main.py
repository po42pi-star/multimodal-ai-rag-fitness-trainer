"""
Главный исполняемый файл.
Инициализирует все компоненты системы и запускает бота.
"""
import os
import sys
import logging
from pathlib import Path

# Добавляем текущую директорию в путь
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


def initialize_rag() -> bool:
    """
    Инициализирует RAG систему при запуске.
    Индексирует все документы из data/fitness_rag_data/
    """
    logger.info("Инициализация RAG системы...")
    
    try:
        from data.fitness_rag import FitnessRAGSystem
        
        data_dir = os.getenv("RAG_DATA_DIR", "data/fitness_rag_data")
        persist_dir = os.getenv("RAG_PERSIST_DIR", "vector_store")
        
        rag = FitnessRAGSystem(persist_dir=persist_dir)
        
        # Загружаем встроенные данные
        rag.load_data(data_dir)
        
        logger.info(f"RAG система готова. Загружено документов: {len(rag.documents)}")
        return True
        
    except Exception as e:
        logger.error(f"Ошибка инициализации RAG: {e}")
        return False


def check_environment() -> bool:
    """Проверяет настройки окружения."""
    logger.info("Проверка окружения...")
    
    required_vars = ["TG_TOKEN", "PROXYAPI_KEY"]
    missing = [var for var in required_vars if not os.getenv(var)]
    
    if missing:
        logger.error(f"Отсутствуют переменные окружения: {', '.join(missing)}")
        logger.error("Создайте файл .env на основе .env.example")
        return False
    
    logger.info("Все необходимые переменные окружения установлены")
    return True


def main():
    """Основная функция запуска."""
    logger.info("=" * 50)
    logger.info("Запуск Fitness Telegram Bot")
    logger.info("=" * 50)
    
    # Проверяем окружение
    if not check_environment():
        sys.exit(1)
    
    # Инициализируем RAG
    if not initialize_rag():
        logger.warning("RAG система не инициализирована, бот будет работать без базы знаний")
    
    # Запускаем бота
    logger.info("Запуск бота...")
    
    try:
        from bot import main as run_bot
        run_bot()
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
