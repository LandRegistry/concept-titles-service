from flask import Flask, request
from flask.ext import restful
from flask.ext.basicauth import BasicAuth
from flask.ext.restful import reqparse
from flask.ext.sqlalchemy import SQLAlchemy
from flask import jsonify
import json
import logging
import os
from raven.contrib.flask import Sentry

app = Flask(__name__)

# Auth
if os.environ.get('BASIC_AUTH_USERNAME'):
    app.config['BASIC_AUTH_USERNAME'] = os.environ['BASIC_AUTH_USERNAME']
    app.config['BASIC_AUTH_PASSWORD'] = os.environ['BASIC_AUTH_PASSWORD']
    app.config['BASIC_AUTH_FORCE'] = True
    basic_auth = BasicAuth(app)

# Sentry exception reporting
if 'SENTRY_DSN' in os.environ:
    sentry = Sentry(app, dsn=os.environ['SENTRY_DSN'])

# Logging
@app.before_first_request
def setup_logging():
    if not app.debug:
        app.logger.addHandler(logging.StreamHandler())
        app.logger.setLevel(logging.INFO)

api = restful.Api(app)
if 'DATABASE_URL' in os.environ:
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ['DATABASE_URL'].replace('postgres://', 'postgresql+psycopg2://')
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql+psycopg2://titles:password@%s/titles' % os.environ['TITLESDB_1_PORT_5432_TCP'].replace('tcp://', '')
db = SQLAlchemy(app)

class TitleModel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title_number = db.Column( db.String(80) )
    postcode = db.Column( db.String(15), index=True)
    content = db.Column( db.Text() )

    def __init__(self, title_number, postcode, content ):
        self.title_number = title_number
        self.postcode = postcode
        self.content = content

    @property
    def serialize(self):
       """Return object data in easily serializeable format"""
       return {

           "title" : json.loads(self.content)

       }


class TitleRevisions(restful.Resource):

    def __init__(self):
        self.parser = reqparse.RequestParser()
        super(TitleRevisions, self).__init__()


    def post(self):
        content = json.loads(request.data)
        try:
            title_number = request.json["content"]["title_number"]

        except:
            return "", 400

        try:
            raw_postcode = request.json["content"]["postcode"]
            postcode = raw_postcode.replace(" ", "")
        except:
            postcode = ""

        title = TitleModel(title_number, postcode, json.dumps(request.json["content"]))

        existing = TitleModel.query.filter_by( title_number = title_number).first()

        if existing:
            db.session.delete( existing )
            db.session.add( title )
        else:
            db.session.add( title )
        db.session.commit()
        return "", 201



class Title(restful.Resource):
    def get(self, title_number):
        title = TitleModel.query.filter_by( title_number = title_number).first()

        if title:
            return jsonify( title.serialize )
        else:
            restful.abort( 404 )



class TitleList(restful.Resource):
    def get(self):
        if 'postcode' in request.args:
            raw_postcode = request.args['postcode']
            postcode = raw_postcode.replace(" ", "")
            titles = TitleModel.query.filter_by( postcode = postcode)
            return jsonify( titles = [i.serialize['title'] for i in titles] ) 
        else:   
            titles = TitleModel.query.all()
            return jsonify( titles = [i.serialize['title'] for i in titles] )



api.add_resource(TitleRevisions, '/titles-revisions')
api.add_resource(Title, '/titles/<string:title_number>')
api.add_resource(TitleList, '/titles')
db.create_all()

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=8004, debug=True)
