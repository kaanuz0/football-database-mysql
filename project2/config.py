import os


DB_HOST = os.getenv("TRANSFERDB_DB_HOST", "127.0.0.1")
DB_USER = os.getenv("TRANSFERDB_DB_USER", "root")
DB_PASSWORD = os.getenv("TRANSFERDB_DB_PASSWORD", "")
DB_NAME = os.getenv("TRANSFERDB_DB_NAME", "TransferDB")

SECRET_KEY = os.getenv("TRANSFERDB_SECRET_KEY", "transferdb-dev-secret")


def db_config(include_database=True, **overrides):
    config = {
        "host": DB_HOST,
        "user": DB_USER,
        "password": DB_PASSWORD,
    }
    if include_database:
        config["database"] = DB_NAME
    config.update(overrides)
    return config
