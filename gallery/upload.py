import os
import os.path
import io
import flask
from contextlib import closing
from flask_login import current_user
from PIL import Image
import gal_utils
from hashlib import md5
from werkzeug.exceptions import HTTPException
from gal_utils import text
#import traceback

def trim(jdata):
    jdata.pop('S3', None)
    jdata.pop('owner', None)
    jdata.pop('filelocation', None)
    jdata.pop('imageversion', None)
    jdata.pop('imagelocation', None)
    jdata.pop('thumblocation', None)
    jdata.pop('smthumblocation', None)
    jdata.pop('numvotes', None)
    jdata.pop('uploaddate', None)


def makeFilePath(basedir, owner):
    usermd5 = md5(owner.encode()).hexdigest()
    subdir1 = usermd5[0:2]
    subdir2 = usermd5[2:4]

    path = os.path.join(basedir, subdir1, subdir2, usermd5)
    if os.path.isdir(path):
        return path

    try:
        os.makedirs(path, 0o775)
        return path
    except OSError:
        flask.abort(500,u'Cannot create directory: ' + path)


def uploadcfdg(designid, name, contents):
    db = gal_utils.get_db()
    with closing(db.cursor(buffered=True)) as cursor:
        cursor.execute(u'SELECT filelocation, owner FROM gal_designs WHERE '
                       u'designid=%s', (designid,))
        data = cursor.fetchone()
        if (data is None or not isinstance(data[0], text) 
                         or not isinstance(data[1], text)):
            flask.abort(404,u'Design not found.')
        oldcfdg = data[0]
        owner = data[1]

    if not gal_utils.validateOwner(owner):
        flask.abort(403,u'Unauthorized.')

    cfdgdir = os.path.join(makeFilePath(u'uploads', owner), str(designid))
    cfdgpath = os.path.join(cfdgdir, name)
    if not gal_utils.legalFilePath(cfdgpath, True):
        flask.abort(400,u'Bad cfdg file name.')

    if not os.path.isdir(cfdgdir):
        try:
            os.mkdir(cfdgdir, 0o775)
        except OSError:
            flask.abort(500,u'Cannot create directory')

    try:
        fd = os.open(cfdgpath, os.O_WRONLY + os.O_CREAT + os.O_TRUNC, 0o775)
        os.write(fd, contents)
    except OSError:
        flask.abort(500,u'Cannot write cfdg')
    finally:
        os.close(fd)

    if oldcfdg != cfdgpath:
        if os.path.isfile(oldcfdg):
            try:
                os.unlink(oldcfdg)
            except OSError:
                pass

    with closing(db.cursor()) as cursor:
        cursor.execute(u'UPDATE gal_designs SET filelocation=%s, '
                       u'whenuploaded=NOW() WHERE designid=%s', 
                       (cfdgpath,designid))
        if cursor.rowcount != 1:
            flask.abort(500,u'Cannot write database')


def uploadpng(design_id, jpeg, png):
    try:
        pngimage = Image.open(io.BytesIO(png))
    except IOError:
        flask.abort(400,u'Cannot read PNG data')

    db = gal_utils.get_db()
    files = []
    try:
        with closing(db.cursor(buffered=True)) as cursor:
            cursor.execute(u'SELECT imagelocation, thumblocation, sm_thumblocation, '
                           u'owner FROM gal_designs WHERE designid=%s', 
                           (design_id,))
            data = cursor.fetchone()
            if (data is None or not isinstance(data[0], text)
                             or not isinstance(data[1], text)
                             or not isinstance(data[2], text)
                             or not isinstance(data[3], text)):
                flask.abort(404,u'Design not found.')

            owner = data[3]
            oldfiles = data[0:2]
            if not gal_utils.validateOwner(owner):
                flask.abort(403,u'Unauthorized.')

            for file in oldfiles:
                if os.path.isfile(file):
                    try:
                        os.unlink(file)
                    except OSError:
                        pass

            path = makeFilePath(u'uploads', owner)
            filename = text(design_id) + (u'.jpg' if jpeg else u'.png')
            imagepath = os.path.join(path, u'full_' + filename)
            thumbpath = os.path.join(path, u'thumb_' + filename)
            sm_thumbpath = os.path.join(path, u'sm_thumb_' + filename)

            resample(pngimage, (800,800), imagepath, jpeg)
            files.append(imagepath)
            resample(pngimage, (300,300), thumbpath, jpeg)
            files.append(thumbpath)
            resample(pngimage, (100,100), sm_thumbpath, jpeg)
            files.append(sm_thumbpath)

            cursor.execute(u'UPDATE gal_designs SET imagelocation=%s, '
                           u'thumblocation=%s, sm_thumblocation=%s,'
                           u'S3="N", imageversion=imageversion+1 '
                           u'WHERE designid=%s',
                           (imagepath,thumbpath,sm_thumbpath,design_id))
            if cursor.rowcount != 1:
                flask.abort(500,u'Cannot write database')
    except Exception as e:
        for file in files:
            if os.path.isfile(file):
                try:
                    os.unlink(file)
                except OSError:
                    pass

        if isinstance(e, HTTPException):
            raise
        else:
            #traceback.print_exc()
            flask.abort(500,u'Image upload failed')


def resample(image, newsize, filename, jpeg):
    oldsize = image.size
    frac = (float(oldsize[0])/newsize[0], float(oldsize[1])/newsize[1])
    finalsize = oldsize

    if frac[0] > frac[1]:
        if finalsize[0] > newsize[0]:
            finalsize = (newsize[0], int(oldsize[1]/frac[0]))
    else:
        if finalsize[1] > newsize[1]:
            finalsize = (int(oldsize[0]/frac[1]), newsize[1])

    newimage = image.resize(finalsize, Image.BICUBIC)

    if jpeg:
        newimage.save(filename, u'JPEG', quality=85, optimize=True)
    else:
        newimage.save(filename, u'PNG', optimize=True)



