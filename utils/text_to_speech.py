"""
Утилита для преобразования текста в речь (TTS).
"""
import os
import logging
import subprocess
from typing import Optional

logger = logging.getLogger(__name__)


def text_to_speech(
    text: str,
    voice: str = "alloy",
    output_path: Optional[str] = None
) -> bytes:
    """
    Преобразует текст в голосовое сообщение.
    
    Args:
        text: Текст для озвучки
        voice: Голос для синтеза
        output_path: Путь для сохранения файла (опционально)
    
    Returns:
        bytes: Аудио данные в формате OGG (для Telegram)
    """
    from services.openai_client import openai_client
    
    try:
        # OpenAI TTS возвращает сырой opus
        audio_content = openai_client.text_to_speech(
            text=text,
            voice=voice,
            format="opus"  # Сырой opus от OpenAI
        )
        
        # Если указан путь, конвертируем в OGG для Telegram
        if output_path:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Если нужно сохранить - конвертируем в OGG
            temp_opus_path = output_path.replace('.ogg', '.opus')
            with open(temp_opus_path, "wb") as f:
                f.write(audio_content)
            
            # Конвертируем в OGG для Telegram
            _convert_opus_to_ogg(temp_opus_path, output_path)
            
            # Удаляем временный opus
            if os.path.exists(temp_opus_path):
                os.remove(temp_opus_path)
            
            logger.info(f"Аудио сохранено: {output_path}")
            return open(output_path, "rb").read() if os.path.exists(output_path) else audio_content
        
        return audio_content
        
    except Exception as e:
        logger.error(f"Ошибка синтеза речи: {e}")
        raise


def _convert_opus_to_ogg(input_path: str, output_path: str) -> None:
    """Конвертирует сырой OPUS в OGG-контейнер для Telegram."""
    try:
        # Используем ffmpeg для конвертации
        subprocess.run([
            'ffmpeg', '-y', '-f', 'opus', '-acodec', 'libopus',
            '-i', input_path, '-c:a', 'libopus', output_path
        ], capture_output=True, check=True)
        logger.info(f"Конвертация в OGG: {output_path}")
    except subprocess.CalledProcessError as e:
        logger.error(f"Ошибка ffmpeg: {e}")
        # Если ffmpeg недоступен, просто переименовываем
        if os.path.exists(input_path):
            os.rename(input_path, output_path)


def get_voice_for_language(language: str = "ru") -> str:
    """
    Возвращает подходящий голос для языка.
    
    Args:
        language: Код языка (ru, en, etc.)
    
    Returns:
        str: Имя голоса
    """
    voices = {
        "ru": "alloy",  # Для русского используем alloy как нейтральный голос
        "en": "alloy",
        "es": "echo",
        "fr": "fable",
        "de": "verse"
    }
    
    return voices.get(language, "alloy")