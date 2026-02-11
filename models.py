"""
Модели БД для бота-тренажёра слов.

Схема:
  users            — пользователи (tg_id, username).
  words            — общий словарь: original, translation.
  dictionaries     — слова пользователя: added_eng_word, added_rus_word.
  learning_history — по user+word: correct_count, fail_count, seen_count.

Связи: User 1─* Dictionary, User 1─* LearningHistory, Word 1─* LearningHistory.
Длина строк слов задаётся в validators.MAX_WORD_LENGTH.
"""
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import (
    Column, Integer, String, ForeignKey, TIMESTAMP, BigInteger,
)
from sqlalchemy.orm import relationship
from datetime import datetime

from validators import MAX_WORD_LENGTH

USERNAME_STRING_LENGTH = 100

Base = declarative_base()


class User(Base):
    """
    Таблица для хранения пользователей
    """

    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True)
    username = Column(String(USERNAME_STRING_LENGTH), nullable=False)
    tg_id = Column(BigInteger, nullable=False, unique=True)
    created_at = Column(TIMESTAMP, default=datetime.now)

    def __repr__(self):
        return (
            f"User(id={self.user_id}, username={self.username}, "
            f"tg_id={self.tg_id}, created_at={self.created_at})"
        )


class Word(Base):
    """
    Таблица для хранения слов
    """

    __tablename__ = "words"

    word_id = Column(Integer, primary_key=True)
    original = Column(String(MAX_WORD_LENGTH), nullable=False)
    translation = Column(String(MAX_WORD_LENGTH), nullable=False)

    def __repr__(self):
        return (
            f"Word(id={self.word_id}, original={self.original}, "
            f"translation={self.translation})"
        )


class Dictionary(Base):
    """
    Таблица для добавления слов пользователей
    """

    __tablename__ = "dictionaries"

    dictionary_id = Column(Integer, primary_key=True)
    user_id = Column(
        Integer,
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    added_eng_word = Column(String(MAX_WORD_LENGTH), nullable=True)
    added_rus_word = Column(String(MAX_WORD_LENGTH), nullable=True)
    removed_word = Column(String(MAX_WORD_LENGTH), nullable=True)

    user = relationship("User", backref="dictionaries")

    def __repr__(self):
        return (
            f"Dictionary(id={self.dictionary_id}, user_id={self.user_id}, "
            f"added_eng_word={self.added_eng_word}, "
            f"added_rus_word={self.added_rus_word})"
        )


class LearningHistory(Base):
    """
    Таблица для хранения истории изучения слов пользователя
    """

    __tablename__ = "learning_history"

    learning_history_id = Column(Integer, primary_key=True)
    user_id = Column(
        Integer,
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    word_id = Column(
        Integer,
        ForeignKey("words.word_id", ondelete="CASCADE"),
        nullable=False,
    )
    correct_count = Column(Integer, nullable=False, default=0)
    fail_count = Column(Integer, nullable=False, default=0)
    # сколько раз слово показывалось пользователю
    seen_count = Column(Integer, nullable=False, default=0)

    user = relationship("User", backref="learning_history")
    word = relationship("Word", backref="learning_history")

    def __repr__(self):
        return (
            f"LearningHistory(id={self.learning_history_id}, "
            f"user_id={self.user_id}, word_id={self.word_id}, "
            f"correct_count={self.correct_count}, "
            f"fail_count={self.fail_count}, "
            f"seen_count={self.seen_count})"
        )
