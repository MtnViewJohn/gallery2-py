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
from werkzeug.utils import secure_filename

def formfix(formdata):
    formdata.pop('S3', None)
    formdata.pop('owner', None)
    formdata.pop('filelocation', None)
    formdata.pop('imageversion', None)
    formdata.pop('imagelocation', None)
    formdata.pop('thumblocation', None)
    formdata.pop('smthumblocation', None)
    formdata.pop('numvotes', None)
    formdata.pop('uploaddate', None)
    if 'designid' in formdata:
        formdata['designid'] = int(formdata['designid'])
    if 'tiledtype' in formdata:
        formdata['tiled'] = int(formdata['tiledtype'])


def makeFilePath(basedir, owner):
    usermd5 = md5(owner.encode()).hexdigest()
    subdir1 = usermd5[0:2]
    subdir2 = usermd5[2:4]

    path = os.path.join(basedir, subdir1, subdir2, usermd5)
    if os.path.isdir(path):
        return path

    try:
        os.makedirs(path, 0o775)
    except OSError as e:
        if e.errno != errno.EEXIST:
            flask.abort(500,u'Cannot create directory: ' + path)
    return path


def uploadcfdg(basedir, design, file, name):
    db = gal_utils.get_db()
    oldcfdg = design.filelocation

    name = secure_filename(name)

    if u'.' not in name or name.rsplit('.', 1)[1].lower() != u'cfdg':
        name = u'design.cfdg'

    cfdgdir = os.path.join(makeFilePath(basedir, design.owner), str(design.designid))
    cfdgpath = os.path.join(cfdgdir, name)
    if not gal_utils.legalFilePath(cfdgpath, True):
        flask.abort(400,u'Bad cfdg file name.')

    if not os.path.isdir(cfdgdir):
        try:
            os.mkdir(cfdgdir, 0o775)
        except OSError as e:
            if e.errno != errno.EEXIST:
                flask.abort(500,u'Cannot create directory')

    try:
        file.save(cfdgpath)
    except OSError:
        flask.abort(500,u'Cannot write cfdg')

    if oldcfdg != cfdgpath:
        if os.path.isfile(oldcfdg):
            try:
                os.unlink(oldcfdg)
            except OSError:
                pass

    with closing(db.cursor(buffered=True)) as cursor:
        cursor.execute(u'UPDATE gal_designs SET filelocation=%s, '
                       u'whenuploaded=NOW() WHERE designid=%s', 
                       (cfdgpath,design.designid))
        if cursor.rowcount != 1:
            flask.abort(500,u'Cannot write database')


def uploadpng(basedir, design, file, jpeg):
    try:
        pngimage = Image.open(file.stream)
    except IOError:
        flask.abort(400, u'Cannot read PNG data.')

    db = gal_utils.get_db()

    files = []
    oldfiles = [design.imagelocation, design.thumblocation, design.sm_thumblocation]

    try:
        with closing(db.cursor(buffered=True)) as cursor:
            for file in oldfiles:
                if os.path.isfile(file):
                    try:
                        os.unlink(file)
                    except OSError:
                        pass

            path = makeFilePath(basedir, design.owner)
            filename = text(design.designid) + (u'.jpg' if jpeg else u'.png')
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
                           (imagepath,thumbpath,sm_thumbpath,design.designid))
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
            flask.abort(500,u'Image upload failed.')


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
        jpegimage = newimage.convert(u'RGB')
        jpegimage.save(filename, u'JPEG', quality=85, optimize=True)
    else:
        png8image = newimage.convert(u'P', palette=Image.ADAPTIVE)
        png8image.save(filename, u'PNG', optimize=True)



