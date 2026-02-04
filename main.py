from telebot import TeleBot, types, custom_filters
from telebot.storage import StateMemoryStorage
from telebot.states import State, StatesGroup
from sqlalchemy import func
import random

from config import config
from database import Session
from models import Word, User, UserWord, LearningHistory, Dictionary


storage = StateMemoryStorage()
bot = TeleBot(config.BOT_TOKEN, state_storage=storage)


class StateWords(StatesGroup):
    """
    Состояния для выбора слова
    """

    choose_word = State()
    delete_word = State()
    translate_word = State()
    add_eng_word = State()
    add_rus_word = State()


bot.add_custom_filter(custom_filters.StateFilter(bot))


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
    bot.send_message(
        message.chat.id,
        f"Привет {message.from_user.username}👋 Давай попрактикуемся в английском языке. "
        "Нажми на кнопку 'Тренька!'",
        reply_markup=markup,
    )


def new_user(message):
    """
    Запись нового пользователя в базу данных или проверка существующего
    """
    with Session() as session:
        tg_id = message.from_user.id
        user = session.query(User).filter_by(tg_id=tg_id).first()
        username = None

        if user is None:
            # Создаем имя пользователя на основе доступных данных
            username = (
                message.from_user.username
                or message.from_user.first_name
                or f"user_{tg_id}"
            )
            user = User(username=username, tg_id=tg_id)
            session.add(user)
            try:
                session.commit()
            except Exception as e:
                session.rollback()
                print(f"Ошибка при создании пользователя: {e}")
                return None

        return user


def create_words(message):
    """
    Создает набор слов для тренировки и обновляет статистику пользователя
    """
    with Session() as session:
        user = session.query(User).filter_by(tg_id=message.from_user.id).first()
        if not user:
            print(f"Юзер {message.from_user.username} вне игры!")
            return []

        # Получаем 4 случайных слова из базы данных
        word_pairs = session.query(Word).order_by(func.random()).limit(4).all()
        if not word_pairs:
            return []

        # Формируем список пар слов
        pairs = [(w.original, w.translation, w.word_id) for w in word_pairs]

        # Обновляем статистику пользователя по каждому слову
        for _, _, word_id in pairs:
            if not word_id:
                continue
            word = session.query(Word).filter_by(word_id=word_id).first()
            if not word:
                continue

            # Проверяем, есть ли уже запись о слове у пользователя
            user_word = (
                session.query(UserWord)
                .filter_by(user_id=user.user_id, word_id=word_id)
                .first()
            )
            if user_word:
                # Если есть, увеличиваем счетчик просмотров
                user_word.seen_count += 1
            else:
                # Если нет, создаем новую запись
                session.add(
                    UserWord(user_id=user.user_id, word_id=word_id, seen_count=1)
                )
        session.commit()
    return pairs


def show_target(data):
    """
    Формирует строку с правильным переводом слова
    """
    return f"{data['choose_word']} -> {data['translate_word']}"


def show_hint(*lines):
    """
    Объединяет строки в одно сообщение с подсказкой
    """
    return "\n".join(lines)


def update_learning_history(user_id, word_id, is_correct):
    """
    Обновляет историю изучения слов пользователя
    """
    # Если ID слова не указан, прекращаем выполнение
    if not word_id:
        return

    with Session() as session:
        # Получаем пользователя по Telegram ID
        user = session.query(User).filter_by(tg_id=user_id).first()
        if not user:
            return

        # Получаем слово по ID
        word = session.query(Word).filter_by(word_id=word_id).first()
        if not word:
            return

        # Проверяем существование записи в истории изучения
        history = (
            session.query(LearningHistory)
            .filter_by(user_id=user.user_id, word_id=word_id)
            .first()
        )

        # Обновляем или создаем запись в истории изучения
        if history:
            # Обновляем существующую запись
            if is_correct:
                history.correct_count += 1
            else:
                history.fail_count += 1
        else:
            # Создаем новую запись
            if is_correct:
                history = LearningHistory(
                    user_id=user.user_id, word_id=word_id, correct_count=1, fail_count=0
                )
            else:
                history = LearningHistory(
                    user_id=user.user_id, word_id=word_id, correct_count=0, fail_count=1
                )
            session.add(history)

        session.commit()


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
        types.KeyboardButton(row[0]) for row in pairs if row[0] != selected_pair[0]
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
    bot.set_state(message.from_user.id, StateWords.choose_word, message.chat.id)
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        data["choose_word"] = selected_pair[0]
        data["translate_word"] = selected_pair[1]
        data["word_id"] = selected_pair[2]
        data["buttons"] = buttons
        print(f"Сохранено в состояние: choose_word={selected_pair[0]}")

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
    bot.send_message(message.chat.id, "Введите слово на английском для удаления:")
    bot.set_state(message.from_user.id, StateWords.delete_word, message.chat.id)


@bot.message_handler(state=StateWords.delete_word)
def input_delete_word(message):
    """
    Обработчик удаления слова из базы данных
    """
    eng_word = message.text
    tg_id = message.from_user.id

    # Удаляем состояние пользователя
    bot.delete_state(message.from_user.id, message.chat.id)

    # Удаляем слово из базы данных
    with Session() as session:
        user = session.query(User).filter(User.tg_id == tg_id).first()
        if not user:
            bot.send_message(message.chat.id, "Пользователь не найден!")
            return
        word = (
            session.query(Dictionary)
            .filter(
                Dictionary.added_eng_word == eng_word,
                Dictionary.user_id == user.user_id,
            )
            .first()
        )
        if word:
            session.delete(word)
            session.commit()
            bot.send_message(message.chat.id, f"Слово '{eng_word}' успешно удалено!")
        else:
            bot.send_message(message.chat.id, "Слово не найдено.")

    train(message)


@bot.message_handler(commands=["stats"])
def show_stats(message):
    """
    Обработчик команды /stats - показывает статистику пользователей
    """
    with Session() as session:
        # Получаем топ-3 пользователей по количеству правильных ответов
        stats = (
            session.query(
                User.username,
                func.sum(LearningHistory.correct_count).label("total_correct"),
                func.sum(LearningHistory.fail_count).label("total_errors"),
            )
            .join(LearningHistory, User.user_id == LearningHistory.user_id)
            .group_by(User.user_id, User.username)
            .having(func.sum(LearningHistory.correct_count) > 0)
            .order_by(func.sum(LearningHistory.correct_count).desc())
            .limit(3)
            .all()
        )

        if not stats:
            bot.send_message(
                message.chat.id,
                "Статистика пока пуста. Начните тренироваться, чтобы попасть в рейтинг!",
            )
            return

        # Формируем сообщение со статистикой
        message_text = "ЛИДЕРЫ:\n\n"
        medals = ["🥇", "🥈", "🥉"]

        for idx, (username, total_correct, total_errors) in enumerate(stats, 1):
            medal = medals[idx - 1]
            message_text += (
                f"{medal} {username}\n"
                f"   Правильных: {total_correct or 0}\n"
                f"   Ошибок: {total_errors or 0}\n\n"
            )

        bot.send_message(message.chat.id, message_text)


@bot.message_handler(func=lambda message: message.text == Command.ADD_WORD)
def add_word(message):
    """
    Обработчик кнопки 'Добавить слово' - запрашивает английское слово
    """
    bot.send_message(message.chat.id, "Введите английское слово:")
    bot.set_state(message.from_user.id, StateWords.add_eng_word, message.chat.id)


@bot.message_handler(state=StateWords.add_eng_word)
def get_add_eng_word(message):
    """
    Обработчик ввода английского слова
    """
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        data["add_eng_word"] = message.text
        data["word_id"] = message.from_user.id
    bot.send_message(message.chat.id, "Введите перевод слова:")
    bot.set_state(message.from_user.id, StateWords.add_rus_word, message.chat.id)


@bot.message_handler(state=StateWords.add_rus_word)
def get_add_rus_word(message):
    """
    Обработчик ввода перевода слова - добавляет слово в базу данных
    """
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        data["add_rus_word"] = message.text

        with Session() as session:
            user = (
                session.query(User).filter(User.tg_id == message.from_user.id).first()
            )
            if not user:
                bot.send_message(
                    message.chat.id, "Пользователь не найден в базе данных!"
                )
                bot.delete_state(message.from_user.id, message.chat.id)
                return

            word = Dictionary(
                user_id=user.user_id,
                added_eng_word=data["add_eng_word"],
                added_rus_word=data["add_rus_word"],
            )
            session.add(word)
            session.commit()
    bot.send_message(message.chat.id, "Слово успешно добавлено!")
    bot.delete_state(message.from_user.id, message.chat.id)
    train(message)


@bot.message_handler(func=lambda message: True, content_types=["text"])
def message_reply(message):
    """
    Обработчик ответа пользователя
    """
    text = message.text
    # Игнорируем команды, которые обрабатываются отдельно
    if text in [Command.NEXT, Command.ADD_WORD, Command.DELETE_WORD, "Тренька!"]:
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
            update_learning_history(message.from_user.id, word_id, is_correct=True)
        hint = show_target(
            {"choose_word": choose_word, "translate_word": translate_word}
        )
        hint_text = ["Отлично!❤", hint]
        hint = show_hint(*hint_text)
        bot.send_message(message.chat.id, hint)
    else:
        # Обработка неправильного ответа
        if word_id:
            update_learning_history(message.from_user.id, word_id, is_correct=False)
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


if __name__ == "__main__":
    print("Бот запущен...")
    bot.polling(none_stop=True, interval=0)
