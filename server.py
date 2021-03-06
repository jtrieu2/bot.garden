"""server file for bot playground."""

from jinja2 import StrictUndefined
from flask import Flask, render_template, redirect, request, flash, session
from werkzeug.utils import secure_filename
from flask_debugtoolbar import DebugToolbarExtension
from datetime import date, datetime
from model import Bot, User, Post, Source, connect_to_db, db
from processing import process_source
from config import FLASK_KEY
import markovify
import os

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'

# Required to use Flask sessions and the debug toolbar
app.secret_key = FLASK_KEY

# catches Jinja2 erorrs
app.jinja_env.undefined = StrictUndefined

# 1. INFO DISPLAY SECTION ---------------------------------

@app.route('/')
def show_index():
    """TODO: Main page - shows a stream of bot posts."""

    return render_template("base.html")

@app.route('/user/<user_id>')
def show_user_page(user_id):
    """TODO: Shows a user info page, including list of user's bots."""

    user = User.query.get(user_id)

    return render_template("user.html",
                              user=user)


@app.route('/bot/<bot_id>')
def show_bot_page(bot_id):
    """TODO: Shows a bot info page, including posts and creator."""

    bot = Bot.query.get(bot_id)
    posts = bot.posts

    return render_template("bot.html",
                            bot=bot,
                            posts=posts)

@app.route('/post/<post_id>')
def show_post_page(post_id):
    """TODO: Shows a bot info page, including posts and creator."""

    posts = Post.query.filter(Post.post_id == post_id).all()
    bot = posts[0].bot

    return render_template("bot.html",
                            posts=posts,
                            bot=bot)

@app.route('/directory')
def show_bot_directory():
    """Shows a bot directory."""

    bots = Bot.query.all()

    return render_template("directory.html", bots=bots)

@app.route('/feed')
def show_feed():
    """Shows a list of posts."""

    posts = Post.query.order_by(-Post.post_id).limit(50)

    return render_template("feed.html", posts=posts)


# 2. USER REGISTRATION AND LOGIN SECTION ------------------


@app.route("/register", methods=["GET"])
def show_reg_form():
    """Displays a user registration form."""

    return render_template("registration.html")


@app.route("/register", methods=["POST"])
def process_reg():
    """Adds user to DB."""

    new_username = request.form.get('username')
    pswd = request.form.get('password')
    desc = request.form.get('description')
    icon = request.form.get('icon')

    # Check for user username in db
    db_username = User.query.filter(User.username == new_username).first()

    if not db_username:
        user = User(username=new_username,
                 password=pswd,
                 user_icon=icon,
                 user_description=desc)
        db.session.add(user)
        db.session.commit()
        flash('registration successful!')
    else:
        flash('username address already exists - try again?')

    return redirect("/")

@app.route("/login", methods=["GET"])
def show_login_form():
    """Displays a user registration form."""

    return render_template("login.html")

@app.route("/login", methods=["POST"])
def login_user():
    """Adds user information to session."""

    login_username = request.form.get('username')
    pswd = request.form.get('password')

    user = User.query.filter(User.username == login_username).first()


    if user:
        if user.password == pswd:
            # add user info to Flask session
            session['user_id'] = user.user_id
            session['username'] = user.username
            flash('welcome back!')
            return redirect("/")
        else:
            flash('invalid password!')
    else:
        flash('user not found!')

    return redirect("/")


@app.route("/logout")
def log_out():
    """Logs user out of session."""

    session.clear()

    return redirect("/")


# 3. BOT CREATION AND LOGIC SECTION -----------------------


@app.route("/create", methods=["GET"])
def show_bot_form():
    """Displays a bot creation form."""

    return render_template("create.html")


@app.route("/create", methods=["POST"])
def create_bot():
    """Adds bot to DB."""

    name = request.form.get('name')
    desc = request.form.get('description')
    data_source = request.form.get('source')
    content_type = request.form.get('type')
    icon = request.form.get('icon')

    if content_type == "text_file":
        data_source = []
        file_list = request.files.getlist("text_file")
        for file in file_list:
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            data_source.append("uploads/" + filename)

    content = process_source(content_type, data_source)

    if content == False:
        flash('error in bot creation! make sure your sources are correct?')
        return redirect("/")

    else:
        source = Source(content_type=content_type,
                        content_source=data_source,
                        content=content)

        db.session.add(source)
        db.session.commit()

        bot = Bot(bot_name=name,
                    creator_id = session['user_id'],
                    bot_description=desc,
                    bot_icon=icon,
                    source_id=source.source_id)

        db.session.add(bot)
        db.session.commit()

        flash('bot planted!')


        return redirect("/bot/" + str(bot.bot_id))

@app.route("/delete", methods=["POST"])
def delete_bot():
    """Removes a bot from the database."""

    bot_id = request.form.get('bot_id')
    bot = Bot.query.get(bot_id)

    if session['user_id'] == bot.user.user_id:

        db.session.delete(bot)
        db.session.commit()

        flash('bot pruned!')

    else:

        flash('error removing bot!')

    return redirect("/")

    
# 3. POST CREATION AND LOGIC SECTION -----------------------


@app.route("/post", methods=["POST"])
def create_post():
    """Generates a new post from sources."""

    bot_id = request.form.get('bot_id')
    bot = Bot.query.get(bot_id)
    
    try:
        chains = markovify.Text(bot.source.content)
        text = chains.make_sentence()

    except KeyError as error:

        print(error)
        text = None

    if text == None:
        flash('*the bot hums gently*')
        return redirect("/bot/" + bot_id)

    post = Post(bot_id=bot_id,
                content=text)

    db.session.add(post)
    db.session.commit()

    return redirect("/bot/" + bot_id)



if __name__ == "__main__":
    
    # set debug mode for testing
    # app.debug = True
    # make sure templates, etc. are not cached in debug mode
    # app.jinja_env.auto_reload = app.debug

    connect_to_db(app)

    # Use the DebugToolbar
    # DebugToolbarExtension(app)

    app.run(port=5000, host='0.0.0.0')
