from telebot import TeleBot, types, custom_filters
from telebot.storage import StateMemoryStorage
from telebot.states import State, StatesGroup
from sqlalchemy import func
import random

from config import config
from database import Session
from models import Word, User, UserWord, LearningHistory


storage = StateMemoryStorage()
bot = TeleBot(config.BOT_TOKEN, state_storage=storage)


class StateWords(StatesGroup):
    choose_word = State()
    delete_word = State()
    translate_word = State()
    add_eng_word = State()
    add_rus_word = State()


bot.add_custom_filter(custom_filters.StateFilter(bot))


class Command:
    ADD_WORD = "Добавить слово ➕"
    DELETE_WORD = "Удалить слово🔙"
    NEXT = "Дальше ⏭"


@bot.message_handler(commands=["start"])
def start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("Тренька!"))
    bot.send_message(
        message.chat.id,
        f"Привет {message.from_user.username}👋 Давай попрактикуемся в английском языке. "
        "Нажми на кнопку 'Тренька!'",
        reply_markup=markup,
    )


def new_user(message):
    with Session() as session:
        user = session.query(User).filter_by(tg_id=message.from_user.id).first()
        if user is None:
            username = (
                message.from_user.username
                or message.from_user.first_name
                or f"user_{message.from_user.id}"
            )
            new_user_obj = User(tg_id=message.from_user.id, username=username)
            session.add(new_user_obj)
            session.commit()

        if user:
            username = (
                user.username
                or message.from_user.username
                or message.from_user.first_name
                or f"user_{message.from_user.id}"
            )
        return f"Юзер {username} в игре!"


def create_words(message):
    with Session() as session:
        user = session.query(User).filter_by(tg_id=message.from_user.id).first()
        if not user:
            print(f"Юзер {message.from_user.username} вне игры!")
            return []
        word_pairs = session.query(Word).order_by(func.random()).limit(4).all()
        if not word_pairs:
            return []
        pairs = [(w.original, w.translation, w.word_id) for w in word_pairs]
        for _, _, word_id in pairs:
            if not word_id:
                continue
            word = session.query(Word).filter_by(word_id=word_id).first()
            if not word:
                continue
            stmn = (
                session.query(UserWord)
                .filter_by(user_id=user.user_id, word_id=word_id)
                .first()
            )
            if stmn:
                stmn.score += 1
            else:
                session.add(UserWord(user_id=user.user_id, word_id=word_id, score=1))
        session.commit()
    return pairs


def show_target(data):
    return f"{data['choose_word']} -> {data['translate_word']}"


def show_hint(*lines):
    return "\n".join(lines)


def update_learning_history(user_id, word_id, is_correct):
    if not word_id:
        return

    with Session() as session:
        user = session.query(User).filter_by(tg_id=user_id).first()
        if not user:
            return

        word = session.query(Word).filter_by(word_id=word_id).first()
        if not word:
            return

        history = (
            session.query(LearningHistory)
            .filter_by(user_id=user.user_id, word_id=word_id)
            .first()
        )

        if history:
            if is_correct:
                history.correct_count += 1
            else:
                history.feil_count += 1
        else:
            if is_correct:
                history = LearningHistory(
                    user_id=user.user_id, word_id=word_id, correct_count=1, feil_count=0
                )
            else:
                history = LearningHistory(
                    user_id=user.user_id, word_id=word_id, correct_count=0, feil_count=1
                )
            session.add(history)

        session.commit()


@bot.message_handler(func=lambda message: message.text == "Тренька!")
def train(message):
    new_user(message)
    pairs = create_words(message)
    if not pairs:
        bot.send_message(
            message.chat.id, "Ошибка: не удалось получить слова для тренировки"
        )
        return
    selected_pair = random.choice(pairs)
    if len(selected_pair) < 3:
        bot.send_message(message.chat.id, "Ошибка: некорректные данные слова")
        return

    markup = types.ReplyKeyboardMarkup(row_width=2)

    buttons = []
    target_btn = types.KeyboardButton(selected_pair[0])
    buttons.append(target_btn)
    others_btn = [
        types.KeyboardButton(row[0]) for row in pairs if row[0] != selected_pair[0]
    ]
    buttons.extend(others_btn)
    random.shuffle(buttons)

    next_btn = types.KeyboardButton(Command.NEXT)
    add_word_btn = types.KeyboardButton(Command.ADD_WORD)
    delete_word_btn = types.KeyboardButton(Command.DELETE_WORD)
    buttons.extend([next_btn, add_word_btn, delete_word_btn])
    markup.add(*buttons)

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
    train(message)


@bot.message_handler(func=lambda message: message.text == Command.DELETE_WORD)
def delete_word(message):
    bot.send_message(message.chat.id, "Введите слово на английском для удаления:")
    bot.set_state(message.from_user.id, StateWords.delete_word, message.chat.id)


@bot.message_handler(state=StateWords.delete_word)
def input_delete_word(message):
    add_eng_word = message.text

    bot.delete_state(message.from_user.id, message.chat.id)

    with Session() as session:
        word = session.query(Word).filter_by(original=add_eng_word).first()
        if word:
            word_id = word.word_id
            session.query(UserWord).filter_by(word_id=word_id).delete()
            session.query(LearningHistory).filter_by(word_id=word_id).delete()
            session.delete(word)
            session.commit()
            bot.send_message(
                message.chat.id, f"Слово '{add_eng_word}' успешно удалено!"
            )
        else:
            bot.send_message(message.chat.id, "Слово не найдено.")

    train(message)


@bot.message_handler(commands=["stats"])
def show_stats(message):
    with Session() as session:
        stats = (
            session.query(
                User.username,
                func.sum(LearningHistory.correct_count).label("total_correct"),
                func.sum(LearningHistory.feil_count).label("total_errors"),
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
    bot.send_message(message.chat.id, "Введите английское слово:")
    bot.set_state(message.from_user.id, StateWords.add_eng_word, message.chat.id)


@bot.message_handler(state=StateWords.add_eng_word)
def get_add_eng_word(message):
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        data["add_eng_word"] = message.text
    bot.send_message(message.chat.id, "Введите перевод слова:")
    bot.set_state(message.from_user.id, StateWords.add_rus_word, message.chat.id)


@bot.message_handler(state=StateWords.add_rus_word)
def get_add_rus_word(message):
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        data["add_rus_word"] = message.text
        with Session() as session:
            word = Word(original=data["add_eng_word"], translation=data["add_rus_word"])
            session.add(word)
            session.commit()
    bot.send_message(message.chat.id, "Слово успешно добавлено!")
    bot.delete_state(message.from_user.id, message.chat.id)
    train(message)


@bot.message_handler(func=lambda message: True, content_types=["text"])
def message_reply(message):
    text = message.text
    if text in [Command.NEXT, Command.ADD_WORD, Command.DELETE_WORD, "Тренька!"]:
        return
    choose_word = None
    translate_word = None
    word_id = None
    buttons = []

    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        choose_word = data.get("choose_word")
        translate_word = data.get("translate_word")
        word_id = data.get("word_id")
        buttons = data.get("buttons", [])

        if text == choose_word:
            if word_id:
                update_learning_history(message.from_user.id, word_id, is_correct=True)
            hint = show_target(data)
            hint_text = ["Отлично!❤", hint]
            hint = show_hint(*hint_text)
            bot.send_message(message.chat.id, hint)
        else:
            if word_id:
                update_learning_history(message.from_user.id, word_id, is_correct=False)
            hint = show_hint(
                "Допущена ошибка!",
                f"Попробуй ещё раз - 🇷🇺{translate_word}",
            )
            markup = types.ReplyKeyboardMarkup(row_width=2)
            if buttons:
                markup.add(*buttons)
            bot.send_message(message.chat.id, hint, reply_markup=markup)
            return
    if not choose_word:
        train(message)
    else:
        bot.delete_state(message.from_user.id, message.chat.id)
        train(message)


if __name__ == "__main__":
    print("Бот запущен...")
    bot.polling(none_stop=True, interval=0)
