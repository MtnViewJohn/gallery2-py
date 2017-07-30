import flask
import time
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
    with closing(db.cursor(buffered=True)) as cursor:
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

        cursor.execute('SELECT UNIX_TIMESTAMP(lastlogin), UNIX_TIMESTAMP(joinedon), '
                       'numposts, numlogins, notify_of_comments, ccURI '
                       'FROM gal_users WHERE screenname=%s', (username,))
        data = cursor.fetchone()
        if data is None or len(data) < 6 or not isinstance(data[0], int) or \
                not isinstance(data[1], int) or not isinstance(data[2], int) or \
                not isinstance(data[3], int) or not isinstance(data[4], int) or \
                not isinstance(data[5], unicode):
            return user

        user.lastlogin = data[0]
        user.joinedon = data[1]
        user.numposts = data[2]
        user.numlogins = data[3]
        user.notify = data[4] != 0
        user.ccURI = data[5]
        user.inGalUsers = True

        return user

class User(UserMixin):
    def __init__(self, user):
        if not isinstance(user, unicode):
            flask.abort(400, 'Bad request')
        self.id = user
        self.is_admin = False
        self.email = u''
        self.password_hash = u''
        self.lastlogin = int(time.time())
        self.joinedon = int(time.time())
        self.numposts = 0
        self.numlogins = 0
        self.notify = False
        self.ccURI = u''
        self.inGalUsers = False

    def __iter__(self):
        yield 'username', self.id
        yield 'admin', self.is_admin
        yield 'email', self.email
        yield 'lastlogin', self.lastlogin
        yield 'joinedon', self.joinedon
        yield 'numposts', self.numposts
        yield 'numlogins', self.numlogins
        yield 'notify', self.notify
        yield 'ccURI', self.ccURI

    def save(self, newLogin=False):
        db = gal_utils.get_db()
        with closing(db.cursor(buffered=True)) as cursor:
            if self.inGalUsers:
                lastlogin = 'lastlogin=NOW(), ' if newLogin else ''
                cursor.execute('UPDATE gal_users SET ' + lastlogin +
                               'numposts=%s, numlogins=%s, notify_of_comments=%s, '
                               'ccURI=%s WHERE screenname=%s',
                               (self.numposts,self.numlogins,
                                self.notify,self.ccURI,self.id))
            else:
                cursor.execute('INSERT INTO gal_users (screenname, email, '
                               'lastlogin, joinedon, numposts, numlogins, '
                               'notify_of_comments, ccURI) VALUES'
                               '(%s,%s,NOW(),NOW(),%s,%s,%s,%s)',
                               (self.id,self.email,self.numposts,
                                self.numlogins,1 if self.notify else 0,
                                self.ccURI))
                if cursor.rowcount == 1:
                    self.inGalUsers = True

            if cursor.rowcount != 1:
                flask.abort(500,'Cannot update user table')
