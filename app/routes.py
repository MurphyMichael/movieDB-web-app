from flask import render_template, url_for, flash, redirect, request
import secrets
import os
from PIL import Image
from app import app, db, bcrypt, mail, moviesDF_top
from app.models import User, MovieDB, WatchedList
from app.forms import RegistrationForm, LoginForm, UpdateUserAccountForm, ResetForm, ResetPasswordForm, SearchForm
from flask_mail import Message
from flask_login import login_user, current_user, logout_user, login_required
from omdbapi.movie_search import GetMovie
import pandas as pd
import imdb
import datetime as dt
from ast import literal_eval
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import linear_kernel


# route for the homepage
@app.route('/' , methods=['GET', 'POST'])
def Home():
    form = SearchForm()
    if form.validate_on_submit():
        search = SearchForm(request.form)
        if request.method == 'POST':
            return Results(search)
        

    return  render_template('home.html', form=form)


@app.route('/results', methods=['GET', 'POST'])
def Results(search):
    searchStr = search.data['search']
    userChoice = search.select.data
    DF_top = pd.DataFrame()

    if (len(searchStr) == 0):
        DF_empty = moviesDF_top.filter(["poster_path", "title", "genres"])
        return render_template('results.html', column_names=DF_empty.columns.values, row_data=list(DF_empty.values.tolist()), link_column="poster_path", zip=zip)
    
    elif(userChoice == "Title"):
        DF_Title = moviesDF_top[moviesDF_top['title'].astype(str).str.contains(str(searchStr), case=False)]
        DF_Title = DF_Title.filter(["poster_path", "title"])
        #print(DF_top)

        return render_template('results.html', column_names=DF_Title.columns.values, row_data=list(DF_Title.values.tolist()), link_column="poster_path", zip=zip)
    
    elif(userChoice == "Year"):
        DF_Year = moviesDF_top[moviesDF_top['year'] == int(searchStr)]
        DF_Year = DF_Year.filter(["poster_path", "title", "year"])
            
        return render_template('results.html', column_names=DF_Year.columns.values, row_data=list(DF_Year.values.tolist()), link_column="poster_path", zip=zip)

    elif(userChoice == "Genre"):
        DF_Genre = moviesDF_top[moviesDF_top['genres'].astype(str).str.contains(str(searchStr), case=False)]
        DF_Genre = DF_Genre.filter(["poster_path", "title", "genres"])

        return render_template('results.html', column_names=DF_Genre.columns.values, row_data=list(DF_Genre.values.tolist()), link_column="poster_path", zip=zip)
        
    return render_template('results.html', column_names=moviesDF_top.columns.values, row_data=list(moviesDF_top.values.tolist()), link_column="poster_path", zip=zip)

    

def path_to_image_html(posterLink):
    return '<img src="'+ posterLink + '" width="150" >'

@app.route('/movie', methods=['GET', 'POST'])
def movie():
    ia = imdb.IMDb() 

    movieName = request.args.get('title')

    rand = ia.search_movie(str(movieName)) 
    M_ID = rand[0].movieID
    mov = ia.get_movie(M_ID)
    moviePlot = mov['plot outline'] 
    movieRatings = mov['rating']
    movieGenre = mov['genres']
    movieReleaseDate = mov['year']
    poster = "http://img.omdbapi.com/?i=tt" + M_ID + "&h=600&apikey=2dc44009"


    

    return render_template('movie.html', M_ID = int(M_ID), movieName=movieName, poster=poster, moviePlot = moviePlot, movieRatings = movieRatings, movieGenre = movieGenre, movieReleaseDate=movieReleaseDate)


@app.route('/addToWatchedList', methods=['GET', 'POST'])
@login_required
def addToWatchedList():
    r = imdb.IMDb() 
    ID = request.args.get('movies_ID')

    movieObject = r.get_movie(ID)
    name = movieObject['title']
    uID = current_user.get_id()

    watchList = WatchedList(userID=uID, movieID=int(ID), movieName=name)

    check = WatchedList.query.filter_by(movieName=name, userID=uID).first()
    if check != None:
        flash(f"{ name } is already in your watched list", 'info')
        return redirect(url_for('Home'))
    else:
        flash(f' {name} has been added to your watched list!', 'success')
        db.session.add(watchList)
        db.session.commit()
        return redirect(url_for('Home'))

@app.route('/delete', methods=['GET', 'POST'])
@login_required
def DeleteFromWL():
    movieName = request.args.get('moviename')
    user = current_user.get_id()
    movieToDelete = WatchedList.query.filter_by(userID=user, movieName=movieName).first()
    db.session.delete(movieToDelete)
    db.session.commit()
    return render_template('watchedlist.html', data = WatchedList.query.filter_by(userID=current_user.get_id()).all())

# route that displays the register form
@app.route('/register', methods=['GET','POST'])
def Register():
    if current_user.is_authenticated:
        return redirect(url_for('Home'))
    form = RegistrationForm()
    # if the form the user submitted is valid, then add them to the DB in the user table
    if form.validate_on_submit():
        hashedPassword = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        user = User(username=form.username.data, email=form.email.data, password=hashedPassword)
        db.session.add(user)
        db.session.commit()
        flash('Your account has been created! Go to Login to sign in to your account!', 'success')
        return redirect(url_for('Login'))
    return render_template('register.html', title='Register', form=form)


# route for the user login page
@app.route('/login', methods=['GET','POST'])
def Login():
    if current_user.is_authenticated:
        return redirect(url_for('Home'))
    form = LoginForm()
    # if the the form submitted is valid, check to see if they exist by email, and check the password, if both are correct, log the user in.
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and bcrypt.check_password_hash(user.password, form.password.data):
            login_user(user, remember=form.remember.data)
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('Home'))
        else:
            flash('Login Unsuccessful. Please check email and password', 'danger')
    return render_template('login.html', title='Login', form=form)


# route that logouts users when they click on "Logout", redirects to home
@app.route('/logout')
def Logout():
    logout_user()
    return redirect(url_for('Home'))


# route for the user's account page
# This is a short profile page that only the user is able to see
# The user can change their email and username here, as well as their profile picture.
@app.route('/account', methods=['GET','POST'])
@login_required
def Account():
    form = UpdateUserAccountForm()
    if form.validate_on_submit():
        if form.userImage.data:
            profilePictureFile = saveUserPicture(form.userImage.data)
            current_user.profilePic = profilePictureFile
        current_user.username = form.username.data
        current_user.email = form.email.data
        db.session.commit()
        flash('Your account has been updated!', 'success')
        return redirect(url_for('Account'))
    elif request.method == 'GET':
        form.username.data = current_user.username
        form.email.data = current_user.email
    image = url_for('static', filename='profilepics/'+ current_user.profilePic)
    return render_template('account.html', title='Account', image=image, form=form)


# route for the current user's watched list of movies. Will only show up if you are logged in.
@app.route('/watchedlist')
@login_required
def Watched_List():
    
    wList = WatchedList.query.filter_by(userID=current_user.get_id()).all()

    userList = []
    recommend = pd.DataFrame()
    top_genres = []

    length = len(wList)
    userList+=[wList[i].movieName for i in range(length)]
    
    user_genre=[]
    DF_Rec = pd.DataFrame()

    tempdf = moviesDF_top.copy()
    tempdf = tempdf.reset_index(drop=True)
    
    tf = TfidfVectorizer(analyzer='word', ngram_range=(1, 3), min_df=0, stop_words='english')
    matrix = tf.fit_transform(tempdf['genres'])
    cosine_similarities = linear_kernel(matrix,matrix)

    movie_title = tempdf['title']
    indices = pd.Series(tempdf.index, index=tempdf['title'])

    recNames = {}
    temp = []
    
    for mov in userList:
        t = movie_recommend(mov, indices, cosine_similarities, movie_title)
        t.to_string(index=False)
        recNames[mov] = t


    values = recNames.values()
    values_list = list(values)
    values_list[0].tolist()
    for i in range(len(values_list)):
        values_list[i] = values_list[i].tolist()
    final = []
    for i in values_list:
        for j in i:
            final.append(j)
    print(final)

    recommend = moviesDF_top[moviesDF_top['title'].isin(final)]
    recommend = recommend.filter(["poster_path", "title"])








    


    
    
    
    return render_template('watchedlist.html', data = wList, column_names=recommend.columns.values, row_data=list(recommend.values.tolist()), link_column="poster_path", zip=zip)

def movie_recommend(title, indices, cosine_similarities, movie_title):

    idx = indices[title]

    sim_scores = list(enumerate(cosine_similarities[idx]))

    sim_scores = sorted(sim_scores, key=lambda x: x[1], reverse=True)

    sim_scores = sim_scores[1:31]

    movie_indices = [i[0] for i in sim_scores]
    rec = movie_title.iloc[movie_indices].head(3)

    return rec

# route to request password reset.
@app.route('/resetpassword', methods=['GET','POST'])
def ResetRequest():
    if current_user.is_authenticated:
        return redirect(url_for('Home'))
    form = ResetForm()
    # if the email was found, a email will be sent with a password reset link
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        SendEmail(user)
        flash('Email sent with password reset instructions.', 'info')
        return redirect(url_for('Login'))
    return render_template('resetrequest.html', title='Reset Password', form=form)


# where the password resetting happens with the token.
@app.route('/resetpassword/<token>', methods=['GET','POST'])
def ResetRequestToken(token):
    if current_user.is_authenticated:
        return redirect(url_for('Home'))
    user = User.VerifyResetToken(token)
    if user is None:
        flash('Your reset token is invalid or has expired.', 'warning')
        return redirect(url_for('ResetRequest'))
    form = ResetPasswordForm()
    if form.validate_on_submit():
        hashedPassword = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        user.password = hashedPassword
        db.session.commit()
        flash('Your password has been successfully changed!', 'success')
        return redirect(url_for('Login'))
    return render_template('resettoken.html', title='Reset Password', form=form)


# route to handle 404 errors and to send you back to home with a link
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html', title='404')

#         ###########functions to help in certain routes###########


# this function resized and saves pictures in the path app/static/profilepics.
def saveUserPicture(form_picture):
    random = secrets.token_hex(8)
    _, f_ext = os.path.splitext(form_picture.filename)
    fileName = random + f_ext
    picturePath = os.path.join(app.root_path, 'static/profilepics', fileName)
    outputSize = (125, 125)
    resize = Image.open(form_picture)
    resize.thumbnail(outputSize)
    resize.save(picturePath)

    return fileName

# the message that will be sent to the user if the email sent into the form is valid.
def SendEmail(user):
    token = user.GetResetToken()
    message = Message('Group4 Movie Database - Password Reset', sender='dontreply@grp4moviedb.com', recipients=[user.email])
    message.body = f''' Click on the link to reset your password!
{url_for('ResetRequestToken', token=token, _external=True)}

If you didn't request a password change, please ignore this message.
'''

    mail.send(message)