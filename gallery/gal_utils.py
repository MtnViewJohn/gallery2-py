import flask
from flask_login import current_user
import mysql.connector
import mysql.connector.pooling
from mysql.connector.constants import ClientFlag
import sys

PY3 = sys.version_info[0] == 3
PY2 = sys.version_info[0] == 2

if PY3:
    text = str
else:
    text = unicode

def get_db():
    db = getattr(flask.g, 'mysql_db', None)
    if db is None:
        mysql_cfg = flask.current_app.config['MYSQL']
        cnxpool = mysql.connector.pooling.MySQLConnectionPool(
            client_flags=[ClientFlag.FOUND_ROWS], **mysql_cfg)
        db = flask.g.mysql_db =  cnxpool.get_connection()
    return db

def legalOwner(owner):
    if not isinstance(owner, text): return False
    if owner == u'': return False
    try:
        pos = next(i for i,x in enumerate(owner) if x in u'#&;:`|*?~<>^()[]{}$\\@%,/\'"-\t\f\r\n')
        return False
    except:
        return True

def validateOwner(owner):
    if not current_user.is_authenticated:
        return False
    return  current_user.is_admin or current_user.id == owner
    

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
        if not filepath.endswith((u'.jpg', u'.jpeg', u'.png')): return False
    try:
        pos = next(i for i,x in enumerate(owner) if x in u'&#;`|*?~<>^()[]{}$\, \x0A\xFF')
        return False
    except:
        return True

