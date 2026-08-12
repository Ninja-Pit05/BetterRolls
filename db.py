""" Database related stuff. """
import sqlite3



class ConnectionManager:
    """ A Context Manager responsible for handling connection and cursor
    creation as well as closing them onde on exit.

    Queries can be done as usual, trough ConenctionManager.cursor or
    ConnectionManager.connection. The manager also disposes of a shortcut
    to commit changes: ConnectionManager.commit()

    Commits must be explicity done trought connection.commit or
    ConnectionManager.commit(). Uncommited changes won't be saved.

    Args:
        file(str) - Path to the .db file.
    """
    def __init__(self, file: str):
        self.file = file

    def __enter__(self):
        self.connection = sqlite3.connect(self.file)
        self.cursor = self.connection.cursor()
        self.cursor.execute("PRAGMA foreign_keys = 1")
        return self
    
    def commit(self):
        """ Shortcut to ConnectionManager.connection.commit(). """
        self.connection.commit()
    
    def __exit__(self, type, value, traceback):
        self.cursor.close()
        self.connection.close()



def init_db(file: str):
    """ Initialises the database. """
    with ConnectionManager(file) as db:
        db.cursor.executescript("""

            CREATE TABLE IF NOT EXISTS users(
                id INTEGER PRIMARY KEY
                , user INT
                ) STRICT;

            CREATE TABLE IF NOT EXISTS stattypes(
                id INTEGER PRIMARY KEY
                , type TEXT
                ) STRICT;

            CREATE TABLE IF NOT EXISTS stats(
                id INTEGER PRIMARY KEY
                , label TEXT
                , user_id INT
                , stattype_id INT
                , value TEXT
                , min INT
                , max INT
                , FOREIGN KEY (user_id) REFERENCES users(id)
                    ON DELETE CASCADE
                , FOREIGN KEY (stattype_id) REFERENCES stattypes(id)
                    ON DELETE CASCADE
                ) STRICT;

            CREATE TABLE IF NOT EXISTS rolltypes(
                id INTEGER PRIMARY KEY
                , type TEXT
                ) STRICT;

            CREATE TABLE IF NOT EXISTS rolls(
                id INTEGER PRIMARY KEY
                , user_id INT
                , rolltype_id INT
                , timestamp INT
                , FOREIGN KEY (user_id) REFERENCES users(id)
                    ON DELETE CASCADE
                , FOREIGN KEY (rolltype_id) REFERENCES rolltypes(id)
                    ON DELETE CASCADE
                ) STRICT;

            CREATE TABLE IF NOT EXISTS dices(
                roll_id INT
                , type INT
                , value INT
                , FOREIGN KEY (roll_id) REFERENCES rolls(id)
                    ON DELETE CASCADE
                ) STRICT;
            """)
        try:
            db.cursor.execute("""
                    INSERT INTO stattypes (id, type)
                        VALUES
                            (0, 'integer')
                            ,(1, 'float')
                            ,(2, 'rangeinteger')
                            ,(3, 'rangefloat')
                            ,(4, 'text')
                            ,(5, 'limitedtext')
                    """)
        except:
            pass
        try:
            db.cursor.execute("""
                    INSERT INTO rolltypes (id, type)
                        VALUES
                            (0, 'single')
                            ,(1, 'advantage')
                            ,(2, 'disadvantage')
                            ,(3, 'grouped')
                    """)
        except:
            pass
        db.commit()


class UsersDBInterface:
    """ Responsible for storing users in the database and their surrogate
    keys retrieval. Other interfaces should use the user surrogate key
    instead of their discord id. """
    def __init__(self, file: str):
        self.file = file

    def add_user(self, user_id: int) -> None:
        with ConnectionManager(self.file) as db:
            db.cursor.execute(
                'INSERT INTO users VALUES(NULL, ?)', [user_id])
            db.connection.commit()

    def get_surrogate(self, user_id: int) -> int|None:
        with ConnectionManager(self.file) as db:
            _id = db.cursor.execute(
                'SELECT id FROM users WHERE user = ?',
                [user_id]).fetchone()
        if _id is None:
            return None
        return _id[0]
