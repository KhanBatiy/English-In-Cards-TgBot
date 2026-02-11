import logging
import random

from telebot import types
from telebot.states import State, StatesGroup
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

from default_db import Session
from models import User, LearningHistory, Dictionary, Word
from bot_instance import bot
from services import (
    create_words,
    new_user,
    show_hint,
    show_target,
    update_learning_history,
)
from validators import validate_english_word, validate_russian_text

logger = logging.getLogger(__name__)


class StateWords(StatesGroup):
    """
    Состояния для выбора слова
    """

    choose_word = State()
    delete_word = State()
    translate_word = State()
    add_eng_word = State()
    add_rus_word = State()


class Command:
    """
    Названия кнопок
    """

    ADD_WORD = "Добавить слово ➕"
    DELETE_WORD = "Удалить слово🔙"
    NEXT = "Дальше ⏭"


@bot.message_handler(commands=["start"])
def start(message):
    """
    Обработчик команды /start
    Отправляет приветственное сообщение и отображает кнопку 'Тренька!'
    """
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("Тренька!"))
    hello = (
        f"Привет {message.from_user.username}👋 "
        "Давай попрактикуемся в английском языке. "
        "Нажми на кнопку 'Тренька!'"
    )
    bot.send_message(
        message.chat.id, hello, reply_markup=markup,
    )


@bot.message_handler(func=lambda message: message.text == "Тренька!")
def train(message):
    """
    Обработчик кнопки 'Тренька!' - запускает тренировку
    """
    new_user(message)
    pairs = create_words(message)
    if not pairs:
        bot.send_message(
            message.chat.id, "Ошибка: не удалось получить слова для тренировки"
        )
        return

    # Выбираем случайное слово для тренировки
    selected_pair = random.choice(pairs)
    if len(selected_pair) < 3:
        bot.send_message(message.chat.id, "Ошибка: некорректные данные слова")
        return

    # Создаем клавиатуру с вариантами ответов
    markup = types.ReplyKeyboardMarkup(row_width=2)
    buttons = []

    # Добавляем правильный перевод
    target_btn = types.KeyboardButton(selected_pair[0])
    buttons.append(target_btn)

    # Добавляем остальные варианты
    others_btn = [
        types.KeyboardButton(row[0])
        for row in pairs
        if row[0] != selected_pair[0]
    ]
    buttons.extend(others_btn)
    random.shuffle(buttons)

    # Добавляем управляющие кнопки
    next_btn = types.KeyboardButton(Command.NEXT)
    add_word_btn = types.KeyboardButton(Command.ADD_WORD)
    delete_word_btn = types.KeyboardButton(Command.DELETE_WORD)
    buttons.extend([next_btn, add_word_btn, delete_word_btn])
    markup.add(*buttons)

    # Устанавливаем состояние выбора слова
    bot.set_state(
        message.from_user.id,
        StateWords.choose_word,
        message.chat.id,
    )
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        data["choose_word"] = selected_pair[0]
        data["translate_word"] = selected_pair[1]
        data["word_id"] = selected_pair[2]
        data["buttons"] = buttons

    greeting = f"Тогда выбери перевод слова:\n🇷🇺 {selected_pair[1]}"
    bot.send_message(message.chat.id, greeting, reply_markup=markup)


@bot.message_handler(func=lambda message: message.text == Command.NEXT)
def next_cards(message):
    """
    Обработчик кнопки 'Дальше' - запускает тренировку с новым словом
    """
    train(message)


@bot.message_handler(func=lambda message: message.text == Command.DELETE_WORD)
def delete_word(message):
    """
    Обработчик кнопки 'Удалить слово' - запрашивает слово для удаления
    """
    bot.send_message(
        message.chat.id,
        "Введите слово на английском для удаления:",
    )
    bot.set_state(
        message.from_user.id,
        StateWords.delete_word,
        message.chat.id,
    )


@bot.message_handler(state=StateWords.delete_word)
def input_delete_word(message):
    """
    Обработчик удаления слова из базы данных.
    Удаляет слово из таблицы Word (для всех) или из Dictionary
    (добавленные пользователем).
    """
    eng_word = (message.text or "").strip()
    tg_id = message.from_user.id

    ok, err = validate_english_word(eng_word)
    if not ok:
        bot.send_message(message.chat.id, err)
        train(message)
        return

    try:
        bot.delete_state(message.from_user.id, message.chat.id)

        with Session() as session:
            user = session.query(User).filter(User.tg_id == tg_id).first()
            if not user:
                bot.send_message(message.chat.id, "Пользователь не найден!")
                return

            deleted = False

            # Сначала ищем в таблице Word (без учёта регистра)
            word_row = (
                session.query(Word)
                .filter(
                    func.lower(Word.original) == eng_word.lower(),
                )
                .first()
            )
            if word_row:
                session.delete(word_row)
                deleted = True

            # Если не в Word — ищем в словаре пользователя
            if not deleted:
                dict_row = (
                    session.query(Dictionary)
                    .filter(
                        func.lower(Dictionary.added_eng_word)
                        == eng_word.lower(),
                        Dictionary.user_id == user.user_id,
                    )
                    .first()
                )
                if dict_row:
                    session.delete(dict_row)
                    deleted = True

            if deleted:
                session.commit()
                bot.send_message(
                    message.chat.id, f"Слово '{eng_word}' успешно удалено!"
                )
            else:
                bot.send_message(message.chat.id, "Слово не найдено.")

        train(message)
    except SQLAlchemyError as e:
        logger.exception(
            "Ошибка БД при удалении слова (tg_id=%s, слово=%s): %s",
            tg_id, eng_word, e,
        )
        bot.send_message(
            message.chat.id,
            "Произошла ошибка при удалении слова. Попробуйте позже.",
        )
        train(message)
    except Exception as e:
        logger.exception("Неожиданная ошибка в input_delete_word: %s", e)
        bot.send_message(
            message.chat.id,
            "Произошла ошибка при удалении слова.",
        )
        train(message)


@bot.message_handler(commands=["stats"])
def show_stats(message):
    """
    Обработчик команды /stats - показывает статистику пользователей
    """
    try:
        with Session() as session:
            # Получаем топ-3 пользователей по количеству правильных ответов
            stats = (
                session.query(
                    User.username,
                    func.sum(LearningHistory.correct_count).label(
                        "total_correct",
                    ),
                    func.sum(LearningHistory.fail_count).label(
                        "total_errors",
                    ),
                )
                .join(LearningHistory, User.user_id == LearningHistory.user_id)
                .group_by(User.user_id, User.username)
                .having(func.sum(LearningHistory.correct_count) > 0)
                .order_by(
                    func.sum(LearningHistory.correct_count).desc(),
                )
                .limit(3)
                .all()
            )

            if not stats:
                bot.send_message(
                    message.chat.id,
                    "Статистика пока пуста. "
                    "Начните тренироваться, чтобы попасть в рейтинг!",
                )
                return

            # Формируем сообщение со статистикой
            message_text = "ЛИДЕРЫ:\n\n"
            medals = ["🥇", "🥈", "🥉"]

            for idx, (username, total_correct, total_errors) in enumerate(
                stats, 1,
            ):
                medal = medals[idx - 1]
                message_text += (
                    f"{medal} {username}\n"
                    f"   Правильных: {total_correct or 0}\n"
                    f"   Ошибок: {total_errors or 0}\n\n"
                )

            bot.send_message(message.chat.id, message_text)
    except SQLAlchemyError as e:
        logger.exception("Ошибка БД в show_stats: %s", e)
        bot.send_message(
            message.chat.id,
            "Не удалось загрузить статистику. Попробуйте позже.",
        )
    except Exception as e:
        logger.exception("Неожиданная ошибка в show_stats: %s", e)
        bot.send_message(
            message.chat.id,
            "Произошла ошибка при получении статистики.",
        )


@bot.message_handler(func=lambda message: message.text == Command.ADD_WORD)
def add_word(message):
    """
    Обработчик кнопки 'Добавить слово' - запрашивает английское слово
    """
    bot.send_message(message.chat.id, "Введите английское слово:")
    bot.set_state(
        message.from_user.id, StateWords.add_eng_word, message.chat.id,
    )


@bot.message_handler(state=StateWords.add_eng_word)
def get_add_eng_word(message):
    """
    Обработчик ввода английского слова
    """
    text = (message.text or "").strip()
    ok, err = validate_english_word(text)
    if not ok:
        bot.send_message(message.chat.id, err)
        return

    try:
        with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
            data["add_eng_word"] = text
            data["word_id"] = message.from_user.id
        bot.send_message(message.chat.id, "Введите перевод слова:")
        bot.set_state(
            message.from_user.id,
            StateWords.add_rus_word,
            message.chat.id,
        )
    except Exception as e:
        logger.exception(
            "Ошибка при сохранении английского слова (tg_id=%s): %s",
            message.from_user.id, e,
        )
        bot.send_message(
            message.chat.id,
            "Произошла ошибка при сохранении слова. Попробуйте снова.",
        )


@bot.message_handler(state=StateWords.add_rus_word)
def get_add_rus_word(message):
    """
    Обработчик ввода перевода слова - добавляет слово в базу данных
    """
    rus_text = (message.text or "").strip()
    ok, err = validate_russian_text(rus_text)
    if not ok:
        bot.send_message(message.chat.id, err)
        return

    try:
        with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
            eng_word = (data.get("add_eng_word") or "").strip()
            ok_eng, err_eng = validate_english_word(eng_word)
            if not ok_eng:
                bot.send_message(
                    message.chat.id,
                    "Английское слово некорректно. "
                    "Начните заново: кнопка «Добавить слово».",
                )
                bot.delete_state(message.from_user.id, message.chat.id)
                return
            data["add_rus_word"] = rus_text

            with Session() as session:
                user = (
                    session.query(User)
                    .filter(User.tg_id == message.from_user.id)
                    .first()
                )
                if not user:
                    bot.send_message(
                        message.chat.id,
                        "Пользователь не найден в базе данных!",
                    )
                    bot.delete_state(message.from_user.id, message.chat.id)
                    return

                word = Dictionary(
                    user_id=user.user_id,
                    added_eng_word=eng_word,
                    added_rus_word=rus_text,
                )
                session.add(word)
                session.commit()
        bot.send_message(message.chat.id, "Слово успешно добавлено!")
        bot.delete_state(message.from_user.id, message.chat.id)
        train(message)
    except IntegrityError as e:
        logger.warning(
            "Ошибка целостности при добавлении слова (tg_id=%s): %s",
            message.from_user.id, e,
        )
        bot.send_message(
            message.chat.id,
            "Такое слово уже есть в словаре или ошибка данных.",
        )
        bot.delete_state(message.from_user.id, message.chat.id)
    except SQLAlchemyError as e:
        logger.exception(
            "Ошибка БД при добавлении слова (tg_id=%s): %s",
            message.from_user.id, e,
        )
        bot.send_message(
            message.chat.id,
            "Не удалось добавить слово. Попробуйте позже.",
        )
        bot.delete_state(message.from_user.id, message.chat.id)
    except Exception as e:
        logger.exception("Неожиданная ошибка в get_add_rus_word: %s", e)
        bot.send_message(
            message.chat.id,
            "Произошла ошибка при добавлении слова.",
        )
        bot.delete_state(message.from_user.id, message.chat.id)


@bot.message_handler(func=lambda message: True, content_types=["text"])
def message_reply(message):
    """
    Обработчик ответа пользователя
    """
    text = message.text
    # Игнорируем команды, которые обрабатываются отдельно
    if text in [
        Command.NEXT, Command.ADD_WORD, Command.DELETE_WORD, "Тренька!",
    ]:
        return

    # Инициализируем переменные для хранения данных о текущем слове
    choose_word = None
    translate_word = None
    word_id = None
    buttons = []

    # Получаем сохраненные данные о текущем состоянии пользователя
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        choose_word = data.get("choose_word")
        translate_word = data.get("translate_word")
        word_id = data.get("word_id")
        buttons = data.get("buttons", [])

    # Проверяем правильность ответа пользователя
    if text == choose_word:
        # Обработка правильного ответа
        if word_id:
            update_learning_history(
                message.from_user.id, word_id, is_correct=True,
            )
        hint = show_target(
            {"choose_word": choose_word, "translate_word": translate_word}
        )
        hint_text = ["Отлично!❤", hint]
        hint = show_hint(*hint_text)
        bot.send_message(message.chat.id, hint)
    else:
        # Обработка неправильного ответа
        if word_id:
            update_learning_history(
                message.from_user.id, word_id, is_correct=False,
            )
        hint = show_hint(
            "Допущена ошибка!",
            f"Попробуй ещё раз - 🇷🇺{translate_word}",
        )
        # Отправляем сообщение с подсказкой и клавиатурой
        markup = types.ReplyKeyboardMarkup(row_width=2)
        if buttons:
            markup.add(*buttons)
        bot.send_message(message.chat.id, hint, reply_markup=markup)
        return

    # Переход к следующему слову или начало новой тренировки
    if not choose_word:
        train(message)
    else:
        bot.delete_state(message.from_user.id, message.chat.id)
        train(message)
