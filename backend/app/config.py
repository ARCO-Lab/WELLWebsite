import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    API_URL = os.getenv("HOBOLINK_API_URL")
    API_TOKEN = os.getenv("HOBOLINK_API_TOKEN")
    LOGGERS = os.getenv("HOBOLINK_LOGGERS")