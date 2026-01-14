"""
Клиент для взаимодействия с API OpenAI через ProxyAPI.
"""
import os
import base64
import logging
from typing import Optional
from openai import OpenAI
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

load_dotenv()


class OpenAIClient:
    """Клиент для работы с OpenAI API через ProxyAPI."""
    
    def __init__(self):
        self.base_url = os.getenv("OPENAI_BASE_URL", "https://api.proxyapi.ru/openai/v1")
        self.api_key = os.getenv("PROXYAPI_KEY")
        
        if not self.api_key:
            raise ValueError("PROXYAPI_KEY не установлен в .env файле")
        
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )
    
    def get_text_model(self) -> str:
        """Возвращает имя модели для текста."""
        return os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    
    def get_vision_model(self) -> str:
        """Возвращает имя модели для vision."""
        return os.getenv("OPENAI_VISION_MODEL", "gpt-4o-mini")
    
    def get_tts_model(self) -> str:
        """Возвращает имя модели для TTS."""
        return os.getenv("OPENAI_TTS_MODEL", "tts-1")
    
    def get_whisper_model(self) -> str:
        """Возвращает имя модели для Whisper."""
        return os.getenv("OPENAI_WHISPER_MODEL", "whisper-1")
    
    def get_image_model(self) -> str:
        """Возвращает имя модели для генерации изображений."""
        return os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-1")
    
    def chat_completion(
        self,
        messages: list,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000
    ) -> str:
        """Отправляет запрос на генерацию текста."""
        if model is None:
            model = self.get_text_model()
        
        response = self.client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )
        return response.choices[0].message.content
    
    def transcribe_audio(self, audio_path: str) -> str:
        """Преобразует аудио в текст с помощью Whisper."""
        with open(audio_path, "rb") as audio_file:
            response = self.client.audio.transcriptions.create(
                model=self.get_whisper_model(),
                file=audio_file
            )
        return response.text
    
    def text_to_speech(
        self,
        text: str,
        voice: str = "alloy",
        format: str = "opus",
        instructions: str = ""
    ) -> bytes:
        """Преобразует текст в речь."""
        model = self.get_tts_model()
        logger.info(f"TTS: модель={model}, voice={voice}, text_len={len(text)}")
        
        try:
            # НЕстриминговый API
            kwargs = {
                "model": model,
                "voice": voice,
                "input": text[:4000],
                "response_format": format
            }
            
            if model == "gpt-4o-mini-tts" and instructions:
                kwargs["instructions"] = instructions
            
            logger.info(f"TTS: создаем запрос к API...")
            response = self.client.audio.speech.create(**kwargs)
            audio_content = response.content
            logger.info(f"TTS: получено {len(audio_content)} байт")
            return audio_content
            
        except Exception as e:
            logger.error(f"TTS: ошибка API: {e}")
            
            # Fallback на tts-1
            try:
                logger.info("TTS: пробуем fallback на tts-1...")
                response = self.client.audio.speech.create(
                    model="tts-1",
                    voice=voice,
                    input=text[:4000],
                    response_format=format
                )
                audio_content = response.content
                logger.info(f"TTS fallback: получено {len(audio_content)} байт")
                return audio_content
            except Exception as e2:
                logger.error(f"TTS fallback ошибка: {e2}")
                raise
    
    def analyze_image(self, image_path: str, prompt: str = "Опиши что на картинке") -> str:
        """Анализирует изображение с помощью Vision модели."""
        with open(image_path, "rb") as image_file:
            base64_image = base64.b64encode(image_file.read()).decode("utf-8")
        
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}"
                        }
                    }
                ]
            }
        ]
        
        response = self.client.chat.completions.create(
            model=self.get_vision_model(),
            messages=messages,
            max_tokens=500
        )
        return response.choices[0].message.content
    
    def generate_image(self, prompt: str, size: str = "1024x1024") -> Optional[str]:
        """Генерирует изображение по текстовому описанию."""
        try:
            model = self.get_image_model()
            logger.info(f"Image generation: model={model}, prompt_len={len(prompt)}")
            
            response = self.client.images.generate(
                model=model,
                prompt=prompt,
                size=size,
                n=1
            )
            
            logger.info(f"Image response: {response}")
            
            # gpt-image-1 возвращает base64, DALL-E возвращает url
            if hasattr(response.data[0], 'b64_json') and response.data[0].b64_json:
                logger.info("Image format: base64")
                return f"data:image/png;base64,{response.data[0].b64_json}"
            
            if hasattr(response.data[0], 'url') and response.data[0].url:
                logger.info("Image format: url")
                return response.data[0].url
            
            logger.error(f"Unknown image response format: {response.data[0]}")
            return None
            
        except Exception as e:
            logger.error(f"Image generation error: {e}", exc_info=True)
            return None


# Глобальный экземпляр клиента
openai_client = OpenAIClient()