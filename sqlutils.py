import os
import sqlite3

# Name of the database file
DB_FILE = "sensor_data.db"


def initialize_database():
    # 1. Check if DB file exists
    db_exists = os.path.exists(DB_FILE)

    # 2. Connect to the database (creates file automatically if missing)
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # 3. Create table if it does not exist
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sensor_readings (
            timestamp INTEGER,
            touch_value INTEGER,
            motion_value INTEGER
        )
    """)

    conn.commit()
    conn.close()

    if db_exists:
        print("Database already existed. Table checked/created.")
    else:
        print("New database created and table initialized.")


def insert_reading(timestamp, touch_value, motion_value):
    """Insert a new sensor reading into the table."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO sensor_readings (timestamp, touch_value, motion_value)
        VALUES (?, ?, ?)
    """, (timestamp, touch_value, motion_value))

    conn.commit()
    conn.close()
    print("Inserted:", timestamp, touch_value, motion_value)


def read_all_rows():
    """Read and return all rows from the sensor_readings table."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM sensor_readings")
    rows = cursor.fetchall()

    conn.close()
    return rows


def read_last_row():
    """Return the last (most recent) row based on the largest timestamp."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM sensor_readings
        ORDER BY timestamp DESC
        LIMIT 1
    """)
    row = cursor.fetchone()

    conn.close()
    return row


if __name__ == "__main__":
    initialize_database()
