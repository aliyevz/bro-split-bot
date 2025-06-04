import sqlite3

# Префикс для имени файла базы данных (например, debts_-123456789.db)
DB_PREFIX = 'debts'

def get_db_path(chat_id: int) -> str:
    """Возвращает путь к файлу базы данных для конкретного чата."""
    return f"{DB_PREFIX}{chat_id}.db"

def get_db_connection(chat_id: int):
    """
    Возвращает объект соединения и курсора для конкретного чата.
    Позволяет управлять транзакциями извне.
    """
    db_path = get_db_path(chat_id)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    return conn, cursor

def init_db(chat_id: int):
    """
    Инициализирует базу данных для конкретного чата,
    создавая таблицу debts и cards, если она не существует.
    """
    conn, cursor = get_db_connection(chat_id)
    try:
        cursor.execute("""
                CREATE TABLE IF NOT EXISTS debts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    operDate DATETIME DEFAULT CURRENT_TIMESTAMP,
                    debtor TEXT,
                    creditor TEXT,
                    amount REAL
                )
            """)
        cursor.execute("""
                CREATE TABLE IF NOT EXISTS cards (
                    username TEXT PRIMARY KEY,
                    card_number TEXT
                )
            """)
        conn.commit() # Коммит создания таблицы
        print(f"База данных '{get_db_path(chat_id)}' инициализирована.")
    finally:
        conn.close()


def add_debts_batch(chat_id: int, debts_data: list):
    """
    Add array of debts, so there would be common commit at the end
    """
    conn, cursor = get_db_connection(chat_id)
    try:
        cursor.executemany(
            'INSERT INTO debts (debtor, creditor, amount) VALUES (?, ?, ?)',
            debts_data  # Здесь передается сам список notes_data
        )
        conn.commit()  # Коммит только после всех операций
        print(f"Successfully added {len(debts_data)} debts.")
    except Exception as e:
        conn.rollback()  # Откат в случае ошибки
        print(f"Error while batch saving od debts {chat_id}: {e}")
        raise  # Повторно вызываем исключение, чтобы его можно было обработать выше
    finally:
        conn.close()

def set_card(chat_id: int, username, card_number):
    """
    Save card assigned to user
    """
    conn, cursor = get_db_connection(chat_id)
    try:
        cursor.execute("REPLACE INTO cards (username, card_number) VALUES (?, ?)", (username, card_number))
        conn.commit()
        print(f"Successfully added card.")
    except Exception as e:
        conn.rollback()  # Откат в случае ошибки
        print(f"Error while card add {chat_id}: {e}")
        raise  # Повторно вызываем исключение, чтобы его можно было обработать выше
    finally:
        conn.close()

def get_card(chat_id: int, username: str):
    """
    Get card assigned to user
    """
    conn, cursor = get_db_connection(chat_id)
    try:
        print(username)
        cursor.execute("SELECT card_number FROM cards WHERE username = ?", (username,))
        card = cursor.fetchone()
        if card:
            return card
        print(f"Successfully added card.")
    except Exception as e:
        print(f"Error while card fetching {chat_id}: {e}")
        raise  # Повторно вызываем исключение, чтобы его можно было обработать выше
    finally:
        conn.close()

def get_debts(chat_id: int):
    """Get all debts for certain chat_id."""
    conn, cursor = get_db_connection(chat_id)
    try:
        cursor.execute("SELECT debtor, creditor, SUM(amount) FROM debts GROUP BY debtor, creditor")
        rows = cursor.fetchall()
        return rows
    finally:
        conn.close()


def reset_debts(chat_id: int):
    """Reset all debts for certain chat_id."""
    conn, cursor = get_db_connection(chat_id)
    try:
        cursor.execute("DELETE FROM debts")
        conn.commit()
    except Exception as e:
        print(f"Error while debts resetting {chat_id}: {e}")
        raise  # Повторно вызываем исключение, чтобы его можно было обработать выше
    finally:
        conn.close()

def get_all_debts_report(chat_id: int):
    """Get all debts for excel report chat_id."""
    conn, cursor = get_db_connection(chat_id)
    try:
        cursor.execute("SELECT operDate, debtor, creditor, amount FROM debts")
        rows = cursor.fetchall()
        return rows
    finally:
        conn.close()