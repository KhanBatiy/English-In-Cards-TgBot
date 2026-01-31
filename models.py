from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import (
    Column,
    Integer,
    String,
    ForeignKey,
    TIMESTAMP,
    Boolean,
)
from sqlalchemy.orm import relationship
from datetime import datetime


Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String, nullable=False)
    tg_id = Column(Integer, nullable=False, unique=True)
    created_at = Column(TIMESTAMP, default=datetime.now)

    def __repr__(self):
        return f"User(id={self.user_id}, username={self.username}, \
                tg_id={self.tg_id}, created_at={self.created_at})"


class Word(Base):
    __tablename__ = "words"

    word_id = Column(Integer, primary_key=True)
    original = Column(String, nullable=False)
    translation = Column(String, nullable=False)

    def __repr__(self):
        return f"Word(id={self.word_id}, original={self.original}, translation={self.translation})"


class UserWord(Base):
    __tablename__ = "user_words"

    user_word_id = Column(Integer, primary_key=True)
    user_id = Column(
        Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False
    )
    word_id = Column(
        Integer, ForeignKey("words.word_id", ondelete="CASCADE"), nullable=False
    )
    added_at = Column(TIMESTAMP, default=datetime.now)
    removed_at = Column(TIMESTAMP, nullable=True)
    score = Column(Integer, default=0)

    user = relationship("User", backref="user_words", cascade="all, delete")
    word = relationship("Word", backref="user_words", cascade="all, delete")

    def __repr__(self):
        return f"UserWord(id={self.id}, user_id={self.user_id}, \
            word_id={self.word_id}, added_at={self.added_at}, \
            removed_at={self.removed_at}, score={self.score})"


class LearningHistory(Base):
    __tablename__ = "learning_history"

    learning_history_id = Column(Integer, primary_key=True)
    user_id = Column(
        Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False
    )
    word_id = Column(
        Integer, ForeignKey("words.word_id", ondelete="CASCADE"), nullable=False
    )
    answer = Column(String, nullable=False)
    is_correct = Column(Boolean, nullable=False)
    options = Column(String, nullable=False)

    user = relationship("User", backref="learning_history", cascade="all, delete")
    word = relationship("Word", backref="learning_history", cascade="all, delete")

    def __repr__(self):
        return f"LearningHistory(id={self.id}, user_id={self.user_id}, \
                word_id={self.word_id}, answer={self.answer}, \
                is_correct={self.is_correct}, options={self.options})"
