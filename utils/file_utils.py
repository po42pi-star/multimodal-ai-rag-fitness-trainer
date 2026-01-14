"""
Утилиты для работы с файлами и логирования.
"""
import os
import sys
import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

# Настройка логирования
def setup_logging(log_level: int = logging.INFO) -> logging.Logger:
    """Настраивает логирование для приложения."""
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # Создаем директорию для логов
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    
    # Настройка хендлеров
    handlers = [
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(
            logs_dir / f"bot_{datetime.now().strftime('%Y%m%d')}.log",
            encoding="utf-8"
        )
    ]
    
    logging.basicConfig(
        level=log_level,
        format=log_format,
        handlers=handlers
    )
    
    logger = logging.getLogger(__name__)
    return logger


def get_temp_dir() -> Path:
    """Возвращает директорию для временных файлов."""
    temp_dir = Path("temp")
    temp_dir.mkdir(exist_ok=True)
    return temp_dir


def save_uploaded_file(file_content: bytes, filename: str, subdir: str = "") -> str:
    """
    Сохраняет загруженный файл.
    
    Args:
        file_content: Содержимое файла
        filename: Имя файла
        subdir: Поддиректория
    
    Returns:
        str: Путь к сохраненному файлу
    """
    if subdir:
        upload_dir = get_temp_dir() / subdir
    else:
        upload_dir = get_temp_dir()
    
    upload_dir.mkdir(exist_ok=True)
    
    # Генерируем уникальное имя файла
    unique_filename = f"{uuid.uuid4().hex[:8]}_{filename}"
    file_path = upload_dir / unique_filename
    
    with open(file_path, "wb") as f:
        f.write(file_content)
    
    return str(file_path)


def cleanup_temp_files(max_age_hours: int = 24) -> int:
    """
    Удаляет временные файлы старше указанного времени.
    
    Args:
        max_age_hours: Максимальный возраст файлов в часах
    
    Returns:
        int: Количество удаленных файлов
    """
    temp_dir = get_temp_dir()
    now = datetime.now()
    deleted = 0
    
    for file_path in temp_dir.rglob("*"):
        if file_path.is_file():
            file_age = datetime.fromtimestamp(file_path.stat().st_mtime)
            age_hours = (now - file_age).total_seconds() / 3600
            
            if age_hours > max_age_hours:
                file_path.unlink()
                deleted += 1
    
    return deleted


def load_json_file(file_path: str) -> dict:
    """Загружает JSON файл."""
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json_file(data: dict, file_path: str) -> None:
    """Сохраняет данные в JSON файл."""
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_user_data_path(user_id: int) -> str:
    """Возвращает путь к файлу данных пользователя."""
    data_dir = Path("user_data")
    data_dir.mkdir(exist_ok=True)
    return str(data_dir / f"user_{user_id}.json")


def load_user_data(user_id: int) -> dict:
    """Загружает данные пользователя."""
    path = get_user_data_path(user_id)
    if os.path.exists(path):
        return load_json_file(path)
    return {}


def save_user_data(user_id: int, data: dict) -> None:
    """Сохраняет данные пользователя."""
    path = get_user_data_path(user_id)
    save_json_file(data, path)