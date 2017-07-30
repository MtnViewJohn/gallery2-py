import flask
import datetime
from contextlib import closing
from flask_login import current_user
from werkzeug.exceptions import HTTPException
import gal_utils

class Design:
    S3_dir = "https://glyphic.s3.amazonaws.com/cfa/gallery/"
    Query_base = ("SELECT designid, owner, title, variation, tiled, ccURI, ccName, "
                      "ccImage, filelocation, S3, imageversion, imagelocation, "
                      "thumblocation, sm_thumblocation, numvotes, "
                      "whenuploaded, notes FROM gal_designs ")
    Query_base_d = ("SELECT d.designid, d.owner, d.title, d.variation, d.tiled, d.ccURI, "
                      "d.ccName, d.ccImage, d.filelocation, d.S3, d.imageversion, "
                      "d.imagelocation, d.thumblocation, d.sm_thumblocation, d.numvotes, "
                      "d.whenuploaded, d.notes FROM gal_designs AS d ")

    def init(self, **data):
        try:
            if 'designid' in data:
                id = int(data['designid'])
                if id < 0:
                    flask.abort(400,'Illegal Design ID.')
                if hasattr(self, 'designid') and self.designid != id:
                    flask.abort(400,'Design ID cannot be changed.')
                self.designid = id

            if 'owner' in data:
                if not gal_utils.legalOwner(data['owner']):
                    flask.abort(400,'Bad owner.')
                if hasattr(self, 'owner') and self.owner != data['owner']:
                    flask.abort(400,'Design owner cannot be changed.')
                self.owner = data['owner']

            if 'title' in data and len(data['title']) > 0:
                title = data['title'].strip()
                if (len(title) < 3 or len(title) > 100):
                    flask.abort(400,'The title must be between 3 and 100 characters.')
                self.title = title

            if 'variation' in data:
                var = data['variation'].strip()
                if not gal_utils.legalVariation(var):
                    flask.abort(400,'Illegal variation.')
                self.variation = var

            if 'tiled' in data:
                tiled = int(data['tiled'])
                if tiled < 0 or tiled > 3:
                    flask.abort(400,'Illegal tile type.')
                self.tiled = tiled

            if 'ccURI' in data and 'ccName' in data and 'ccImage' in data:
                if gal_utils.validateLicense(data):
                    self.ccURI = data['ccURI']
                    self.ccName = data['ccName']
                    self.ccImage = data['ccImage']
                else:
                    self.ccURI = ''
                    self.ccName = ''
                    self.ccImage = 'No license chosen'

            if 'filelocation' in data:
                if not gal_utils.legalFilePath(data['filelocation'], True):
                    flask.abort(400,'Illegal cfdg file specification.')
                self.filelocation = data['filelocation']

            if 'S3' in data:
                if data['S3'] == 'Y':
                    self.S3 = True
                elif data['S3'] == 'N':
                    self.S3 = False
                else:
                    flask.abort(400,'Illegal enum value for S3 flag.')

            if 'imageversion' in data:
                v = int(data['imageversion'])
                if v < 0: flask.abort(400,'Illegal image version.')
                data['imageversion'] = v

            if 'imagelocation' in data:
                if not gal_utils.legalFilePath(data['imagelocation'], False):
                    flask.abort(400,'Illegal image file specification.')
                self.imagelocation = data['imagelocation']

            if 'thumblocation' in data:
                if not gal_utils.legalFilePath(data['thumblocation'], False):
                    flask.abort(400,'Illegal image file specification.')
                self.thumblocation = data['thumblocation']

            if 'sm_thumblocation' in data:
                if not gal_utils.legalFilePath(data['sm_thumblocation'], False):
                    flask.abort(400,'Illegal image file specification.')
                self.sm_thumblocation = data['sm_thumblocation']

            if 'numvotes' in data:
                num = int(data['numvotes'])
                if num < 0: flask.abort(400,'Illegal vote count.')
                data['numvotes'] = num

            if 'whenuploaded' in data:
                if isinstance(data['whenuploaded'], datetime.datetime):
                    self.whenuploaded = data['whenuploaded']
                elif isinstance(data['whenuploaded'], unicode):
                    self.whenuploaded = datetime.datetime.strptime(
                        data['whenuploaded'], "%Y-%m-%dT%H:%M:%S")
                else:
                    flask.abort(400,'Upload date must be a datetime.')

            if 'notes' in data:
                if len(data['notes']) > 1000:
                    flask.abort(400,'Notes cannot be longer than 1000 bytes.')
                self.notes = data['notes'].decode('utf-8')

        except HTTPException:
            raise
        except:
            flask.abort(400,'Cannot instantiate a design.')

    def __init__(self, **data):
        self.init(**data)

    def serialize(self):
        return dict(self)

    def __iter__(self):
        yield 'designid', self.designid
        yield 'owner', self.owner
        yield 'title', self.title
        yield 'variation', self.variation
        yield 'tiled', self.tiled
        yield 'S3', u'Y' if self.S3 else u'N'
        yield 'filelocation', self.filelocation
        yield 'imagelocation', self.imagelocation
        yield 'thumblocation', self.thumblocation
        yield 'sm_thumblocation', self.sm_thumblocation
        yield 'imageversion', self.imageversion
        yield 'numvotes', self.numvotes
        yield 'notes', self.notes
        yield 'ccURI', self.ccURI
        yield 'ccName', self.ccName
        yield 'ccImage', self.ccImage
        yield 'whenuploaded', self.whenuploaded.isoformat()
        if hasattr(self, 'tags'):
            yield 'tags', self.tags
        if hasattr(self, 'fans'):
            yield 'fans', self.fans


    def normalize(self):
        try:
            if not hasattr(self, 'designid'):
                self.designid = 0       # INSERT new design
            elif self.designid < 0:
                flask.abort(400,'Bad design id.')

            if not hasattr(self, 'owner'):
                u = current_user
                if not u.is_authenticated:
                    flask.abort(400,'A design must have an owner.')
                self.owner = u.id
            if not gal_utils.legalOwner(self.owner):
                flask.abort(400,'Bad owner.')

            if not hasattr(self, 'title'):
                flask.abort(400,'A design must have a title.')
            elif self.title != self.title.strip() or len(self.title) < 3 or len(self.title) > 100:
                flask.abort(400,'Bad title.')

            if not hasattr(self, 'variation'):
                self.variation = u'';
            elif not gal_utils.legalVariation(self.variation):
                flask.abort(400,'Bad variation.')

            if not hasattr(self, 'tiled'):
                self.tiled = 0
            elif self.tiled < 0 or self.tiled > 3:
                flask.abort(400,'Bad tiling state.')

            if not hasattr(self, 'S3'):
                self.S3 = False
            elif type(self.S3) is not bool:
                flask.abort(400,'Bad S3 state.')

            if not hasattr(self, 'filelocation'):
                self.filelocation = u''
            elif not gal_utils.legalFilePath(self.filelocation, True):
                flask.abort(400,'Bad cfdg file path.')

            if not hasattr(self, 'imagelocation'):
                self.imagelocation = u''
            elif not gal_utils.legalFilePath(self.imagelocation, False):
                flask.abort(400,'Bad image file path.')

            if not hasattr(self, 'thumblocation'):
                self.thumblocation = u''
            elif not gal_utils.legalFilePath(self.thumblocation, False):
                flask.abort(400,'Bad image file path.')

            if not hasattr(self, 'sm_thumblocation'):
                self.sm_thumblocation = u''
            elif not gal_utils.legalFilePath(self.sm_thumblocation, False):
                flask.abort(400,'Bad image file path.')

            if not hasattr(self, 'imageversion'):
                self.imageversion = 0
            elif self.imageversion < 0:
                flask.abort(400,'Bad image version.')

            if not hasattr(self, 'numvotes'):
                self.numvotes = 0
            elif self.numvotes < 0:
                flask.abort(400,'Bad vote count.')

            if not hasattr(self, 'notes'):
                self.notes = u''
            elif len(self.notes) > 1000:
                flask.abort(400,'Notes cannot be longer than 1000 bytes.')

            if hasattr(self, 'ccURI') and hasattr(self, 'ccName') and hasattr(self, 'ccImage'):
                data = {
                    'ccURI': self.ccURI,
                    'ccName': self.ccName,
                    'ccImage': self.ccImage
                }
                if gal_utils.validateLicense(data):
                    self.ccURI = data['ccURI']
                    self.ccName = data['ccName']
                    self.ccImage = data['ccImage']
                else:
                    self.ccURI = ''
                    self.ccName = ''
                    self.ccImage = 'No license chosen'
            else:
                self.ccURI = ''
                self.ccName = ''
                self.ccImage = 'No license chosen'
                # TODO: when there are sessions then try the user default license

            if not hasattr(self, 'whenuploaded'):
                self.whenuploaded = datetime.datetime.now()

        except HTTPException:
            raise
        except:
            flask.abort(400,'Cannot normalize a design.')

    def archive(self):
        db = gal_utils.get_db()
        with closing(db.cursor(buffered=True)) as cursor:
            cursor.execute('SELECT S3 FROM gal_designs WHERE designid=%s', (self.designid,))
            if cursor.rowcount != 1: return False

            data = cursor.fetchone()
            if not isinstance(data[0], unicode): return False
            if data[0] == u'Y': return True

            cursor.execute('UPDATE gal_designs SET S3 = "Y" WHERE designid=%s', (self.designid,))
            return cursor.rowcount == 1

    def save(self):
        db = gal_utils.get_db()
        owner = current_user
        with closing(db.cursor(buffered=True)) as cursor:
            if self.designid == 0:
                cursor.execute('INSERT INTO gal_designs (owner, title, '
                    'variation, tiled, ccURI, ccName, ccImage, S3, '
                    'imageversion, numvotes, whenuploaded, notes) '
                    'VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), %s)',
                    (self.owner,self.title,self.variation,self.tiled,
                     self.ccURI,self.ccName,self.ccImage,u'Y' if self.S3 else u'N',
                     self.imageversion,self.numvotes,self.notes))
                self.designid = cursor.lastrowid

                if cursor.rowcount == 1:
                    owner.numposts += 1
            else:
                cursor.execute('UPDATE gal_designs SET title=%s, variation=%s, '
                    'tiled=%s, ccURI=%s, ccName=%s, ccImage=%s, S3=%s, '
                    'notes=%s WHERE designid=%s', 
                    (self.title,self.variation,self.tiled,self.ccURI,
                     self.ccName,self.ccImage,u'Y' if self.S3 else u'N',
                     self.notes,self.designid))
                print cursor.statement
                print cursor.rowcount

            if cursor.rowcount == 1:
                owner.ccURI = self.ccURI
                owner.save()
                return self.designid
        return None


def DesignbyID(design_id):
    if not isinstance(design_id, int) or design_id < 0:
        flask.abort(400, 'Bad request')

    db = gal_utils.get_db()
    with closing(db.cursor(dictionary=True, buffered=True)) as cursor:
        if design_id > 0:           # get actual design
            query = Design.Query_base + "WHERE designid=%s"
            cursor.execute(query, (design_id,))
        else:                       # get latest design
            query = Design.Query_base + "ORDER BY designid DESC LIMIT 1"
            cursor.execute(query)

        if cursor.rowcount != 1:
            return None

        design = Design(**cursor.fetchone())

        cursor.execute('SELECT n.name FROM gal_tags AS t, gal_tag_names AS n WHERE t.item=%s '
            'AND t.tag=n.id', (design_id,))
        if cursor.rowcount > 0:
            design.tags = []
            rows = cursor.fetchall()
            for row in rows:
                design.tags.append(row['name'])

        cursor.execute('SELECT screenname FROM gal_favorites WHERE designid=%s '
            'ORDER BY screenname', (design_id,))
        if cursor.rowcount > 0:
            design.fans = []
            rows = cursor.fetchall()
            for row in rows:
                design.fans.append(row['screenname'])

        design.normalize()
        return design

def complete(cursor):
    if cursor.rowcount == 0: return []

    rows = cursor.fetchall()

    ret = []
    for row in rows:
        design = Design(**row)
        design.normalize()
        ret.append(design)

    return ret


def DesignByDesigner(name, start, num):
    if not gal_utils.legalOwner(name) or \
        not isinstance(start, int) or not isinstance(num, int) or start < 0 or num < 1:
        flask.abort(400,'Bad request.')

    gal_utils.db = get_db()
    with closing(db.cursor(dictionary=True, buffered=True)) as cursor:
        cursor.execute(Design.Query_base + 'WHERE owner=%s ORDER BY whenuploaded ' 
            'DESC LIMIT %s,%s', (name,start,num))
        return complete(cursor)

def DesignByTitle(start, num):
    if not isinstance(start, int) or not isinstance(num, int) or start < 0 or num < 1:
        flask.abort(400,'Bad request.')

    gal_utils.db = get_db()
    with closing(db.cursor(dictionary=True, buffered=True)) as cursor:
        cursor.execute(Design.Query_base + 'ORDER BY title LIMIT %s,%s', (start,num))
        return complete(cursor)

def CountByTitle(title):
    if not isinstance(title, unicode) or len(title) < 3 or len(title) > 100:
        flask.abort(400,'Bad request.')

    db = gal_utils.get_db()
    with closing(db.cursor()) as cursor:
        cursor.execute('SELECT count(*) FROM gal_designs WHERE STRCMP(%s, title) > 0', (title,))
        datum = cursor.fetchone()
        if datum is None or type(datum[0]) is not int:
            flask.abort(400,'Bad request.')

        return datum[0]

def DesignByRandom(seed, start, num):
    if not isinstance(seed, int) or not isinstance(start, int) or \
            not isinstance(num, int) or start < 0 or num < 1:
        flask.abort(400,'Bad request.')

    db = gal_utils.get_db()
    with closing(db.cursor(dictionary=True, buffered=True)) as cursor:
        cursor.execute(Design.Query_base + 'ORDER BY RAND(%s) LIMIT %s,%s', (seed,start,num))
        return complete(cursor)

def DesignByDate(oldest, start, num):
    if not isinstance(oldest, bool) or not isinstance(start, int) or \
            not isinstance(num, int) or start < 0 or num < 1:
        flask.abort(400,'Bad request.')

    db = gal_utils.get_db()
    query = Design.Query_base + ('ORDER BY whenuploaded LIMIT %s,%s' if oldest
                            else 'ORDER BY whenuploaded DESC LIMIT %s,%s')
    with closing(db.cursor(dictionary=True, buffered=True)) as cursor:
        cursor.execute(query, (start,num))
        return complete(cursor)

def DesignFavorites(name, start, num):
    if not gal_utils.legalOwner(name) or not isinstance(start, int) or \
            not isinstance(num, int) or start < 0 or num < 1:
        flask.abort(400,'Bad request.')

    db = gal_utils.get_db()
    with closing(db.cursor(dictionary=True, buffered=True)) as cursor:
        cursor.execute(Design.Query_base_d + ', gal_favorites AS f WHERE '
            'f.screenname=%s AND f.designid = d.designid ORDER BY d.designid '
            'DESC LIMIT %s,%s', (name,start,num))
        return complete(cursor)









