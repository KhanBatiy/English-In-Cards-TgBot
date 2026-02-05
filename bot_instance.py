from telebot import TeleBot, custom_filters
from telebot.storage import StateMemoryStorage
from config import config

storage = StateMemoryStorage()
bot = TeleBot(config.BOT_TOKEN, state_storage=storage)
bot.add_custom_filter(custom_filters.StateFilter(bot))
