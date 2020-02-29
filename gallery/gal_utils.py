import flask
from flask_login import current_user
import mysql.connector
import mysql.connector.pooling
from mysql.connector.constants import ClientFlag
import sys

PY3 = sys.version_info[0] >= 3

if PY3:
    text = str
else:
    text = unicode

def get_db():
    db = getattr(flask.g, 'mysql_db', None)
    if db is None:
        mysql_cfg = flask.current_app.config['MYSQL']
        cnxpool = mysql.connector.pooling.MySQLConnectionPool(
            client_flags=[ClientFlag.FOUND_ROWS], autocommit=True, **mysql_cfg)
        db = flask.g.mysql_db =  cnxpool.get_connection()
        db.autocommit = True
    return db

def legalOwner(owner):
    if not isinstance(owner, text): return False
    if owner == u'': return False
    try:
        pos = next(i for i,x in enumerate(owner) if x in u'#&;:`|*?~<>^()[]{}$\\@%,/"-\t\f\r\n')
        return False
    except:
        return True

def validateOwner(owner):
    if not current_user.is_authenticated:
        return False
    return  current_user.is_admin or current_user.id == owner
    

def validateTagger(owner):
    if not current_user.is_authenticated:
        return False
    return  current_user.is_tagger or current_user.id == owner


def legalVariation(var):
    if not isinstance(var, text): return False
    if len(var) > 6: return False
    for c in var:
        if not c.isalpha(): return False
    return True

def validateLicense(data):
    if (data['ccURI'].find(u'creativecommons.org') == -1 or
        data['ccImage'].find(u'creativecommons.org') == -1):
        return False
    if len(data['ccName']) < 3: return False
    if data['ccURI'].startswith(u'http:'):
        data['ccURI'] = data['ccURI'].replace(u'http:', u'https:', 1)
    if data['ccImage'].startswith(u'http:'):
        data['ccImage'] = data['ccImage'].replace(u'http:', u'https:', 1)
    return True

def legalFilePath(filepath, cfdgfile):
    if not isinstance(filepath, text): return False
    if filepath.find(u'..') != -1: return False
    if not filepath.startswith(u'uploads/'): return False
    if cfdgfile:
        if not filepath.endswith(u'.cfdg'): return False
    else:
        if not filepath.endswith((u'.jpg', u'.jpeg', u'.png', u'.gif')): return False
    try:
        pos = next(i for i,x in enumerate(owner) if x in u'&#;`|*?~<>^()[]{}$\, \x0A\xFF')
        return False
    except:
        return True


def translate2Markdown(legacy):
    out = u''
    pos = 0
    while True:
        cpos = legacy.find(u'[code]', pos)
        lpos = legacy.find(u'[link ', pos)

        if cpos == -1 and lpos == -1:
            return out + legacy[pos:]

        code = lpos == -1 or (cpos != -1 and cpos < lpos)

        xpos = cpos if code else lpos
        out += legacy[pos:xpos]

        if code:
            pos = cpos + 6
            if out and out[-1] != u'\n':
                out += u'\n'
            out += u'```cfdg\n'
            if pos < len(legacy) and legacy[pos] == u'\n':
                pos = pos + 1
            cpos = legacy.find(u'[/code]', pos)
            if cpos == -1:
                return out + legacy[pos:] + u'\n```\n'
            out += legacy[pos:cpos]
            pos = cpos + 7
            if out[-1] != u'\n':
                out += u'\n'
            out += u'```\n'
            if pos < len(legacy) and legacy[pos] == u'\n':
                pos = pos + 1
        else:
            pos = lpos + 6
            lpos = legacy.find(u']', pos)
            if lpos == -1:
                return out
            link = legacy[pos:lpos]
            pos = lpos + 1
            lpos = legacy.find(u'[/link]', pos)
            if lpos == -1:
                out += u'[' + legacy[pos:] + u']'
            else:
                out += u'[' + legacy[pos:lpos] + u']'
                pos = lpos + 7
            out += u'(' + linkCvt(link) + u')'
            if lpos == -1:
                return out

validChars = bytearray('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-._~!$&\'()*+,;=?', 'utf-8')

def encodeFragment(ustr):
    bytesutf8 = bytearray(ustr, 'utf-8')
    ret = u''
    for b in bytesutf8:
        if b in validChars:
            ret += chr(b)
        else:
            ret += u'%{:02X}'.format(b)
    return ret

def linkCvt(oldLink):
    oldLink = oldLink.lstrip()
    if oldLink.startswith(u'user:'):
        return u'#user/' + encodeFragment(oldLink[5:].strip())
    if oldLink.startswith(u'design:'):
        return u'#design/' + oldLink[7:].strip()
    return oldLink.strip()

def loginUrl():
    if flask.current_app.debug:
        url = u'http://localhost:8000/main.html#newest/0'
    else:
        url = u'../../gallery2/index.html#newest/0/'
    return flask.redirect(url, code = 303)


