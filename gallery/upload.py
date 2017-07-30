import os
import os.path
import flask
from contextlib import closing
from flask_login import current_user
import gal_utils
from hashlib import md5

def makeFilePath(basedir, owner):
    usermd5 = md5(owner).hexdigest()
    subdir1 = usermd5[0:2]
    subdir2 = usermd5[2:2]

    path = basedir + os.sep + subdir1 + os.sep + subdir2 + os.sep + usermd5
    if os.path.isdir(path):
        return path

    try:
        os.makedirs(path, 0775)
        return path
    except os.error:
        flask.abort(500,'Cannot create directory')


def uploadcfdg(designid, name, contents):
    loggedIn = current_user.id
    db = gal_utils.get_db()
    with closing(db.cursor(buffered=True)) as cursor:
        cursor.execute('SELECT filelocation FROM gal_designs WHERE '
                       'designid=%s AND owner=%s', (designid, loggedIn))
        data = cursor.fetchone()
        if data is None or not isinstance(data[0], unicode):
            flask.abort(400,'Ownership issue.')
        oldcfdg = data[0]


    cfdgdir = makeFilePath('uploads', loggedIn) + os.sep + str(designid)
    cfdgpath = cfdgdir + os.dir + name
    if not gal_utils.legalFilePath(cfdgpath, True):
        flask.abort(400,'Bad cfdg file name.')

    if not os.path.isdir(cfdgdir):
        try:
            os.mkdir(cfdgdir, 0775)
        except OSerror:
            flask.abort(500,'Cannot create directory')

    try:
        with closing(os.open(cfdgpath, os.O_WRONLY + os.O_CREAT + os.O_TRUNC, 
                             0775)) as fd:
            os.write(fd, contents)
    except OSerror:
        flask.abort(500,'Cannot write cfdg')

    if oldcfdg != cfdgpath:
        if os.path.isfile(oldcfdg):
            try:
                os.unlink(oldcfdg)
            except OSerror:
                pass

    with closing(db.cursor()) as cursor:
        cursor.execute('UPDATE gal_designs SET filelocation=%s, '
                       'whenuploaded=NOW() WHERE designid=%s', 
                       (cfdgpath,designid))
        if cursor.rowcount != 1:
            flask.abort(500,'Cannot write database')




