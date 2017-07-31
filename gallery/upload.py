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

def trim(jdata):
    jdata.pop('S3', None)
    jdata.pop('owner', None)
    jdata.pop('filelocation', None)
    jdata.pop('imageversion', None)
    jdata.pop('imagelocation', None)
    jdata.pop('thumblocation', None)
    jdata.pop('sm_thumblocation', None)
    jdata.pop('numvotes', None)
    jdata.pop('uploaddate', None)


def makeFilePath(basedir, owner):
    usermd5 = md5(owner).hexdigest()
    subdir1 = usermd5[0:2]
    subdir2 = usermd5[2:4]

    path = basedir + os.sep + subdir1 + os.sep + subdir2 + os.sep + usermd5
    if os.path.isdir(path):
        return path

    try:
        os.makedirs(path, 0775)
        return path
    except OSError:
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
    cfdgpath = cfdgdir + os.sep + name
    if not gal_utils.legalFilePath(cfdgpath, True):
        flask.abort(400,'Bad cfdg file name.')

    if not os.path.isdir(cfdgdir):
        try:
            os.mkdir(cfdgdir, 0775)
        except OSError:
            flask.abort(500,'Cannot create directory')

    try:
        fd = os.open(cfdgpath, os.O_WRONLY + os.O_CREAT + os.O_TRUNC, 0775)
        os.write(fd, contents)
    except OSError:
        flask.abort(500,'Cannot write cfdg')
    finally:
        os.close(fd)

    if oldcfdg != cfdgpath:
        if os.path.isfile(oldcfdg):
            try:
                os.unlink(oldcfdg)
            except OSError:
                pass

    with closing(db.cursor()) as cursor:
        cursor.execute('UPDATE gal_designs SET filelocation=%s, '
                       'whenuploaded=NOW() WHERE designid=%s', 
                       (cfdgpath,designid))
        if cursor.rowcount != 1:
            flask.abort(500,'Cannot write database')


def uploadpng(design_id, jpeg, png):
    try:
        pngimage = Image.open(io.BytesIO(png))
    except IOError:
        flask.abort(400,'Cannot read PNG data')

    loggedIn = current_user.id
    db = gal_utils.get_db()
    files = []
    try:
        with closing(db.cursor(buffered=True)) as cursor:
            cursor.execute('SELECT imagelocation, thumblocation, sm_thumblocation '
                           'FROM gal_designs WHERE designid=%s AND owner=%s', 
                           (design_id, loggedIn))
            data = cursor.fetchone()
            if (data is None or not isinstance(data[0], unicode)
                             or not isinstance(data[1], unicode)
                             or not isinstance(data[2], unicode)):
                flask.abort(400,'Ownership issue.')
            
            for file in data:
                if os.path.isfile(file):
                    try:
                        os.unlink(file)
                    except OSError:
                        pass

            path = makeFilePath('uploads', loggedIn)
            filename = str(design_id) + ('.jpg' if jpeg else '.png')
            imagepath = path + os.sep + 'full_' + filename
            thumbpath = path + os.sep + 'thumb_' + filename
            sm_thumbpath = path + os.sep + 'sm_thumb_' + filename

            resample(pngimage, (800,800), imagepath, jpeg)
            files.append(imagepath)
            resample(pngimage, (300,300), thumbpath, jpeg)
            files.append(thumbpath)
            resample(pngimage, (100,100), sm_thumbpath, jpeg)
            files.append(sm_thumbpath)

            cursor.execute('UPDATE gal_designs SET imagelocation=%s, '
                           'thumblocation=%s, sm_thumblocation=%s,'
                           'S3="N", imageversion=imageversion+1 '
                           'WHERE designid=%s',
                           (imagepath,thumbpath,sm_thumbpath,design_id))
            if cursor.rowcount != 1:
                flask.abort(500,'Cannot write database')
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
            flask.abort(500,'Image upload failed')


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
        newimage.save(filename, "JPEG", quality=85, optimize=True)
    else:
        newimage.save(filename, "PNG", optimize=True)



