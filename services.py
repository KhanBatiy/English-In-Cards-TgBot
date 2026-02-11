import logging

from default_db import Session
from models import Word, User, LearningHistory
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

logger = logging.getLogger(__name__)


def new_user(message):
    """
    Запись нового пользователя в базу данных или проверка существующего
    """
    try:
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
                except IntegrityError as e:
                    session.rollback()
                    logger.warning(
                        "Ошибка целостности при создании пользователя "
                        "tg_id=%s: %s",
                        tg_id, e,
                    )
                    return None
                except SQLAlchemyError as e:
                    session.rollback()
                    logger.exception(
                        "Ошибка БД при создании пользователя tg_id=%s: %s",
                        tg_id, e,
                    )
                    return None

            return user
    except SQLAlchemyError as e:
        logger.exception(
            "Ошибка БД в new_user (tg_id=%s): %s",
            message.from_user.id, e,
        )
        return None
    except Exception as e:
        logger.exception("Неожиданная ошибка в new_user: %s", e)
        return None


def create_words(message):
    """
    Создает набор слов для тренировки и обновляет статистику пользователя
    """
    try:
        with Session() as session:
            user = (
                session.query(User)
                .filter_by(tg_id=message.from_user.id)
                .first()
            )
            if not user:
                print(f"Юзер {message.from_user.username} вне игры!")
                return []

            # Получаем 4 случайных слова из базы данных
            word_pairs = (
                session.query(Word).order_by(func.random()).limit(4).all()
            )
            if not word_pairs:
                return []

            # Формируем список пар слов
            pairs = [
                (w.original, w.translation, w.word_id) for w in word_pairs
            ]

            # Обновляем счётчик показов в LearningHistory
            # для каждого показанного слова
            for _, _, word_id in pairs:
                if not word_id:
                    continue
                word = session.query(Word).filter_by(word_id=word_id).first()
                if not word:
                    continue

                history = (
                    session.query(LearningHistory)
                    .filter_by(user_id=user.user_id, word_id=word_id)
                    .first()
                )
                if history:
                    history.seen_count += 1
                else:
                    session.add(
                        LearningHistory(
                            user_id=user.user_id,
                            word_id=word_id,
                            correct_count=0,
                            fail_count=0,
                            seen_count=1,
                        )
                    )
            session.commit()
        return pairs
    except SQLAlchemyError as e:
        logger.exception(
            "Ошибка БД в create_words (tg_id=%s): %s",
            message.from_user.id, e,
        )
        return []
    except Exception as e:
        logger.exception("Неожиданная ошибка в create_words: %s", e)
        return []


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

    try:
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
                        user_id=user.user_id,
                        word_id=word_id,
                        correct_count=1,
                        fail_count=0,
                    )
                else:
                    history = LearningHistory(
                        user_id=user.user_id,
                        word_id=word_id,
                        correct_count=0,
                        fail_count=1,
                    )
                session.add(history)

            session.commit()
    except SQLAlchemyError as e:
        logger.exception(
            "Ошибка БД в update_learning_history (user_id=%s, word_id=%s): %s",
            user_id, word_id, e,
        )
    except Exception as e:
        logger.exception("Неожиданная ошибка в update_learning_history: %s", e)
