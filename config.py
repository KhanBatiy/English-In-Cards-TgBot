import os
from dotenv import load_dotenv


load_dotenv(dotenv_path=".env")


class Config:
    BOT_TOKEN = os.getenv("TOKEN")

    host = os.getenv("DB_HOST")
    port = os.getenv("DB_PORT")
    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASSWORD")
    db_name = os.getenv("DB_NAME")

    DSN = f"postgresql://{user}:{password}@{host}:{port}/{db_name}"


config = Config()
