###############################
####### SETUP (OVERALL) #######
###############################

## Import statements
# Import statements
import os
import json
import requests
import time
import hashlib
import ast

from flask import Flask, render_template, session, redirect, request, url_for, flash
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, HiddenField,PasswordField, BooleanField, ValidationError
from wtforms.validators import Required, Length, Email, Regexp, EqualTo
from flask_migrate import Migrate, MigrateCommand
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.types import JSON

# Imports for login management
from flask_login import LoginManager, login_required, logout_user, login_user, UserMixin, current_user
from werkzeug.security import generate_password_hash, check_password_hash

from flask_script import Manager, Shell

## App setup code
app = Flask(__name__)





app.config['SECRET_KEY'] = 'hardtoguessstringfromsi364thisisnotsupersecurebutitsok'

# TODO: Update this to your database URI
print(os.environ.get('DATABASE_URL'))
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL') or "postgresql://priscillamnunez@localhost:5432/finals"
app.config['SQLALCHEMY_COMMIT_ON_TEARDOWN'] = True
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

app.debug = True

## All app.config values

# Login configurations setup
login_manager = LoginManager()
login_manager.session_protection = 'strong'
login_manager.login_view = 'login'
login_manager.init_app(app) # set up login manager

manager = Manager(app)

## Statements for db setup (and manager setup if using Manager)
db = SQLAlchemy(app)

migrate = Migrate(app, db)
manager.add_command('db', MigrateCommand)



######################################
######## HELPER FXNS (If any) ########
######################################

def is_valid_year(form, field):
    if int(field.data) >=1990 and int(field.data) <=2019:
        return True
    raise ValidationError('Please Enter a valid year between 1990 and 2019')

def is_year(form, field):
    if field.data and field.data.isdigit():
        return True
    raise ValidationError('Please Enter a valid year')

## DB load function
## Necessary for behind the scenes login manager that comes with flask_login capabilities! Won't run without this.
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id)) # returns User object or None

def get_or_create_user(username, password):
    """Always returns a Gif instance"""
    user = User.query.filter_by(username=username).first()
    if not user:
        user = User(username=username, password=password)
        db.session.add(user)
        db.session.commit()
    return user

def get_or_create_search(searchStartYear, userId):
    """Always returns a Gif instance"""
    search = SearchYear.query.filter_by(searchStartYear=searchStartYear).first()
    if not search:
        search = SearchYear(searchStartYear=searchStartYear)
        db.session.add(search)
        db.session.commit()
    user = User.query.get(int(userId))
    user.searches.append(search)
    db.session.commit()
    return search  




##################
##### MODELS #####
##################

# Special model for users to log in
class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(255), unique=True, index=True)
    searches = db.relationship("SearchYear",
                           secondary="user_searches",
                           backref='users', lazy='dynamic')
    password_hash = db.Column(db.String(128))

    @property
    def password(self):
        raise AttributeError('password is not a readable attribute')

    @password.setter
    def password(self, password):
        self.password_hash = generate_password_hash(password)

    def verify_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def __repr__(self):
        return "{} (ID: {})".format(self.username, self.id)

class SearchYear(db.Model):
    __tablename__ = "searches"
    id = db.Column(db.Integer,primary_key=True)
    searchStartYear = db.Column(db.String(64))

class Like(db.Model):
    __tablename__ = "likes"
    id = db.Column(db.Integer,primary_key=True)
    userId = db.Column(db.Integer, db.ForeignKey('users.id'))
    comic = db.Column(JSON)

class Bookmark(db.Model):
    __tablename__ = "bookmarks"
    id = db.Column(db.Integer,primary_key=True)
    userId = db.Column(db.Integer, db.ForeignKey('users.id'))
    comic = db.Column(JSON)


UserSearch = db.Table('user_searches', db.Column('userId', db.Integer,db.ForeignKey('users.id'),
                                                nullable=False),
                                    db.Column('search_year_id', db.Integer,db.ForeignKey('searches.id'),
                                                nullable=False))

###################
###### FORMS ######
###################

class SearchForm(FlaskForm):
    searchStartYear = StringField("Please enter a search start year for marvels movie collections.",validators=[Required(),is_year, is_valid_year])
    submit = SubmitField()

class EditSearchForm(FlaskForm):
    searchStartYear = StringField("",validators=[Required(), is_valid_year])
    submit = SubmitField('Update')

class LikeForm(FlaskForm):
    movie = HiddenField("hidden")
    submit = SubmitField("Like")

class BookmarkForm(FlaskForm):
    movie = HiddenField("hidden")
    submit = SubmitField("bookmark")

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[Required(), Length(1,64)])
    password = PasswordField('Password', validators=[Required()])
    remember_me = BooleanField('Keep me logged in')
    submit = SubmitField('Log In')

class RegistrationForm(FlaskForm):
    username = StringField('Username:',validators=[Required(),Length(1,64),Regexp('^[A-Za-z][A-Za-z0-9_.]*$',0,'Username must have only letters, numbers, dots or underscores')])
    password = PasswordField('Password:',validators=[Required(),EqualTo('password2',message="Passwords must match")])
    password2 = PasswordField("Confirm Password:",validators=[Required()])
    submit = SubmitField('Register User')

    #Additional checking methods for the form
    def validate_email(self,field):
        if User.query.filter_by(email=field.data).first():
            raise ValidationError('Email already registered.')

    def validate_username(self,field):
        if User.query.filter_by(username=field.data).first():
            raise ValidationError('Username already taken')

class DeleteSearchForm(FlaskForm):
    submit = SubmitField("Delete")

#######################
###### VIEW FXNS ######
#######################

@app.route('/login',methods=["GET","POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user is not None and user.verify_password(form.password.data):
            login_user(user, form.remember_me.data)
            return redirect(request.args.get('next') or url_for('search'))
        flash('Invalid username or password.')
    return render_template('login.html',form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out')
    return redirect(url_for('home'))

@app.route('/register',methods=["GET","POST"])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        get_or_create_user(username=form.username.data,password=form.password.data)
        flash('You can now log in!')
        return redirect(url_for('login'))
    return render_template('register.html',form=form)


@app.route('/', methods = ["POST", "GET"])
def home():
    if hasattr(current_user, 'username'):
        return redirect(url_for('search'))
    return render_template('index.html')


@app.route('/search', methods = ["POST", "GET"])
@login_required
def search():
    results = []
    form = SearchForm()
    form2 = LikeForm()
    form3 = BookmarkForm()

    if form.validate_on_submit():
        searchStartYear = form.searchStartYear.data
        get_or_create_search(searchStartYear, current_user.id)
        
        baseUrl = 'https://gateway.marvel.com:443/v1/public'

        ts= time.time();
        publicKey = 'b5d493b7c3c88ab7de81562a4478702c'
        privateKey = 'b49c0f9c09df1d78105d0abea0dbcda4b7146141'
        hash = hashlib.md5(('{}{}{}').format(ts,privateKey, publicKey).encode('utf-8')).hexdigest()
        comics = requests.get('{}/comics'.format(baseUrl), 
            params= {
                "startYear": searchStartYear,
                "orderBy": "onsaleDate",
                "apikey": publicKey,
                "hash": hash,
                "ts": ts,
                "offset": 0
            })
        json_format = json.loads(comics.text)
        results = json_format['data']['results']
    errors = [v for v in form.errors.values()]
    if len(errors) > 0:
        print(len(errors))
        flash("!!!! ERRORS IN FORM SUBMISSION - " + str(errors))
    
    return render_template('search.html', form=form , form2=form2, form3=form3, results=results)


@app.route('/like', methods = ["POST"])
@login_required
def like_movie():
    username = current_user.username
    form = LikeForm()
    comic = form.movie.data
    newlike = Like(comic=comic, userId=current_user.id)
    db.session.add(newlike)
    db.session.commit()
    return redirect(url_for('user_likes'))

@app.route('/bookmark', methods = ["POST"])
@login_required
def bookmark_movie():
    username = current_user.username
    form = BookmarkForm()
    comic = form.movie.data
    newbookmark = Bookmark(comic=comic, userId=current_user.id)
    db.session.add(newbookmark)
    db.session.commit()
    return redirect(url_for("user_bookmarks"))


@app.route('/users')
@login_required
def all_users():
    username = current_user.username
    users = User.query.all()
    return render_template('name_example.html',users=users, username=username)

@app.route('/bookmarks')
@login_required
def user_bookmarks():
    bookmarks = Bookmark.query.filter_by(userId = current_user.id).all()
    results =  list(bookmarks)
    for items in results:
        try:
            items.comic = ast.literal_eval(items.comic)
        except ValueError:
            pass
    return render_template('bookmarked_movies.html', results=results)

@app.route('/likes')
@login_required
def user_likes():
    likes = Like.query.filter_by(userId = current_user.id).all()
    results =  list(likes)
    for items in results:
        try:
            items.comic = ast.literal_eval(items.comic)
        except ValueError:
            pass
    return render_template('liked_movies.html',results=results)

@app.route('/searches')
@login_required
def all_searches():
    form = DeleteSearchForm()
    form2 = EditSearchForm()
    searches = User.query.get(current_user.id).searches
    return render_template('searches.html',searches=searches, form=form, form2=form2)

@app.route('/delete/<lst>',methods=["POST"])
def delete(lst):
    user = User.query.get(current_user.id)
    searches = user.searches
    for search in searches:
        print(search.id, lst)
        if search.id == int(lst):
            user.searches.remove(search)
            db.session.commit()
    flash('Deleted search year')
    return redirect(url_for('all_searches'))

@app.route('/update/<lst>',methods=["POST"])
def update(lst):
    form = EditSearchForm()
    if form.validate_on_submit():
        searchStartYear = form.searchStartYear.data
        get_or_create_search(searchStartYear, current_user.id)
        user = User.query.get(current_user.id)
        searches = user.searches
        for search in searches:
            if search.id == int(lst):
                user.searches.remove(search)
                db.session.commit()
        flash('Updated search year')
        return redirect(url_for('all_searches'))




@app.errorhandler(401)
def unauthorized(e):
    return render_template('401.html'), 401

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('500.html'), 500



## Code to run the application...

# Put the code to do so here!
# NOTE: Make sure you include the code you need to initialize the database structure when you run the application!
if __name__=='__main__':
    db.create_all()
    app.run(debug = True)
    manager.run()
