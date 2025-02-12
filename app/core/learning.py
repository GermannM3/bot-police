import logging
from datetime import datetime
import json
import os

logger = logging.getLogger(__name__)

TRAINING_DATA_FILE = "training_data.json"

def log_flagged_message(user_id: int, chat_id: int, text: str) -> None:
    """
    Логирует сообщение, которое было определено как подозрительное.
    Эти данные можно использовать для последующего обучения модели.
    """
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "user_id": user_id,
        "chat_id": chat_id,
        "text": text,
        "feedback": None  # Пока нет обратной связи
    }
    logger.info(f"FLAGGED MESSAGE: {log_entry}")
    _append_training_data(log_entry)

def log_feedback(admin_id: int, chat_id: int, feedback: str, original_text: str) -> None:
    """
    Логирует обратную связь (лайк/дизлайк) от администратора или модератора.
    В дальнейшем эти данные помогут дообучить модель.
    """
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "admin_id": admin_id,
        "chat_id": chat_id,
        "feedback": feedback,
        "original_text": original_text
    }
    logger.info(f"FEEDBACK: {log_entry}")
    _append_training_data(log_entry)

def _append_training_data(entry: dict) -> None:
    """
    Добавляет запись в обучающий файл. Для демонстрации используется локальный JSON-файл.
    Реальная система должна сохранять данные в базу данных или на сервер.
    """
    data = []
    if os.path.exists(TRAINING_DATA_FILE):
        try:
            with open(TRAINING_DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as ex:
            logger.error(f"Ошибка при загрузке обучающих данных: {ex}")
    data.append(entry)
    try:
        with open(TRAINING_DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as ex:
        logger.error(f"Ошибка при сохранении обучающих данных: {ex}")
