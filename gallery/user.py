import flask
import time
from flask_login import UserMixin
from contextlib import closing
import gal_utils
from passlib.apps import phpbb3_context
from passlib.hash import bcrypt
from gal_utils import text

def canLogin(username, password):
    if not gal_utils.legalOwner(username) or not isinstance(password, text):
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
        cursor.execute(u'SELECT user_password, user_rank, user_email FROM phpbb3_users '
                       u'WHERE username=%s', (username,))
        data = cursor.fetchone()
        if data is None or len(data) < 3 or not isinstance(data[1], int) or \
                not isinstance(data[0], bytearray) or not isinstance(data[2], bytearray):
            return None

        user = User(username)
        if hasattr(data[0], 'decode'):
            user.password_hash = data[0].decode('utf-8')
        else:
            user.password_hash = data[0]
        user.is_admin = data[1] == 1
        if hasattr(data[2], 'decode'):
            user.email = data[2].decode('utf-8')
        else:
            user.email = data[2]

        cursor.execute(u'SELECT UNIX_TIMESTAMP(lastlogin), UNIX_TIMESTAMP(joinedon), '
                       u'numposts, numlogins, notify_of_comments, ccURI '
                       u'FROM gal_users WHERE screenname=%s', (username,))
        data = cursor.fetchone()
        if data is None or len(data) < 6 or not isinstance(data[0], int) or \
                not isinstance(data[1], int) or not isinstance(data[2], int) or \
                not isinstance(data[3], int) or not isinstance(data[4], int) or \
                not isinstance(data[5], text):
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
        if not isinstance(user, text):
            flask.abort(400, u'Bad request')
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
                lastlogin = u'lastlogin=NOW(), ' if newLogin else u''
                cursor.execute(u'UPDATE gal_users SET ' + lastlogin +
                               u'numposts=%s, numlogins=%s, notify_of_comments=%s, '
                               u'ccURI=%s WHERE screenname=%s',
                               (self.numposts,self.numlogins,
                                self.notify,self.ccURI,self.id))
            else:
                cursor.execute(u'INSERT INTO gal_users (screenname, email, '
                               u'lastlogin, joinedon, numposts, numlogins, '
                               u'notify_of_comments, ccURI) VALUES'
                               u'(%s,%s,NOW(),NOW(),%s,%s,%s,%s)',
                               (self.id,self.email,self.numposts,
                                self.numlogins,1 if self.notify else 0,
                                self.ccURI))
                if cursor.rowcount == 1:
                    self.inGalUsers = True

            if cursor.rowcount != 1:
                flask.abort(500,u'Cannot update user table')

def Newbie():
    db = gal_utils.get_db()
    with closing(db.cursor(buffered=True)) as cursor:
        cursor.execute(u'SELECT screenname, email, UNIX_TIMESTAMP(lastlogin), '
                       u'UNIX_TIMESTAMP(joinedon), '
                       u'numposts, numlogins, notify_of_comments, ccURI '
                       u'FROM gal_users WHERE numposts >= 1 '
                       u'ORDER BY joinedon DESC LIMIT 1')
        data = cursor.fetchone()
        if (data is None or not isinstance(data[0], text) or 
                not isinstance(data[1], text) or not isinstance(data[4], int) or
                not isinstance(data[5], int) or not isinstance(data[6], int) or
                not isinstance(data[7], text)):
            return None

        user = User(data[0])
        user.email = data[1]
        user.lastlogin = data[2]
        user.joinedon = data[3]
        user.numposts = data[4]
        user.numlogins = data[5]
        user.notify = data[6] != 0
        user.ccURI = data[7]
        user.inGalUsers = True
        return user

class MiniUser:
    Query_base = (u'SELECT screenname, UNIX_TIMESTAMP(joinedon), numposts FROM '
                  u'gal_users WHERE numposts>0 ')

    def __init__(self, row):
        self.name = row[0]
        self.joinedon = row[1]
        self.numposts = row[2]

    def serialize(self):
        return dict(self)

    def __iter__(self):
        yield 'username', self.name
        yield 'joinedon', self.joinedon
        yield 'numposts', self.numposts


def complete(cursor):
    if cursor.rowcount == 0: return (0, [])

    rows = cursor.fetchall()

    ret = []
    for row in rows:
        try:
            user = MiniUser(row)
            ret.append(user)
        except:
            pass

    return (cursor.rowcount, ret)


def UsersByName(ascending, start, num):
    direction = u'ASC' if ascending else 'DESC'
    query = MiniUser.Query_base + u'ORDER BY screenname ' + direction + u' LIMIT %s,%s'
    db = gal_utils.get_db()
    with closing(db.cursor()) as cursor:
        cursor.execute(query, (start,num))
        return complete(cursor)

def UsersByJoindate(ascending, start, num):
    direction = u'ASC' if ascending else 'DESC'
    query = MiniUser.Query_base + u'ORDER BY joinedon ' + direction + u' LIMIT %s,%s'
    db = gal_utils.get_db()
    with closing(db.cursor()) as cursor:
        cursor.execute(query, (start,num))
        return complete(cursor)

def UsersByPosts(ascending, start, num):
    direction = u'ASC' if ascending else 'DESC'
    query = MiniUser.Query_base + u'ORDER BY numposts ' + direction + u', screenname LIMIT %s,%s'
    db = gal_utils.get_db()
    with closing(db.cursor()) as cursor:
        cursor.execute(query, (start,num))
        return complete(cursor)



