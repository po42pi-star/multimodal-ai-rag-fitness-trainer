"""
Утилита для преобразования голосового сообщения в текст.
"""
import os
import logging
from pathlib import Path
from pydub import AudioSegment

logger = logging.getLogger(__name__)


def convert_ogg_to_wav(ogg_path: str, wav_path: str) -> bool:
    """Конвертирует OGG файл в WAV формат для Whisper."""
    try:
        # Загружаем OGG файл (стандартный формат Telegram)
        audio = AudioSegment.from_ogg(ogg_path)
        
        # Конвертируем в WAV
        audio.export(wav_path, format="wav")
        return True
    except Exception as e:
        logger.error(f"Ошибка конвертации OGG в WAV: {e}")
        return False


def speech_to_text(audio_path: str) -> str:
    """Основная функция для преобразования голоса в текст."""
    from services.openai_client import openai_client
    
    # Проверяем формат файла
    ext = Path(audio_path).suffix.lower()
    
    # Если это OGG, конвертируем в WAV
    if ext == ".ogg":
        wav_path = audio_path.replace(".ogg", ".wav")
        if not convert_ogg_to_wav(audio_path, wav_path):
            return "Ошибка преобразования аудио файла"
        
        audio_path = wav_path
    
    # Транскрибируем
    try:
        text = openai_client.transcribe_audio(audio_path)
        return text
    except Exception as e:
        logger.error(f"Ошибка транскрибации: {e}")
        raise