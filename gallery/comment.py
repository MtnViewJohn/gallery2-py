import flask
import time
from contextlib import closing
from flask_login import current_user
from werkzeug.exceptions import HTTPException
import gal_utils
from flask_login import current_user

class Comment:
    Query_base = (u'SELECT screenname, comment, UNIX_TIMESTAMP(whenposted) AS postdate, '
                  u'commentid FROM gal_comments ')

    def init(self, **data):
        try:
            if 'screenname' in data:
                if not gal_utils.legalOwner(data['screenname']):
                    flask.abort(400,u'Bad screenname.')
                if hasattr(self, 'screenname') and self.screenname != data['screenname']:
                    flask.abort(400,u'Comment owner cannot be changed.')
                self.screenname = data['screenname']

            if 'comment' in data:
                if hasattr(data['comment'], 'decode'):
                    self.comment = data['comment'].decode('utf-8')
                else:
                    self.comment = data['comment']

            if 'postdate' in data:
                if not isinstance(data['postdate'], int):
                    flask.abort(400,u'Comment date must be a POSIX timestamp int.')
                elif data['postdate'] < 1104566400:
                    flask.abort(400,u'Comment date before 2005')
                elif hasattr(self, 'postdate') and self.postdate != data['postdate']:
                    flask.abort(400,u'Comment post date cannot be changed.')
                self.postdate = data['postdate']

            if 'commentid' in data:
                id = int(data['commentid'])
                if id < 0:
                    flask.abort(400,u'Illegal Comment ID.')
                if hasattr(self, 'commentid') and self.commentid != id:
                    flask.abort(400,u'Comment ID cannot be changed.')
                self.commentid = id

        except HTTPException:
            raise
        except:
            flask.abort(400,u'Cannot instantiate a comment.')

    def __init__(self, **data):
        self.init(**data)

    def serialize(self):
        return dict(self)

    def __iter__(self):
        yield 'screenname', self.screenname
        yield 'comment', self.comment
        yield 'commentmd', gal_utils.translate2Markdown(self.comment)
        yield 'postdate', self.postdate
        yield 'commentid', self.commentid

    def normalize(self):
        try:
            if not hasattr(self, 'commentid'):
                self.commentid = 0      # insert new comment
            elif self.commentid < 0:
                flask.abort(400,u'Bad comment id.')

            if not hasattr(self, 'comment'):
                flask.abort(400,u'Empty comments are not allowed.')

            if hasattr(self, 'postdate'):
                if self.postdate < 1104566400:
                    flask.abort(400,u'Comment date before 2005')
            else:
                self.whenposted = int(time.time())

            if not hasattr(self, 'screenname'):
                u = current_user
                if not u.is_authenticated:
                    flask.abort(400,u'A comment must have an owner.')
                self.screenname = u.id
            if not gal_utils.legalOwner(self.screenname):
                flask.abort(400,u'Bad owner.')

        except HTTPException:
            raise
        except:
            flask.abort(400,u'Cannot instantiate a comment.')

def CommentsByDesign(designid):
    if not isinstance(designid, int) or designid < 1:
        flask.abort(400, u'Bad design id')

    db = gal_utils.get_db()
    with closing(db.cursor(dictionary=True, buffered=True)) as cursor:
        cursor.execute(Comment.Query_base + u'WHERE designid=%s ORDER BY whenposted', (designid,))
        if cursor.rowcount == 0: return []

        rows = cursor.fetchall()

        ret = []
        for row in rows:
            comment = Comment(**row)
            comment.normalize()
            ret.append(comment)

        return ret

def CommentById(commentid):
    if not isinstance(commentid, int) or commentid < 1:
        flask.abort(400, u'Bad comment id')

    db = gal_utils.get_db()
    with closing(db.cursor(dictionary=True, buffered=True)) as cursor:
        cursor.execute(Comment.Query_base + u'WHERE commentid=%s', (commentid,))
        if cursor.rowcount != 1:
            flask.abort(404, u'Comment not in database')

        row = cursor.fetchone()
        comment = Comment(**row)
        comment.normalize()
        return comment

def UpdateComment(commentid, newComment):
    if not isinstance(commentid, int) or commentid < 1:
        flask.abort(400, u'Bad comment id')

    db = gal_utils.get_db()
    with closing(db.cursor(buffered=True)) as cursor:
        cursor.execute(u"UPDATE gal_comments SET comment = %s WHERE screenname=%s AND commentid=%s",
            (newComment,current_user.id,commentid))
        if cursor.rowcount != 1:
            flask.abort(403, u'Cannot update comment')
        return CommentById(commentid)

def CreateComment(designid, newComment):
    if not isinstance(designid, int) or designid < 1:
        flask.abort(400, u'Bad design id')

    db = gal_utils.get_db()
    with closing(db.cursor(buffered=True)) as cursor:
        cursor.execute(u'INSERT INTO gal_comments (screenname, designid, whenposted, comment) '
            u'VALUES (%s, %s, NOW(), %s)', (current_user.id,designid,newComment))
        commentid = cursor.lastrowid
        if cursor.rowcount != 1:
            flask.abort(403, u'Cannot add comment')
        return CommentById(commentid)

def DeleteComment(commentid):
    if not isinstance(commentid, int) or commentid < 1:
        flask.abort(400, u'Bad comment id')

    db = gal_utils.get_db()
    with closing(db.cursor(buffered=True)) as cursor:
        cursor.execute(u"DELETE FROM gal_comments WHERE screenname=%s AND commentid=%s",
            (current_user.id,commentid))
        if cursor.rowcount != 1:
            flask.abort(403, u'Cannot delete comment')



