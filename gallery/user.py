import flask
from flask_login import UserMixin
from contextlib import closing
import gal_utils
from passlib.apps import phpbb3_context
from passlib.hash import bcrypt

def canLogin(username, password):
    if not gal_utils.legalOwner(username) or not isinstance(password, unicode):
        return None

    u = get(username)
    if u is None:
        return None

    try:
        if not phpbb3_context.verify(password, u.password_hash):
            return None
    except ValueError:
        if not bcrypt.verify(password, u.password_hash):
            return None
    except:
        return None

    return u

def get(username):
    if not gal_utils.legalOwner(username):
        return None

    db = gal_utils.get_db()
    with closing(db.cursor()) as cursor:
        cursor.execute('SELECT user_password, user_rank, user_email FROM phpbb3_users '
                       'WHERE username=%s', (username,))
        data = cursor.fetchone()
        if data is None or len(data) < 3 or not isinstance(data[1], int) or \
                not isinstance(data[0], bytearray) or not isinstance(data[2], bytearray):
            return None

        user = User(username)
        user.password_hash = data[0].decode('utf-8')
        user.is_admin = data[1] == 1
        user.email = data[2].decode('utf-8')
        return user

class User(UserMixin):
    def __init__(self, user):
        if not isinstance(user, unicode):
            flask.abort(400, 'Bad request')
        self.id = user
        self.is_admin = False
        self.email = u''
        self.password_hash = u''

    def __iter__(self):
        yield 'username', self.id
        yield 'admin', self.is_admin
        yield 'email', self.email
