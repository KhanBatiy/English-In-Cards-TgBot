from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, ForeignKey, TIMESTAMP, BigInteger
from sqlalchemy.orm import relationship
from datetime import datetime


Base = declarative_base()


class User(Base):
    """
    Таблица для хранения пользователей
    """

    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True)
    username = Column(String, nullable=False)
    tg_id = Column(BigInteger, nullable=False, unique=True)
    created_at = Column(TIMESTAMP, default=datetime.now)

    def __repr__(self):
        return f"User(id={self.user_id}, username={self.username}, \
                tg_id={self.tg_id}, created_at={self.created_at})"


class Word(Base):
    """
    Таблица для хранения слов
    """

    __tablename__ = "words"

    word_id = Column(Integer, primary_key=True)
    original = Column(String, nullable=False)
    translation = Column(String, nullable=False)

    def __repr__(self):
        return f"Word(id={self.word_id}, original={self.original}, translation={self.translation})"


class Dictionary(Base):
    """
    Таблица для добавления и удаления слов пользователей
    """

    __tablename__ = "dictionaries"

    dictionary_id = Column(Integer, primary_key=True)
    user_id = Column(
        Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False
    )
    added_eng_word = Column(String, nullable=True)
    added_rus_word = Column(String, nullable=True)
    removed_word = Column(String, nullable=True)

    user = relationship("User", backref="dictionaries")

    def __repr__(self):
        return f"Dictionary(id={self.dictionary_id}, user_id={self.user_id}, \
            added_eng_word={self.added_eng_word}, added_rus_word={self.added_rus_word})"


class UserWord(Base):
    """
    Таблица для хранения слов пользователя
    """

    __tablename__ = "user_words"

    user_word_id = Column(Integer, primary_key=True)
    user_id = Column(
        Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False
    )
    word_id = Column(
        Integer, ForeignKey("words.word_id", ondelete="CASCADE"), nullable=False
    )
    added_at = Column(TIMESTAMP, default=datetime.now)
    seen_count = Column(
        Integer, default=0
    )  # количество раз, когда слово было просмотрено

    user = relationship("User", backref="user_words")
    word = relationship("Word", backref="user_words")

    def __repr__(self):
        return f"UserWord(id={self.user_word_id}, user_id={self.user_id}, \
            word_id={self.word_id}, added_at={self.added_at}, \
            seen_count={self.seen_count})"


class LearningHistory(Base):
    """
    Таблица для хранения истории изучения слов пользователя
    """

    __tablename__ = "learning_history"

    learning_history_id = Column(Integer, primary_key=True)
    user_id = Column(
        Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False
    )
    word_id = Column(
        Integer, ForeignKey("words.word_id", ondelete="CASCADE"), nullable=False
    )
    correct_count = Column(Integer, nullable=False, default=0)
    fail_count = Column(Integer, nullable=False, default=0)

    user = relationship("User", backref="learning_history")
    word = relationship("Word", backref="learning_history")

    def __repr__(self):
        return (
            f"LearningHistory(id={self.learning_history_id}, user_id={self.user_id}, \
                word_id={self.word_id}, correct_count={self.correct_count}, \
                fail_count={self.fail_count})"
        )
