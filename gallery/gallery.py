import mysql.connector
import flask
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from contextlib import closing
import time
import design
import comment
import user
import upload
import gal_utils
from flask_cors import CORS

app = flask.Flask(__name__)
app.config.from_json('config.json')
CORS(app, supports_credentials=True)

@app.teardown_appcontext
def close_db(error):
    if hasattr(flask.g, 'mysql_db'):
        flask.g.mysql_db.close()

login_manager = LoginManager()
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return user.get(user_id)

@app.route(u'/design/<int:design_id>', methods=[u'GET'])
def get_design(design_id):
    mydesign, tags = design.DesignbyID(design_id)
    if mydesign is None:
        return flask.json.jsonify({ 'error': u'Could not find design'})
    else:
        return flask.json.jsonify({ 'design': dict(mydesign), 'tags': tags})

@app.route(u'/postdesign', methods=[u'POST'])
@login_required
def put_design():
    jdesign = flask.request.get_json()

    upload.trim(jdesign)

    if 'designid' in jdesign:
        design_id = jdesign['designid']
        if not isinstance(design_id, int) or design_id <= 0:
            flask.abort(400,u'Bad design id')
        d = design.DesignbyID(design_id)[0] # Get design from database

        if d is None:
            flask.abort(404,u'Design not found.')
        if not gal_utils.validateOwner(d.owner):
            flask.abort(403,u'Unauthorized.')
        
        d.init(**jdesign)                   # Merge in changes from POST
    else:
        d = design.Design(**jdesign)        # Create new design from POST

    d.normalize()
    id = d.save()
    if id is not None:
        return flask.json.jsonify({
            'getdesign': flask.url_for('get_design', design_id=id),
            'putimage': flask.url_for('upload_image', design_id=id, jpeg=0),
            'putcfdg': flask.url_for('upload_cfdg', design_id=id, name='name.cfdg')
        })
    else:
        if 'designid' in jdesign:
            return flask.json.jsonify({'error': u'Could not update design'})
        else:
            return flask.json.jsonify({'error': u'Could not insert design'})

@app.route(u'/image/<int:design_id>/<int:jpeg>', methods=[u'PUT'])
@login_required
def upload_image(design_id, jpeg):
    if design_id <= 0:
        flask.abort(400,u'Bad design id')
    png = flask.request.data
    if png is None or len(png) == 0:
        flask.abort(400,u'Bad PNG')
    upload.uploadpng(design_id, jpeg != 0, png)
    return flask.json.jsonify({'success': True})

@app.route(u'/cfdg/<int:design_id>/<name>', methods=[u'PUT'])
@login_required
def upload_cfdg(design_id, name):
    if design_id <= 0:
        flask.abort(400,u'Bad design id')
    cfdg = flask.request.data
    if cfdg is None or len(cfdg) == 0:
        flask.abort(400,u'Bad cfdg')
    upload.uploadcfdg(design_id, name, cfdg)
    return flask.json.jsonify({'success': True})

@app.route(u'/data/<dtype>/<int:design_id>', methods=[u'GET', u'HEAD'])
def get_data(dtype, design_id):
    if design_id <= 0:
        flask.abort(400,u'Bad design id')
    if dtype not in [u'cfdg', u'full', u'thumb', u'smallthumb', u'cclicense']:
        flask.abort(400,u'Bad data type')

    mydesign = design.DesignbyID(design_id)[0]
    if mydesign is None:
        flask.abort(404,u'Design not found')

    if dtype == u'cfdg':
        newurl = mydesign.filelocation.replace(u'//', u'/')
        if mydesign.variation:
            newurl += u'?variation=' + mydesign.variation
        return flask.redirect(newurl)

    prefix = design.S3_dir if mydesign.S3 else u''

    if dtype == u'full':
        newurl = prefix + mydesign.imagelocation
    elif dtype == u'thumb':
        newurl = prefix + mydesign.thumblocation
    elif dtype == u'smallthumb':
        newurl = prefix + mydesign.sm_thumblocation
    else:
        if mydesign.ccURI:
            newurl = mydesign.ccURI
        else:
            flask.abort(404,u'No CC license')
    if not mydesign.S3:     # S3 requires verbatim url but flask chokes on //
        newurl = newurl.replace(u'//', u'/')
    return flask.redirect(newurl)

def complete(designs, start, num, qpath):
    jdesigns = map(design.Design.serialize, designs[1])
    if not isinstance(jdesigns, list):      # Test for Python3 behavior
        jdesigns = list(jdesigns)
    
    pstart = 0 if start < num else start - num

    prevlink = u'/'.join([qpath, str(pstart), str(num)]) if start > 0 else u''
    nextlink = u'/'.join([qpath, str(start + num), str(num)]) if designs[0] == num else u''

    payload = {
        'querysize': designs[0], 
        'start': start,
        'count': num,
        'prevlink': prevlink,
        'nextlink': nextlink,
        'thislink': u'/'.join([qpath, str(start)]),
        'designs': jdesigns
    }

    return flask.json.jsonify(payload)

@app.route(u'/by/<name>/<int:start>/<int:num>')
def get_designer(name, start, num):
    if num < 1 or num > 50:
        flask.abort(400,u'Bad design count')

    return complete(design.DesignByDesigner(name, start, num), start, num, 
                    u'user/' + name)

@app.route(u'/faves/<name>/<int:start>/<int:num>')
def get_favorites(name, start, num):
    if num < 1 or num > 50:
        flask.abort(400,u'Bad design count')

    return complete(design.DesignFavorites(name, start, num), start, num, 
                    u'faves/' + name)

@app.route(u'/tag/<tag>/<int:start>/<int:num>')
def get_tagged(tag, start, num):
    if num < 1 or num > 50:
        flask.abort(400,u'Bad design count')
    if len(tag.split()) != 1 or tag != tag.strip():
        flask.abort(400,u'Bad tag')

    return complete(design.DesignTagged(tag, start, num), start, num, 
                    u'tag/' + tag)

@app.route(u'/tags')
def get_tags():
    return flask.json.jsonify({'tags': design.AllTags()})



@app.route(u'/popular/<int:start>/<int:num>')
def get_popular(start, num):
    if num < 1 or num > 50:
        flask.abort(400,u'Bad design count')

    return complete(design.DesignByPopularity(start, num), start, num, 
                    u'popular')


@app.route(u'/oldest/<int:start>/<int:num>')
def get_oldest(start, num):
    if num < 1 or num > 50:
        flask.abort(400,u'Bad design count')

    return complete(design.DesignByDate(True, start, num), start, num, 
                    u'oldest')

@app.route(u'/newest/<int:start>/<int:num>')
def get_newest(start, num):
    if num < 1 or num > 50:
        flask.abort(400,u'Bad design count')

    return complete(design.DesignByDate(False, start, num), start, num, 
                    u'newest')

@app.route(u'/title/<int:start>/<int:num>')
def get_titles(start, num):
    if num < 1 or num > 50:
        flask.abort(400,u'Bad design count')
    
    return complete(design.DesignByTitle(start, num), start, num, 
                    u'title')

@app.route(u'/titleindex/<title>')
def get_title_num(title):
    return flask.json.jsonify({'index': design.CountByTitle(title), 'title': title})

@app.route(u'/random/<int:seed>/<int:start>/<int:num>')
def get_random(seed, start, num):
    if num < 1 or num > 50:
        flask.abort(400,u'Bad design count')

    return complete(design.DesignByRandom(seed, start, num), start, num, 
                    u'random/' + str(seed))

@app.route(u'/comments/<int:design_id>')
def get_comments(design_id):
    comments = comment.CommentsByDesign(design_id)
    jcomments = map(comment.Comment.serialize, comments)
    if not isinstance(jcomments, list):     # Test for Python3 behavior
        jcomments = list(jcomments)
    return flask.json.jsonify({'designid': design_id, 'comments': jcomments})

@app.route(u'/updatecomment/<int:comment_id>', methods=[u'PUT'])
@login_required
def updateComment(comment_id):
    newText = flask.request.data
    cmt = comment.UpdateComment(comment_id, newText)
    return flask.json.jsonify(dict(cmt))

@app.route(u'/createcomment/<int:design_id>', methods=[u'PUT'])
@login_required
def createComment(design_id):
    newText = flask.request.data
    cmt = comment.CreateComment(design_id, newText)
    print dict(cmt)
    return flask.json.jsonify(dict(cmt))

@app.route(u'/deletecomment/<int:comment_id>', methods=[u'POST'])
@login_required
def deleteComment(comment_id):
    comment.DeleteComment(comment_id)
    return flask.json.jsonify({'commentid': comment_id})

@app.route(u'/login/<username>/<password>/<int:rememberme>', methods=[u'POST'])
def gal_login(username, password, rememberme):
    newuser = user.canLogin(username, password)
    if newuser is not None:
        newuser.lastlogin = int(time.time())
        newuser.numlogins += 1
        newuser.save(True)
        login_user(newuser, remember=(rememberme != 0))
        return flask.json.jsonify({'userinfo': dict(newuser)})

    return flask.json.jsonify({'userinfo': {}})

@app.route(u'/logout', methods=[u'POST'])
@login_required
def gal_logout():
    logout_user()
    return flask.json.jsonify({'logout_success': True})

@app.route(u'/userinfo', defaults={'username': ''})
@app.route(u'/userinfo/<username>')
def gal_userinfo(username):
    if username == '':
        u = current_user
        if not u.is_authenticated:
            return flask.json.jsonify({'userinfo': {}})
    else:
        u = user.get(username)

    if u is None:
        return flask.json.jsonify({'userinfo': {}})
    else:
        return flask.json.jsonify({'userinfo': dict(u)})

@app.route(u'/newbie')
def get_newbie():
    u = user.Newbie()
    if u is None:
        return flask.json.jsonify({'userinfo': {}})
    else:
        count, designs = design.DesignByDesigner(u.id, 0, 1)
        if len(designs) > 0:
            return flask.json.jsonify({ 'design': dict(designs[0])})
        else:
            return flask.json.jsonify({ 'design': {}})



@app.route(u'/notify/<int:notify>', methods=[u'POST'])
@login_required
def gal_set_notify(notify):
    u = current_user
    if not u.is_authenticated:
        return flask.json.jsonify({'userinfo': {}})

    u.notify = notify != 0
    u.save()
    return flask.json.jsonify({'userinfo': dict(u)})

@app.route(u'/uploads/<path:path>', methods=[u'GET'])
def getStaticFile(path):
    return flask.send_from_directory('uploads', path)

def ucomplete(users, start, num, qpath):
    jusers = map(user.MiniUser.serialize, users[1])
    if not isinstance(jusers, list):      # Test for Python3 behavior
        jusers = list(jusers)
    
    pstart = 0 if start < num else start - num

    prevlink = u'/'.join([qpath, str(pstart), str(num)]) if start > 0 else u''
    nextlink = u'/'.join([qpath, str(start + num), str(num)]) if users[0] == num else u''

    payload = {
        'querysize': users[0], 
        'start': start,
        'count': num,
        'prevlink': prevlink,
        'nextlink': nextlink,
        'thislink': u'/'.join([qpath, str(start), str(num)]),
        'users': jusers
    }

    return flask.json.jsonify(payload)

@app.route(u'/users/name/<int:start>/<int:num>')
def usersByName(start, num):
    if num < 1 or num > 50:
        flask.abort(400,u'Bad user count')

    return ucomplete(user.UsersByName(start,num), start, num, u'users/name')

@app.route(u'/users/joined/<int:start>/<int:num>')
def usersByJoindate(start, num):
    if num < 1 or num > 50:
        flask.abort(400,u'Bad user count')

    return ucomplete(user.UsersByJoindate(start,num), start, num, u'users/joined')

@app.route(u'/users/posts/<int:start>/<int:num>')
def usersByPosts(start, num):
    if num < 1 or num > 50:
        flask.abort(400,u'Bad user count')

    return ucomplete(user.UsersByPosts(start,num), start, num, u'users/posts')





