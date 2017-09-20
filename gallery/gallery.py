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
from gal_utils import text
from flask_cors import CORS
from werkzeug.exceptions import HTTPException
from werkzeug.datastructures import FileStorage
import io
import base64

app = flask.Flask(__name__)
app.config.from_json('config.json')
if app.debug:
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
    mydesign = design.DesignbyID(design_id)
    if mydesign is None:
        return flask.json.jsonify({ 'error': u'Could not find design'})
    else:
        return flask.json.jsonify({ 'design': dict(mydesign)})

@app.route(u'/postdesign', methods=[u'POST'])
def put_design():
    try:
        if flask.request.is_json:
            fdesign = flask.request.get_json()
        else:
            fdesign = dict(flask.request.form.iteritems())

        if not isinstance(fdesign, dict):
            return gal_utils.errorUrl(u'No data received.')
        if not current_user.is_authenticated:
            if u'screenname' not in fdesign or u'password' not in fdesign:
                return gal_utils.errorUrl(u'Not logged in/no user credentils provided.')
            
            newuser = user.canLogin(fdesign['screenname'], fdesign['password'])
            if newuser is None:
                return gal_utils.errorUrl(u'Incorrect login credentials.')
            login_user(newuser, remember=False)

        upload.formfix(fdesign)

        if 'tags' in fdesign:
            new_tags = fdesign['tags']
        else:
            new_tags = []

        cfdgPresent  = (u'cfdgfile' in flask.request.files and 
                        flask.request.files[u'cfdgfile'].filename != u'')
        imagePresent = (u'imagefile' in flask.request.files and 
                        flask.request.files[u'imagefile'].filename != u'')
        cfdgJson  = (flask.request.is_json and 'cfdgfile' in fdesign
                     and fdesign['cfdgfile'] is not None)
        imageJson = (flask.request.is_json and 'imagefile' in fdesign
                     and fdesign['imagefile'] is not None)

        if u'designid' in fdesign and fdesign['designid'] != 0:
            design_id = fdesign['designid']
            if not isinstance(design_id, int) or design_id <= 0:
                return gal_utils.errorUrl(u'Bad design id.')
            d = design.DesignbyID(design_id) # Get design from database
            orig_tags = d.tags
            orig_tagids = d.tagids

            if d is None:
                return gal_utils.errorUrl(u'Design not found.')
            if not gal_utils.validateOwner(d.owner):
                return gal_utils.errorUrl(u'Unauthorized to edit this design.')
            
            d.init(**fdesign)                   # Merge in changes from POST
        else:
            if not ((cfdgPresent and imagePresent) or (cfdgJson and imageJson)):
                return gal_utils.errorUrl(u'Upload missing cfdg or PNG file.')
            orig_tags = []
            orig_tagids = []
            d = design.Design(**fdesign)        # Create new design from POST

        d.normalize()
        id = d.save()

        if id is not None:
            design.UpdateTags(id, orig_tags, orig_tagids, new_tags)
            jpeg = 'compression' not in fdesign or fdesign['compression'] != u'PNG-8'
            if cfdgPresent:
                upload.uploadcfdg(d, flask.request.files['cfdgfile'])
            if imagePresent:
                upload.uploadpng(d, flask.request.files['imagefile'], jpeg)
            if cfdgJson:
                cfdgtext = base64.standard_b64decode(fdesign['cfdgfile']['contents'])
                cfdgfile = FileStorage(stream = io.BytesIO(cfdgtext), name = 'cfdgfile',
                                        filename = fdesign['cfdgfile']['filename'])
                upload.uploadcfdg(d, cfdgfile)
            if imageJson:
                pngdata = base64.standard_b64decode(fdesign['imagefile']['contents'])
                pngfile = FileStorage(stream = io.BytesIO(pngdata), name = 'imagefile',
                                        filename = fdesign['imagefile']['filename'])
                upload.uploadpng(d, pngfile, jpeg)
            newurl = u'http://localhost:8000/main.html#design/' + text(id)

            if flask.request.is_json:
                return flask.json.jsonify({'design': dict(d), 'tags': design.AllTags()})
            else:
                return flask.redirect(newurl, code=303)
        else:
            if flask.request.is_json:
                flask.abort(500, u'Failed to save design.')
            else:
                return gal_utils.errorUrl(u'Failed to save design.')

    except HTTPException as e:
        print e
        if flask.request.is_json:
            raise
        else:
            return gal_utils.errorUrl(text(e))
    except Exception as e:
        print e
        if flask.request.is_json:
            raise
        else:
            return gal_utils.errorUrl(u'Unknown error occured.')

@app.route(u'/delete/<int:design_id>', methods=[u'POST'])
@login_required
def deleteDesign(design_id):
    design.DeleteDesign(design_id)
    return flask.json.jsonify({'designid': design_id})


@app.route(u'/data/<dtype>/<int:design_id>', methods=[u'GET', u'HEAD'])
def get_data(dtype, design_id):
    if design_id <= 0:
        flask.abort(400,u'Bad design id')
    if dtype not in [u'cfdg', u'full', u'thumb', u'smallthumb', u'cclicense']:
        flask.abort(400,u'Bad data type')

    mydesign = design.DesignbyID(design_id)
    if mydesign is None:
        flask.abort(404,u'Design not found')

    if app.debug:
        serverurl = u''
    else:
        serverurl = flask.request.url_root.rstrip('/').rstrip('abcdefghijklmnopqrstuvwxyz')

    if dtype == u'cfdg':
        newurl = serverurl + mydesign.filelocation.replace(u'//', u'/')
        if mydesign.variation:
            newurl += u'?variation=' + mydesign.variation
        return flask.redirect(newurl)

    prefix = design.S3_dir if mydesign.S3 else serverurl

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

    # S3 requires verbatim url but flask chokes on //
    if not newurl.startswith(u'http'):
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

@app.route(u'/by/<name>/<int:start>/<int:num>', defaults={'ccOnly': False})
@app.route(u'/ccby/<name>/<int:start>/<int:num>', defaults={'ccOnly': True})
def get_designer(name, start, num, ccOnly):
    if num < 1 or num > 50:
        flask.abort(400,u'Bad design count')

    return complete(design.DesignByDesigner(name, start, num, ccOnly), start, num, 
                    u'user/' + name)

@app.route(u'/faves/<name>/<int:start>/<int:num>', defaults={'ccOnly': False})
@app.route(u'/ccfaves/<name>/<int:start>/<int:num>', defaults={'ccOnly': True})
def get_favorites(name, start, num, ccOnly):
    if num < 1 or num > 50:
        flask.abort(400,u'Bad design count')

    return complete(design.DesignFavorites(name, start, num, ccOnly), start, num, 
                    u'faves/' + name)

@app.route(u'/tag/<tag>/<int:start>/<int:num>', defaults={'ccOnly': False})
@app.route(u'/cctag/<tag>/<int:start>/<int:num>', defaults={'ccOnly': True})
def get_tagged(tag, start, num, ccOnly):
    if num < 1 or num > 50:
        flask.abort(400,u'Bad design count')
    if len(tag.split()) != 1 or tag != tag.strip():
        flask.abort(400,u'Bad tag')

    return complete(design.DesignTagged(tag, start, num, ccOnly), start, num, 
                    u'tag/' + tag)

@app.route(u'/tags')
def get_tags():
    return flask.json.jsonify({'tags': design.AllTags()})



@app.route(u'/popular/<int:start>/<int:num>', defaults={'ccOnly': False})
@app.route(u'/ccpopular/<int:start>/<int:num>', defaults={'ccOnly': True})
def get_popular(start, num, ccOnly):
    if num < 1 or num > 50:
        flask.abort(400,u'Bad design count')

    return complete(design.DesignByPopularity(start, num, ccOnly), start, num, 
                    u'popular')


@app.route(u'/oldest/<int:start>/<int:num>', defaults={'ccOnly': False})
@app.route(u'/ccoldest/<int:start>/<int:num>', defaults={'ccOnly': True})
def get_oldest(start, num, ccOnly):
    if num < 1 or num > 50:
        flask.abort(400,u'Bad design count')

    return complete(design.DesignByDate(True, start, num, ccOnly), start, num, 
                    u'oldest')

@app.route(u'/newest/<int:start>/<int:num>', defaults={'ccOnly': False})
@app.route(u'/ccnewest/<int:start>/<int:num>', defaults={'ccOnly': True})
def get_newest(start, num, ccOnly):
    if num < 1 or num > 50:
        flask.abort(400,u'Bad design count')

    return complete(design.DesignByDate(False, start, num, ccOnly), start, num, 
                    u'newest')

@app.route(u'/title/<int:start>/<int:num>', defaults={'ccOnly': False})
@app.route(u'/cctitle/<int:start>/<int:num>', defaults={'ccOnly': True})
def get_titles(start, num, ccOnly):
    if num < 1 or num > 50:
        flask.abort(400,u'Bad design count')
    
    return complete(design.DesignByTitle(start, num, ccOnly), start, num, 
                    u'title')

@app.route(u'/titleindex/<title>', defaults={'ccOnly': False})
@app.route(u'/cctitleindex/<title>', defaults={'ccOnly': True})
def get_title_num(title, ccOnly):
    return flask.json.jsonify({'index': design.CountByTitle(title, ccOnly), 'title': title})

@app.route(u'/random/<int:seed>/<int:start>/<int:num>', defaults={'ccOnly': False})
@app.route(u'/ccrandom/<int:seed>/<int:start>/<int:num>', defaults={'ccOnly': True})
def get_random(seed, start, num, ccOnly):
    if num < 1 or num > 50:
        flask.abort(400,u'Bad design count')

    return complete(design.DesignByRandom(seed, start, num, ccOnly), start, num, 
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
    return flask.json.jsonify(dict(cmt))

@app.route(u'/deletecomment/<int:comment_id>', methods=[u'POST'])
@login_required
def deleteComment(comment_id):
    comment.DeleteComment(comment_id)
    return flask.json.jsonify({'commentid': comment_id})

@app.route(u'/addfave/<int:design_id>', methods=[u'POST'])
@login_required
def addFave(design_id):
    newfaves = design.AddFave(design_id)
    return flask.json.jsonify({'designid': design_id, 'faves': newfaves})

@app.route(u'/deletefave/<int:design_id>', methods=[u'POST'])
@login_required
def deleteFave(design_id):
    newfaves = design.DeleteFave(design_id)
    return flask.json.jsonify({'designid': design_id, 'faves': newfaves})

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
        count, designs = design.DesignByDesigner(u.id, 0, 1, False)
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

    return ucomplete(user.UsersByName(True,start,num), start, num, u'users/name')

@app.route(u'/users/joined/<int:start>/<int:num>')
def usersByJoindate(start, num):
    if num < 1 or num > 50:
        flask.abort(400,u'Bad user count')

    return ucomplete(user.UsersByJoindate(True,start,num), start, num, u'users/joined')

@app.route(u'/users/posts/<int:start>/<int:num>')
def usersByPosts(start, num):
    if num < 1 or num > 50:
        flask.abort(400,u'Bad user count')

    return ucomplete(user.UsersByPosts(True,start,num), start, num, u'users/posts')

@app.route(u'/users/name_d/<int:start>/<int:num>')
def usersByNameDesc(start, num):
    if num < 1 or num > 50:
        flask.abort(400,u'Bad user count')

    return ucomplete(user.UsersByName(False,start,num), start, num, u'users/name_d')

@app.route(u'/users/joined_d/<int:start>/<int:num>')
def usersByJoindateDesc(start, num):
    if num < 1 or num > 50:
        flask.abort(400,u'Bad user count')

    return ucomplete(user.UsersByJoindate(False,start,num), start, num, u'users/joined_d')

@app.route(u'/users/posts_d/<int:start>/<int:num>')
def usersByPostsDesc(start, num):
    if num < 1 or num > 50:
        flask.abort(400,u'Bad user count')

    return ucomplete(user.UsersByPosts(False,start,num), start, num, u'users/posts_d')





