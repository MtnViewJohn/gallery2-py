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
from werkzeug.exceptions import HTTPException
from werkzeug.datastructures import FileStorage
import io
import os
import os.path
import base64
import translate
import random
import sys

app = flask.Flask(__name__)
app.config.from_json('config.json')
os.chdir(app.config['UPLOAD_DIR'])
if app.debug:
    import logging
    from flask_cors import CORS
    CORS(app, supports_credentials=True)
    logging.getLogger('flask_cors').level = logging.DEBUG
PY3 = sys.version_info[0] >= 3

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
        #time.sleep(5)
        return flask.json.jsonify({ 'design': dict(mydesign)})

@app.route(u'/cfdg/<int:design_id>', methods=[u'GET', u'HEAD'])
def get_cfdg(design_id):
    if design_id <= 0:
        flask.abort(400,u'Bad design id')

    mydesign = design.DesignbyID(design_id)
    if mydesign is None:
        flask.abort(404,u'Design not found')

    try:
        fullpath = os.path.join(app.root_path, mydesign.filelocation)
        with open(fullpath, mode = u'rb') as myfile:
            cfdgtxt = myfile.read().decode(u'utf-8')

        return flask.json.jsonify({ u'cfdg': cfdgtxt,
                                    'design': dict(mydesign)})
    except Exception:
        flask.abort(500, u'Failed to load cfdg file.')


@app.route(u'/postdesigntags', methods=[u'POST'])
def jpost_designtags():
    jdesign = flask.request.get_json()
    newdesigntags = put_designtags(jdesign)
    return flask.json.jsonify({'design': dict(newdesigntags), 'tags': design.AllTags()})

@app.route(u'/fpostdesigntags', methods=[u'POST'])
def fpost_designtags():
    if PY3:
        fdesign = dict(flask.request.form.items())
    else:
        fdesign = dict(flask.request.form.iteritems())
    if 'tags' in fdesign:
        fdesign['tags'] = fdesign['tags'].split(u' ')
    newdesigntags = put_designtags(fdesign)
    return flask.json.jsonify({'design': dict(newdesigntags), 'tags': design.AllTags()})

def put_designtags(jdesign):
    if not isinstance(jdesign, dict):
        flask.abort(400, u'No data received.')
    if not current_user.is_authenticated:
        flask.abort(401, u'Not logged in/no user credentils provided.')

    upload.formfix(jdesign)
    jdesign.pop('title', None)
    jdesign.pop('variation', None)
    jdesign.pop('tiled', None)
    jdesign.pop('notes', None)
    jdesign.pop('cclicense', None)
    jdesign.pop('ccURI', None)
    jdesign.pop('ccName', None)
    jdesign.pop('ccImage', None)

    design_id = jdesign.get('designid', 0)
    new_tags = jdesign.get('tags', [])
    if not isinstance(design_id, int) or design_id <= 0:
        flask.abort(400, u'Bad design id.')
    if not isinstance(new_tags, list):
        flask.abort(400, u'Bad tags.')
    if not all(isinstance(elem, text) for elem in new_tags):
        flask.abort(400, u'Bad tags.')

    d = design.DesignbyID(design_id) # Get design from database
    if d is None:
            flask.abort(404, u'Design not found.')
    orig_tags = d.tags
    orig_tagids = d.tagids

    if not gal_utils.validateTagger(d.owner):
        flask.abort(401, u'Unauthorized to edit tags for this design.')
    
    d.init(**jdesign)                   # Merge in changes from POST
    d.normalize()
    id = d.save()

    if id is not None:
        design.UpdateTags(id, orig_tags, orig_tagids, new_tags)
        newdesign = design.DesignbyID(id)
        return newdesign
    else:
        flask.abort(500, u'Failed to save design.')



@app.route(u'/postdesign', methods=[u'POST'])
def jpost_design():
    jdesign = flask.request.get_json()
    newdesign = put_design(jdesign)
    return flask.json.jsonify({'design': dict(newdesign[1]), 'tags': design.AllTags()})

@app.route(u'/fpostdesign', methods=[u'POST'])
def fpost_design():
    if PY3:
        fdesign = dict(flask.request.form.items())
    else:
        fdesign = dict(flask.request.form.iteritems())
    if 'tags' in fdesign:
        fdesign['tags'] = fdesign['tags'].split(u' ')
    newdesign = put_design(fdesign)
    return flask.json.jsonify({'design': dict(newdesign[1]), 'tags': design.AllTags()})

def put_design(fdesign):
        if not isinstance(fdesign, dict):
            flask.abort(400, u'No data received.')
        if not current_user.is_authenticated:
            if u'screenname' not in fdesign or u'password' not in fdesign:
                flask.abort(401, u'Not logged in/no user credentils provided.')
            
            newuser = user.canLogin(fdesign['screenname'], fdesign['password'])
            if newuser is None:
                flask.abort(401, u'Incorrect login credentials.')
            login_user(newuser, remember=False)

        upload.formfix(fdesign)

        design_id = fdesign.get('designid', 0)
        new_tags = fdesign.get('tags', [])
        if not isinstance(design_id, int) or design_id < 0:
            flask.abort(400, u'Bad design id.')
        if not isinstance(new_tags, list):
            flask.abort(400, u'Bad tags.')
        if not all(isinstance(elem, text) for elem in new_tags):
            flask.abort(400, u'Bad tags.')

        cfdgPresent  = (u'cfdgfile' in flask.request.files and 
                        flask.request.files[u'cfdgfile'].filename != u'')
        imagePresent = (u'imagefile' in flask.request.files and 
                        flask.request.files[u'imagefile'].filename != u'')
        cfdgJson  = (flask.request.is_json and 'cfdgfile' in fdesign
                     and fdesign['cfdgfile'] is not None)
        imageJson = (flask.request.is_json and 'imagefile' in fdesign
                     and fdesign['imagefile'] is not None)

        if design_id != 0:
            d = design.DesignbyID(design_id) # Get design from database
            if d is None:
                flask.abort(404, u'Design not found.')
            orig_tags = d.tags
            orig_tagids = d.tagids

            if not gal_utils.validateOwner(d.owner):
                flask.abort(401, u'Unauthorized to edit this design.')
            
            d.init(**fdesign)                   # Merge in changes from POST
        else:
            if not ((cfdgPresent and imagePresent) or (cfdgJson and imageJson)):
                flask.abort(400, u'Upload missing cfdg or PNG file.')
            orig_tags = []
            orig_tagids = []
            d = design.Design(**fdesign)        # Create new design from POST

        d.normalize()
        id = d.save()

        if id is not None:
            try:
                design.UpdateTags(id, orig_tags, orig_tagids, new_tags)
                jpeg = 'compression' not in fdesign or fdesign['compression'] != u'PNG-8'
                if cfdgPresent:
                    upload.uploadcfdg(d, flask.request.files['cfdgfile'], flask.request.files['cfdgfile'].filename)
                if imagePresent:
                    upload.uploadpng(d, flask.request.files['imagefile'], jpeg)
                if cfdgJson:
                    cfdgtext = base64.standard_b64decode(fdesign['cfdgfile']['contents'])
                    cfdgfile = FileStorage(stream = io.BytesIO(cfdgtext), name = 'cfdgfile',
                                            filename = fdesign['cfdgfile']['filename'])
                    upload.uploadcfdg(d, cfdgfile, fdesign['cfdgfile']['filename'])
                if imageJson:
                    pngdata = base64.standard_b64decode(fdesign['imagefile']['contents'])
                    pngfile = FileStorage(stream = io.BytesIO(pngdata), name = 'imagefile',
                                            filename = fdesign['imagefile']['filename'])
                    upload.uploadpng(d, pngfile, jpeg)
                newurl = u'http://localhost:8000/main.html#design/' + text(id)
                newdesign = design.DesignbyID(id)

                return (newurl, newdesign)
            except:
                design.UnaddDesign(id)
                raise
        else:
            flask.abort(500, u'Failed to save design.')


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
    #time.sleep(5)
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
    if seed == 0:
        seed = random.randint(1,1000000000)
    if num < 1 or num > 50:
        flask.abort(400,u'Bad design count')

    return complete(design.DesignByRandom(seed, start, num, ccOnly), start, num, 
                    u'random/' + str(seed))

@app.route(u'/popularrandom/<int:seed>/<int:start>/<int:num>', defaults={'ccOnly': False})
@app.route(u'/ccpopularrandom/<int:seed>/<int:start>/<int:num>', defaults={'ccOnly': True})
def get_poprandom(seed, start, num, ccOnly):
    if num < 1 or num > 50:
        flask.abort(400,u'Bad design count')

    return complete(design.DesignByRandomPopular(seed, start, num, ccOnly), start, num, 
                    u'random/' + str(seed))

@app.route(u'/auxinfo/<int:design_id>')
def getFans(design_id):
    fans = design.GetFans(design_id)
    tags, ids = design.GetTags(design_id)
    sz = design.GetSize(design_id)
    if sz is None:
        return flask.json.jsonify({'fans': fans, 'tags': tags})
    else:
        return flask.json.jsonify({'fans': fans, 'tags': tags, 'imagesize': sz})

def completexlate(cfdg2txt):
    try:
        with closing(translate.Translator(cfdg2txt)) as cfdgxlate:
            cfdgxlate.translate()
            return flask.json.jsonify({ u'cfdg3txt': cfdgxlate.output.getvalue(), 
                                        u'colortarget': cfdgxlate.colortarget,
                                        u'discards' : cfdgxlate.extraChars})
    except Exception as e:
        flask.abort(400, text(e))

@app.route(u'/translate/<int:design_id>')
def translateDesign(design_id):
    if design_id <= 0:
        flask.abort(400,u'Bad design id')

    mydesign = design.DesignbyID(design_id)
    if mydesign is None:
        flask.abort(404,u'Design not found')
    #else:
    try:
        fullpath = os.path.join(app.root_path, mydesign.filelocation)
        with open(fullpath, mode = u'rb') as myfile:
            cfdg2txt = myfile.read().decode(u'utf-8')
    except Exception:
        flask.abort(500, u'Failed to load cfdg file.')
    return completexlate(cfdg2txt)



@app.route(u'/translate', methods = [u'POST'])
def translateCfdg2():
    try:
        cfdg2txt = flask.request.data.decode(u'utf-8')
    except Exception as e:
        flask.abort(400, u'Unicode error.')
    return completexlate(cfdg2txt)


@app.route(u'/comments/<int:design_id>')
def get_comments(design_id):
    comments = comment.CommentsByDesign(design_id)
    jcomments = map(comment.Comment.serialize, comments)
    if not isinstance(jcomments, list):     # Test for Python3 behavior
        jcomments = list(jcomments)
    return flask.json.jsonify({'designid': design_id, 'comments': jcomments})

@app.route(u'/updatecomment/<int:comment_id>', methods=[u'PUT', u'POST'])
@login_required
def updateComment(comment_id):
    newText = flask.request.data
    cmt = comment.UpdateComment(comment_id, newText)
    return flask.json.jsonify(dict(cmt))

@app.route(u'/createcomment/<int:design_id>', methods=[u'PUT', u'POST'])
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
        newuser.unseen = design.NewerDesigns(newuser.lastdesign)
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
        u.unseen = design.NewerDesigns(u.lastdesign)
        return flask.json.jsonify({'userinfo': dict(u)})

@app.route(u'/unseen')
def getUnseen():
    unseen = 0
    u = current_user
    if u.is_authenticated:
        unseen = design.NewerDesigns(u.lastdesign)
    return flask.json.jsonify({'unseen': unseen})

@app.route(u'/newdesigns', methods=[u'POST'])
@login_required
def newdesigns():
    u = current_user
    count, designs = design.DesignByDate(False, 0, 1, False)
    if count != 1 or len(designs) != 1:
        return flask.json.jsonify({'newdesigns': 0})
    else:
        u.lastdesign = designs[0].designid
        u.save()
        return flask.json.jsonify({'newdesigns': 1})

@app.route(u'/newbie')
def get_newbie():
    u = user.Newbie(1)
    if len(u) != 1:
        return flask.json.jsonify({'userinfo': {}})
    else:
        count, designs = design.DesignByDesigner(u[0].id, 0, 1, False)
        if len(designs) > 0:
            return flask.json.jsonify({ 'design': dict(designs[0])})
        else:
            return flask.json.jsonify({ 'design': {}})



@app.route(u'/newbies/<int:ignore>/<int:count>')
def get_newbies(ignore, count):
    if count < 1 or count > 50:
        flask.abort(400,u'Bad user count')
    users = user.Newbie(count)
    designs = []
    for u in users:
        count, udesigns = design.DesignByDesigner(u.id, 0, 1, False)
        if len(udesigns) > 0:
            designs.append(dict(udesigns[0]))

    return flask.json.jsonify({'designs': designs})



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





