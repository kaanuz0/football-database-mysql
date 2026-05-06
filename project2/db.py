import mysql.connector

from config import db_config

DB_CONFIG = db_config()


def get_connection():
    return mysql.connector.connect(**DB_CONFIG)


def query(sql, params=None, fetchone=False, fetchall=False, commit=False):
    conn = get_connection()
    cur = conn.cursor(dictionary=True, buffered=True)
    try:
        cur.execute(sql, params or ())
        if commit:
            conn.commit()
            return cur.lastrowid, None
        if fetchone:
            return cur.fetchone(), None
        if fetchall:
            return cur.fetchall(), None
        return None, None
    except mysql.connector.Error as e:
        conn.rollback()
        return None, str(e)
    finally:
        cur.close()
        conn.close()


def callproc(proc_name, args):
    conn = get_connection()
    cur = conn.cursor()
    try:
        result_args = cur.callproc(proc_name, args)
        conn.commit()
        return result_args, None
    except mysql.connector.Error as e:
        conn.rollback()
        return None, str(e)
    finally:
        cur.close()
        conn.close()
