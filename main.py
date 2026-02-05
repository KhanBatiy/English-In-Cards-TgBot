from bot_instance import bot
import handlers


if __name__ == "__main__":
    print("Бот запущен...")
    bot.polling(none_stop=True, interval=0)
