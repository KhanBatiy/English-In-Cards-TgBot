from telebot import TeleBot, types, custom_filters
from telebot.storage import StateMemoryStorage
from telebot.states import State, StatesGroup
from sqlalchemy import func
import random
from config import config
from database import Session
from models import Word, User, UserWord


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
        if session.query(User).filter_by(tg_id=message.from_user.id).first() is None:
            session.add(
                User(tg_id=message.from_user.id, username=message.from_user.username)
            )
        session.commit()
        return f"Пользователь {message.from_user.username} в игре!"


def create_words(message):
    with Session() as session:
        user = session.query(User).filter_by(tg_id=message.from_user.id).first()
        if not user:
            print(f"Юзер {message.from_user.username} вне игры!")
            return []
        word_pairs = session.query(Word).order_by(func.random()).limit(4).all()
        pairs = [(w.original, w.translation, w.word_id) for w in word_pairs]
        for _, _, index in pairs:
            stmn = session.query(UserWord).where(UserWord.word_id == index).first()
            if stmn:
                stmn.score += 1
            else:
                session.add(UserWord(user_id=user.user_id, word_id=index, score=1))
        session.commit()
    return pairs


def show_target(data):
    return f"{data['choose_word']} -> {data['translate_word']}"


def show_hint(*lines):
    return "\n".join(lines)


@bot.message_handler(func=lambda message: message.text == "Тренька!")
def train(message):
    new_user(message)
    pairs = create_words(message)
    selected_pair = random.choice(pairs)
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
        data["buttons"] = buttons  # Сохраняем кнопки в состоянии
    print(
        f"show_next_word: choose_word='{data['choose_word']}', translate_word='{data['translate_word']}'"
    )
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

    with Session() as session:
        word = session.query(Word).filter_by(original=add_eng_word).first()
        if word:
            session.delete(word)
            session.commit()
            bot.send_message(
                message.chat.id, f"Слово '{add_eng_word}' успешно удалено!"
            )
        else:
            bot.send_message(message.chat.id, "Слово не найдено.")

    bot.delete_state(message.from_user.id, message.chat.id)
    train(message)


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
    
    # Получаем данные из состояния и сохраняем значения
    choose_word = None
    translate_word = None
    buttons = []
    is_correct = False
    
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        choose_word = data.get("choose_word")
        translate_word = data.get("translate_word")
        buttons = data.get("buttons", [])
        
        if text == choose_word:
            # Правильный ответ
            print(f"Правильный ответ! text='{text}', choose_word='{choose_word}'")
            hint = show_target(data)
            hint_text = ["Отлично!❤", hint]
            hint = show_hint(*hint_text)
            bot.send_message(message.chat.id, hint)
            is_correct = True
        else:
            # Неправильный ответ
            hint = show_hint(
                "Допущена ошибка!",
                f"Попробуй ещё раз - 🇷🇺{translate_word}",
            )
            markup = types.ReplyKeyboardMarkup(row_width=2)
            if buttons:
                markup.add(*buttons)
            bot.send_message(message.chat.id, hint, reply_markup=markup)
            return
    
    # После закрытия контекста retrieve_data обновляем состояние
    if not choose_word:
        train(message)
    elif is_correct:
        # Очищаем старое состояние перед генерацией нового слова
        bot.delete_state(message.from_user.id, message.chat.id)
        train(message)


if __name__ == "__main__":
    print("Бот запущен...")
    bot.polling(none_stop=True, interval=0)
