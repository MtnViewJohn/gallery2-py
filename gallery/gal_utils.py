import flask
import urlparse
import mysql.connector

def get_db():
    db = getattr(flask.g, 'mysql_db', None)
    if db is None:
        mysql_cfg = flask.current_app.config['MYSQL']
        db = flask.g.mysql_db =  mysql.connector.connect(**mysql_cfg)
    return db

def legalOwner(owner):
    if not isinstance(owner, unicode): return False
    if owner == '': return False
    try:
        pos = next(i for i,x in enumerate(owner) if x in '#&;:`|*?~<>^()[]{}$\\@%,/\'"- \t\f\r\n')
        return False
    except:
        return True

def legalVariation(var):
    if not isinstance(var, unicode): return False
    if len(var) > 6: return False
    for c in var:
        if not c.isalpha(): return False
    return True

def validateLicense(data):
    URIparts = urlparse.urlparse(data['ccURI'])
    imageparts = urlparse.urlparse(data['ccImage'])
    if URIparts.netloc.find('creativecommons.org') == -1 or \
       imageparts.netloc.find('creativecommons.org') == -1:
        return False
    if len(data['ccName']) < 3: return False
    if URIparts.scheme == 'http':
        data['ccURI'] = data['ccURI'].replace('http:', 'https:', 1)
    if imageparts.scheme == 'http':
        data['ccImage'] = data['ccImage'].replace('http:', 'https:', 1)
    return True

def legalFilePath(filepath, cfdgfile):
    if not isinstance(filepath, unicode): return False
    if filepath.find('..') != -1: return False
    if not filepath.startswith('uploads/'): return False
    if cfdgfile:
        if not filepath.endswith('.cfdg'): return False
    else:
        if not filepath.endswith(('.jpg', '.jpeg', '.png')): return False
    try:
        pos = next(i for i,x in enumerate(owner) if x in '&#;`|*?~<>^()[]{}$\, \x0A\xFF')
        return False
    except:
        return True

