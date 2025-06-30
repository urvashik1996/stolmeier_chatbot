import sqlite3
import logging

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

def init_db():
    """Initialize the SQLite database."""
    try:
        with sqlite3.connect('content.db') as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS content (
                    page_title TEXT,
                    url TEXT,
                    content_type TEXT,
                    content TEXT,
                    PRIMARY KEY (page_title, content_type)
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS contact_info (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    contact_text TEXT
                )
            ''')
            conn.commit()
            logging.debug("Database initialized successfully.")
    except Exception as e:
        logging.error(f"Error initializing database: {str(e)}")

def clear_database():
    """Clear all data from the database."""
    try:
        with sqlite3.connect('content.db') as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM content')
            cursor.execute('DELETE FROM contact_info')
            conn.commit()
            logging.debug("Database cleared successfully.")
    except Exception as e:
        logging.error(f"Error clearing database: {str(e)}")

def get_content(page_title, content_type):
    """Retrieve content from the database."""
    try:
        with sqlite3.connect('content.db') as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT content FROM content WHERE page_title = ? AND content_type = ?', (page_title, content_type))
            result = cursor.fetchone()
            if result:
                logging.debug(f"Content found for {page_title} ({content_type})")
                return result[0]
            logging.debug(f"No content found for {page_title} ({content_type})")
            return None
    except Exception as e:
        logging.error(f"Error retrieving content: {str(e)}")
        return None

def store_content(page_title, url, content_type, content):
    """Store content in the database."""
    try:
        with sqlite3.connect('content.db') as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO content (page_title, url, content_type, content)
                VALUES (?, ?, ?, ?)
            ''', (page_title, url, content_type, content))
            conn.commit()
            logging.debug(f"Stored content for {page_title} ({content_type})")
    except Exception as e:
        logging.error(f"Error storing content: {str(e)}")

def get_contact_info():
    """Retrieve contact information from the database."""
    try:
        with sqlite3.connect('content.db') as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT contact_text FROM contact_info ORDER BY id DESC LIMIT 1')
            result = cursor.fetchone()
            if result:
                logging.debug("Contact info found")
                return result[0]
            logging.debug("No contact info found")
            return None
    except Exception as e:
        logging.error(f"Error retrieving contact info: {str(e)}")
        return None

def store_contact_info(contact_text):
    """Store contact information in the database."""
    try:
        with sqlite3.connect('content.db') as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM contact_info')  # Clear old contact info
            cursor.execute('INSERT INTO contact_info (contact_text) VALUES (?)', (contact_text,))
            conn.commit()
            logging.debug("Stored contact info")
    except Exception as e:
        logging.error(f"Error storing contact info: {str(e)}")