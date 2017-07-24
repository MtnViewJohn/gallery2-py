import flask
import datetime
from contextlib import closing
import gal_utils

class Comment:
    Query_base = 'SELECT screenname, comment, whenposted, commentid FROM gal_comments '

    def init(self, **data):
        try:
            if 'screenname' in data:
                if not gal_utils.legalOwner(data['screenname']):
                    flask.abort(400,'Bad screenname.')
                if hasattr(self, 'screenname') and self.screenname != data['screenname']:
                    flask.abort(400,'Comment owner cannot be changed.')
                self.screenname = data['screenname']

            if 'comment' in data:
                self.comment = data['comment'].decode('utf-8')

            if 'whenposted' in data:
                if type(data['whenposted']) is not datetime.datetime:
                    flask.abort(400,'Comment date must be a datetime.')
                self.whenposted = data['whenposted']

            if 'commentid' in data:
                id = int(data['commentid'])
                if id < 0:
                    flask.abort(400,'Illegal Comment ID.')
                if hasattr(self, 'commentid') and self.commentid != id:
                    flask.abort(400,'Comment ID cannot be changed.')
                self.commentid = id

        except:
            flask.abort(400,'Cannot instantiate a comment.')

    def __init__(self, **data):
        self.init(**data)

    def serialize(self):
        return dict(self)

    def __iter__(self):
        yield 'screenname', self.screenname
        yield 'comment', self.comment
        yield 'whenposted', self.whenposted
        yield 'commentid', self.commentid

    def normalize(self):
        try:
            if not hasattr(self, 'commentid'):
                self.commentid = 0      # insert new comment
            elif self.commentid < 0:
                flask.abort(400,'Bad comment id.')

            if not hasattr(self, 'comment'):
                flask.abort(400,'Empty comments are not allowed.')

            if not hasattr(self, 'whenposted'):
                self.whenposted = datetime.now()

            if not hasattr(self, 'screenname'):
                flask.abort(400,'A comment must have an owner.')
                # TODO: get owner from session if logged in
            elif not gal_utils.legalOwner(self.screenname):
                flask.abort(400,'Bad owner.')

        except:
            flask.abort(400,'Cannot instantiate a comment.')

def CommentsByDesign(designid):
    if type(designid) is not int or designid < 1:
        flask.abort(400, 'Bad request')

    db = gal_utils.get_db()
    with closing(db.cursor(dictionary=True, buffered=True)) as cursor:
        cursor.execute(Comment.Query_base + 'WHERE designid=%s ORDER BY whenposted', (designid,))
        if cursor.rowcount == 0: return []

        rows = cursor.fetchall()

        ret = []
        for row in rows:
            comment = Comment(**row)
            comment.normalize()
            ret.append(comment)

        return ret


