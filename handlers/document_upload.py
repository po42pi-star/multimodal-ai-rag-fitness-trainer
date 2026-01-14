"""
Обработчик загрузки документов в систему RAG.
"""
import os
import logging
from pathlib import Path
from typing import Optional
import json

logger = logging.getLogger(__name__)

# Поддерживаемые форматы файлов
SUPPORTED_FORMATS = {".pdf", ".txt", ".md"}


def load_document(file_path: str) -> Optional[str]:
    """
    Загружает документ и возвращает его текстовое содержимое.
    
    Args:
        file_path: Путь к файлу
    
    Returns:
        str: Текст документа или None при ошибке
    """
    ext = Path(file_path).suffix.lower()
    
    if ext not in SUPPORTED_FORMATS:
        logger.warning(f"Неподдерживаемый формат файла: {ext}")
        return None
    
    try:
        if ext == ".pdf":
            return _load_pdf(file_path)
        elif ext in (".txt", ".md"):
            return _load_text(file_path)
    except Exception as e:
        logger.error(f"Ошибка загрузки документа {file_path}: {e}")
        return None


def _load_text(file_path: str) -> str:
    """Загружает текстовый файл."""
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()


def _load_pdf(file_path: str) -> str:
    """Загружает PDF файл (требует PyPDF2 или pdfplumber)."""
    try:
        import pdfplumber
        
        text = ""
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                text += page.extract_text() + "\n"
        return text
        
    except ImportError:
        logger.warning("Для PDF требуется библиотека pdfplumber")
        # Попробуем альтернативу
        try:
            from PyPDF2 import PdfReader
            
            text = ""
            reader = PdfReader(file_path)
            for page in reader.pages:
                text += page.extract_text() + "\n"
            return text
        except ImportError:
            raise ImportError("Установите pdfplumber или PyPDF2 для работы с PDF")


def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 100) -> list:
    """
    Разбивает текст на чанки для индексации.
    
    Args:
        text: Текст для разбиения
        chunk_size: Максимальный размер чанка
        overlap: Перекрытие между чанками
    
    Returns:
        list: Список чанков текста
    """
    chunks = []
    start = 0
    
    while start < len(text):
        end = start + chunk_size
        
        # Пробуем разрезать по абзацам
        if end < len(text):
            # Ищем конец предложения или абзаца
            while end > start and text[end] not in ".\n":
                end -= 1
            
            # Если не нашли, режем по пробелу
            if end == start:
                end = start + chunk_size
                while end < len(text) and text[end] not in " \n":
                    end += 1
        
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        
        start = end - overlap
        if start >= len(text):
            break
    
    return chunks


def prepare_document_for_indexing(file_path: str) -> dict:
    """
    Подготавливает документ для индексации в векторную базу.
    
    Args:
        file_path: Путь к файлу
    
    Returns:
        dict: Подготовленные данные для индексации
    """
    text = load_document(file_path)
    
    if not text:
        return None
    
    chunks = chunk_text(text)
    
    return {
        "source": str(Path(file_path).resolve()),
        "filename": Path(file_path).name,
        "chunks": chunks,
        "total_chunks": len(chunks)
    }


def index_document(file_path: str, persist_dir: str = "vector_store") -> dict:
    """
    Индексирует документ в векторную базу данных.
    
    Args:
        file_path: Путь к файлу
        persist_dir: Директория для хранения векторной базы
    
    Returns:
        dict: Результат индексации
    """
    from data.fitness_rag import FitnessRAGSystem
    
    prepared = prepare_document_for_indexing(file_path)
    
    if not prepared:
        return {"success": False, "error": "Не удалось загрузить документ"}
    
    try:
        rag = FitnessRAGSystem(persist_dir=persist_dir)
        
        # Добавляем каждый чанк в базу
        for i, chunk in enumerate(prepared["chunks"]):
            rag.add_document(
                text=chunk,
                metadata={
                    "source": prepared["source"],
                    "filename": prepared["filename"],
                    "chunk_id": i
                }
            )
        
        logger.info(f"Документ {prepared['filename']} успешно проиндексирован")
        
        return {
            "success": True,
            "filename": prepared["filename"],
            "chunks_indexed": prepared["total_chunks"]
        }
        
    except Exception as e:
        logger.error(f"Ошибка индексации: {e}")
        return {"success": False, "error": str(e)}


def index_all_documents(data_dir: str = "data/fitness_rag_data", persist_dir: str = "vector_store") -> dict:
    """
    Индексирует все документы из директории.
    
    Args:
        data_dir: Директория с документами
        persist_dir: Директория для хранения векторной базы
    
    Returns:
        dict: Результат индексации
    """
    from data.fitness_rag import FitnessRAGSystem
    
    rag = FitnessRAGSystem(persist_dir=persist_dir)
    
    # Загружаем встроенные данные
    rag.load_data(data_dir)
    
    return {
        "success": True,
        "documents_loaded": len(rag.collections) if rag.collections else 0,
        "collections": list(rag.collections.keys()) if rag.collections else []
    }