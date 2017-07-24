import os
import mysql.connector
import flask
from contextlib import closing
import design
import comment

app = flask.Flask(__name__)
app.config.from_json('config.json')

@app.teardown_appcontext
def close_db(error):
    if hasattr(flask.g, 'mysql_db'):
        flask.g.mysql_db.close()

@app.route('/')
def hello():
    return str(app.config['MYSQL'])
    #TODO : delete this!


@app.route('/design/<int:design_id>', methods=['GET'])
def get_design(design_id):
    mydesign = design.DesignbyID(design_id)
    if mydesign is None:
        return flask.json.jsonify(error = "Could not find design")
    else:
        return flask.json.jsonify({ 'design': dict(mydesign)})

def complete(designs):
    jdesigns = map(design.Design.serialize, designs)
    return flask.json.jsonify({'designs': jdesigns})

@app.route('/by/<name>/<int:start>/<int:num>')
def get_designer(name, start, num):
    if num < 1 or num > 50:
        flask.abort(400,'Bad design count')

    return complete(design.DesignByDesigner(name, start, num))

@app.route('/favorites/<name>/<int:start>/<int:num>')
def get_favorites(name, start, num):
    if num < 1 or num > 50:
        flask.abort(400,'Bad design count')

    return complete(design.DesignFavorites(name, start, num))

@app.route('/title/<int:start>/<int:num>')
def get_titles(start, num):
    if num < 1 or num > 50:
        flask.abort(400,'Bad design count')
    
    return complete(design.DesignByTitle(start, num))

@app.route('/titleindex/<title>')
def get_title_num(title):
    return flask.json.jsonify({'index': design.CountByTitle(title)})

@app.route('/random/<int:seed>/<int:start>/<int:num>')
def get_random(seed, start, num):
    if num < 1 or num > 50:
        flask.abort(400,'Bad design count')

    return complete(design.DesignByRandom(seed, start, num))

@app.route('/comments/<int:design_id>')
def get_comments(design_id):
    comments = comment.CommentsByDesign(design_id)
    jcomments = map(comment.Comment.serialize, comments)
    return flask.json.jsonify({'comments': jcomments})

