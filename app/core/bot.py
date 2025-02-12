import datetime
import random
import difflib
import logging
from telegram.ext import (
    Application,
    MessageHandler,
    CommandHandler,
    CallbackQueryHandler,
    filters,
)
from telegram import Update, ChatPermissions, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from app.core.nlp import NLPProcessor
from app.core.learning import log_flagged_message, log_feedback
from app.config import Config

logger = logging.getLogger(__name__)

# Список скороговорок для прохождения теста на трезвость.
TONGUE_TWISTERS = [
    "Карл у Клары украл кораллы, а Клара у Карла украла кларнет",
    "Шла Саша по шоссе и сосала сушку",
    "От топота копыт пыль по полю летит",
    "Как утром, так и вечером – все повторится снова",
    "На дворе трава, на траве дрова"
]

COOLDOWN_SECONDS = 300  # Интервал между предупреждениями
SIMILARITY_THRESHOLD = 0.8  # Минимальная схожесть ответа скороговорке
MUTE_TIME_SECONDS = 300     # Время мута (5 минут)

class PoliceBot:
    def __init__(self):
        self.nlp = NLPProcessor()
        # Отслеживаем время последнего предупреждения для каждого пользователя и в каждом чате.
        self.last_warning = {}
        self.last_chat_warning = {}
        # Состояния ожидания теста: ключ – (chat_id, user_id), значение – dict с ожидаемой скороговоркой и временем выдачи.
        self.pending_tests = {}

    async def create_app(self) -> Application:
        app = Application.builder().token(Config.TELEGRAM_TOKEN).build()
        app.add_handler(CommandHandler("start", self.handle_start))
        app.add_handler(MessageHandler(filters.VOICE, self.handle_voice))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text))
        # Обработка callback query для скрытой обратной связи
        app.add_handler(CallbackQueryHandler(self.handle_feedback_callback))
        return app

    async def handle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        message = update.effective_message
        if not message:
            return
        await message.reply_text("Бот активен. Отправьте текст или голосовое сообщение для проверки.")

    async def transcribe_voice(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
        """
        Заглушка для распознавания речи. Здесь можно реализовать интеграцию с сервисом Speech-to-Text.
        """
        message = update.effective_message
        if not message or not message.voice:
            logger.debug("Голосовое сообщение не найдено для транскрипции.")
            return ""
        try:
            voice = message.voice
            file = await context.bot.get_file(voice.file_id)
            file_bytes = await file.download_as_bytearray()
            # Здесь можно вызвать сервис распознавания речи и вернуть транскрипцию.
            transcription = "фактическая транскрипция голосового сообщения"
            logger.info(f"Получена транскрипция: {transcription}")
            return transcription
        except Exception as ex:
            logger.error(f"Ошибка при распознавании голосового сообщения: {ex}")
            return ""

    async def should_warn(self, user_id: int, chat_id: int) -> bool:
        """
        Проверяет, отправлялось ли для данного пользователя или чата предупреждение недавно.
        """
        now = datetime.datetime.now()
        user_warned = (user_id in self.last_warning and
                       (now - self.last_warning[user_id]).total_seconds() < COOLDOWN_SECONDS)
        chat_warned = (chat_id in self.last_chat_warning and
                       (now - self.last_chat_warning[chat_id]).total_seconds() < COOLDOWN_SECONDS)
        return not (user_warned or chat_warned)

    async def update_warning_timestamps(self, user_id: int, chat_id: int) -> None:
        now = datetime.datetime.now()
        self.last_warning[user_id] = now
        self.last_chat_warning[chat_id] = now

    def build_feedback_keyboard(self, chat_id: int, user_id: int) -> InlineKeyboardMarkup:
        """
        Создает inline-клавиатуру для скрытой обратной связи:
        lhs: 👍 (лайк), rhs: 👎 (дизлайк).
        Callback data содержит тип обратной связи, chat_id и user_id.
        """
        keyboard = [
            [
                InlineKeyboardButton("👍", callback_data=f"like|{chat_id}|{user_id}"),
                InlineKeyboardButton("👎", callback_data=f"dislike|{chat_id}|{user_id}")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    async def issue_test(self, chat_id: int, user_id: int, message, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Выдает тест на трезвость с выбранной случайной скороговоркой и прикрепляет inline-клавиатуру для обратной связи.
        Сохраняет состояние теста для последующей проверки ответа.
        """
        tongue_twister = random.choice(TONGUE_TWISTERS)
        self.pending_tests[(chat_id, user_id)] = {
            "expected": tongue_twister,
            "timestamp": datetime.datetime.now()
        }
        response = (
            f"Ваше сообщение вызывает подозрение. Пожалуйста, пройдите тест на трезвость:\n\n"
            f"произнесите скороговорку: '{tongue_twister}'"
        )
        await self.update_warning_timestamps(user_id, chat_id)
        try:
            await message.reply_text(response, reply_markup=self.build_feedback_keyboard(chat_id, user_id))
        except Exception as e:
            logger.error(f"Ошибка при отправке предупреждения: {e}")

    async def mute_user(self, chat_id: int, user_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Пытается наложить мут на пользователя (если чат является супергруппой и пользователь не является владельцем).
        """
        chat = await context.bot.get_chat(chat_id)
        if chat.type != "supergroup":
            logger.error("Нельзя применить мут: чат не является супергруппой.")
            return
        member = await context.bot.get_chat_member(chat_id, user_id)
        if member.status == "creator":
            logger.error("Нельзя применить мут: пользователь является владельцем чата.")
            return
        try:
            until_date = int((datetime.datetime.now() + datetime.timedelta(seconds=MUTE_TIME_SECONDS)).timestamp())
            await context.bot.restrict_chat_member(
                chat_id=chat_id,
                user_id=user_id,
                permissions=ChatPermissions(can_send_messages=False),
                until_date=until_date
            )
            logger.info(f"Мут наложен на пользователя {user_id} в чате {chat_id} до {until_date}.")
        except Exception as e:
            logger.error(f"Ошибка при применении мута: {e}")

    async def handle_feedback_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Обработка callback query с обратной связью.
        Callback data имеет формат: "feedbackType|chat_id|user_id".
        Обратная связь логируется, а ответ на callback отправляется приватно администратору.
        """
        query = update.callback_query
        await query.answer()  # Ответ без показа уведомления в чате
        data = query.data.split("|")
        if len(data) != 3:
            logger.error("Неверный формат callback data.")
            return
        feedback_type, chat_id, user_id = data
        chat_id = int(chat_id)
        user_id = int(user_id)
        # Получаем текст оригинального предупреждения, на которое ответили
        if query.message and query.message.reply_to_message:
            original_text = query.message.reply_to_message.text
        else:
            original_text = "Нет данных об оригинальном сообщении."
        log_feedback(query.from_user.id, chat_id, feedback_type, original_text)
        # Отправляем приватный ответ админу
        await query.answer(text="Обратная связь сохранена.", show_alert=False)

    async def handle_voice(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        message = update.effective_message
        if not message:
            return
        user = update.effective_user
        chat = update.effective_chat
        if not user or not chat:
            return

        user_id = user.id
        chat_id = chat.id

        # Если существует активный тест для пользователя — обрабатываем голос как ответ.
        if (chat_id, user_id) in self.pending_tests:
            transcription = await self.transcribe_voice(update, context)
            if not transcription:
                logger.debug("Пустая транскрипция голосового сообщения; пропускаем анализ.")
                return
            expected = self.pending_tests[(chat_id, user_id)]["expected"]
            similarity = difflib.SequenceMatcher(None, transcription.lower(), expected.lower()).ratio()
            if similarity >= SIMILARITY_THRESHOLD:
                try:
                    await message.reply_text("Тест успешно пройден. Вы выглядите трезвыми!")
                except Exception as e:
                    logger.error(f"Ошибка при отправке подтверждения: {e}")
                del self.pending_tests[(chat_id, user_id)]
            else:
                try:
                    await message.reply_text("Ответ неверный. Вы получаете мут на 5 минут.")
                    await self.mute_user(chat_id, user_id, context)
                except Exception as e:
                    logger.error(f"Ошибка при попытке наложить мут: {e}")
                del self.pending_tests[(chat_id, user_id)]
            return

        # Если нет активного теста, обрабатываем голосовое сообщение обычным образом.
        transcription = await self.transcribe_voice(update, context)
        if transcription:
            needs_test = await self.nlp.analyze(transcription)
            if needs_test:
                log_flagged_message(user_id, chat_id, transcription)
                await self.issue_test(chat_id, user_id, message, context)
            else:
                logger.debug("Голосовое сообщение не требует предупреждения (анализ транскрипции).")
        else:
            logger.debug("Не удалось получить транскрипцию голосового сообщения.")

    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        message = update.effective_message
        if not message or not message.text:
            return

        user = update.effective_user
        chat = update.effective_chat
        if not user or not chat:
            return

        user_id = user.id
        chat_id = chat.id
        text = message.text.strip()

        # Если пользователь ожидает тест, проверяем ответ.
        if (chat_id, user_id) in self.pending_tests:
            expected = self.pending_tests[(chat_id, user_id)]["expected"]
            similarity = difflib.SequenceMatcher(None, text.lower(), expected.lower()).ratio()
            if similarity >= SIMILARITY_THRESHOLD:
                try:
                    await message.reply_text("Тест успешно пройден. Вы выглядите трезвыми!")
                except Exception as e:
                    logger.error(f"Ошибка при отправке подтверждения: {e}")
                del self.pending_tests[(chat_id, user_id)]
            else:
                try:
                    await message.reply_text("Ответ неверный. Вы получаете мут на 5 минут.")
                    await self.mute_user(chat_id, user_id, context)
                except Exception as e:
                    logger.error(f"Ошибка при попытке наложить мут: {e}")
                del self.pending_tests[(chat_id, user_id)]
            return

        # Если нет активного теста, анализируем текстовое сообщение обычным образом.
        if not await self.should_warn(user_id, chat_id):
            logger.debug(f"Кулдаун активен для пользователя {user_id} или чата {chat_id}.")
            return

        needs_test = await self.nlp.analyze(text)
        if needs_test:
            log_flagged_message(user_id, chat_id, text)
            await self.issue_test(chat_id, user_id, message, context)
        else:
            logger.debug("Текстовое сообщение не требует предупреждения.")
