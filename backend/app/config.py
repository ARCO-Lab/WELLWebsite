import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()
@dataclass(frozen=True)
class Config:
    HOBO_API_URL = os.getenv("HOBOLINK_API_URL")
    HOBO_API_TOKEN = os.getenv("HOBOLINK_API_TOKEN")
    HOBO_LOGGERS = os.getenv("HOBOLINK_LOGGERS")

    WQ_API_URL = os.getenv("WQ_API_URL")
    WQ_API_KEY = os.getenv("WQ_API_KEY")
    WQ_DEVICE_ID = os.getenv("WQ_DEVICE_ID")
    
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
