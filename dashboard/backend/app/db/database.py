# This file initializes the SQLAlchemy database instance for use with Flask.
# The 'db' object is used throughout the project for ORM operations.

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()