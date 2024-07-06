import os
from datetime import date
from flask import Flask, abort, render_template, redirect, url_for, flash, request, session, jsonify
from flask_bootstrap import Bootstrap5
from flask_ckeditor import CKEditor
from flask_login import UserMixin, login_user, LoginManager, current_user, logout_user
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship, DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, String, Text, Boolean
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from forms import CreateTaskForm, RegisterForm, LoginForm, CommentForm

# Optional: add contact me email functionality (Day 60)
import smtplib

'''
Make sure the required packages are installed: 
Open the Terminal in PyCharm (bottom left). 

On Windows type:
python -m pip install -r requirements.txt

On MacOS type:
pip3 install -r requirements.txt

This will install the packages from the requirements.txt for this project.
'''

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get("SECRET")
ckeditor = CKEditor(app)
Bootstrap5(app)

# Configure Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id):
    return db.get_or_404(User, user_id)


# CREATE DATABASE
class Base(DeclarativeBase):
    pass


app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DB_URI", "sqlite:///to_do.db")
db = SQLAlchemy(model_class=Base)
db.init_app(app)


#Create Task
class CreateTask(db.Model):
    __tablename__ = "new_tasks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Create Foreign Key, "users.id" the users refers to the tablename of User.
    author_id: Mapped[int] = mapped_column(Integer, db.ForeignKey("users.id"))
    # Create reference to the User object. The "posts" refers to the posts property in the User class.
    author = relationship("User", back_populates="tasks")
    title: Mapped[str] = mapped_column(String(250), nullable=True)
    date: Mapped[str] = mapped_column(String(250), nullable=True)
    task_date: Mapped[str] = mapped_column(String(250), nullable=True)


# Create a User table for all your registered users
class User(UserMixin, db.Model):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(100), unique=True)
    password: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(100))
    # This will act like a list of BlogPost objects attached to each User.
    # The "author" refers to the author property in the BlogPost class.
    tasks = relationship("CreateTask", back_populates="author")


with app.app_context():
    db.create_all()


# Create an login decorator
def logged_in(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # If id is not 1 then return abort with 403 error
        try:
            if current_user.id >= 1:
                return abort(403)
        except AttributeError:
            pass
        # Otherwise continue with the route function
        return f(*args, **kwargs)

    return decorated_function


list_of_tasks = []
user_logged_in = False


@app.route('/register', methods=["GET", "POST"])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        # Check if user email is already present in the database.
        result = db.session.execute(db.select(User).where(User.email == form.email.data))
        user = result.scalar()
        if user:
            # User already exists
            flash("You've already signed up with that email, log in instead!")
            return redirect(url_for('login'))

        hash_and_salted_password = generate_password_hash(
            form.password.data,
            method='pbkdf2:sha256',
            salt_length=8
        )
        new_user = User(
            email=form.email.data,
            name=form.name.data,
            password=hash_and_salted_password,
        )
        db.session.add(new_user)
        db.session.commit()
        # This line will authenticate the user with Flask-Login
        login_user(new_user)
        global user_logged_in
        user_logged_in = True
        return redirect(url_for("get_all_tasks"))
    return render_template("register.html", form=form, current_user=current_user)


@app.route('/', methods=["GET", "POST"])
def get_all_tasks():
    global list_of_tasks
    task_id = len(list_of_tasks)
    existing_tasks = []
    try:
        if int(current_user.id) > 0:
            result = db.session.execute(db.select(CreateTask).where(CreateTask.author_id == int(current_user.id)))
            # Note, this may get more than one cafe per location
            all_tasks = result.scalars().all()
            existing_tasks = []
            for to_do in all_tasks:
                new_to_do = {
                    "id": to_do.id,
                    "title": to_do.title,
                    "task_date": to_do.task_date,
                    "date": to_do.date
                }
                existing_tasks.append(new_to_do)
    except AttributeError:
        pass
    if request.method == "POST":
        task = {"id": task_id,
                "title": request.form["description"],
                "task_date": date.today().strftime("%B %d, %Y"),
                "date": date.today().strftime("%B %d, %Y")}
        list_of_tasks.append(task)
        redirect(url_for('get_all_tasks'))
    return render_template("index.html", tasks=list_of_tasks, current_user=current_user, old_tasks=existing_tasks)


@app.route('/login', methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        password = form.password.data
        result = db.session.execute(db.select(User).where(User.email == form.email.data))
        # Note, email in db is unique so will only have one result.
        user = result.scalar()
        # Email doesn't exist
        if not user:
            flash("That email does not exist, please try again.")
            return redirect(url_for('login'))
        # Password incorrect
        elif not check_password_hash(user.password, password):
            flash('Password incorrect, please try again.')
            return redirect(url_for('login'))
        else:
            login_user(user)
            global user_logged_in
            user_logged_in = True
            return redirect(url_for('get_all_tasks'))

    return render_template("sign_in.html", form=form, current_user=current_user)


@app.route('/logout')
def logout():
    logout_user()
    global user_logged_in, list_of_tasks
    user_logged_in = False
    list_of_tasks = []
    return redirect(url_for('get_all_tasks'))


@app.route('/add_new_task', methods=["GET", "POST"])
def add_new_task():
    global list_of_tasks
    tasks = list_of_tasks
    existing_tasks = []
    if len(tasks) > 0:
        for task in tasks:
            new_task = CreateTask(
                title=task["title"],
                author=current_user,
                date=task["date"],
                task_date=task["task_date"]
            )
            db.session.add(new_task)
            db.session.commit()
        list_of_tasks = []
    try:
        if int(current_user.id) > 0:
            result = db.session.execute(db.select(CreateTask).where(CreateTask.author_id == int(current_user.id)))
            # Note, this may get more than one cafe per location
            all_tasks = result.scalars().all()
            existing_tasks = []
            for to_do in all_tasks:
                new_to_do = {
                    "id": to_do.id,
                    "title": to_do.title,
                    "task_date": to_do.task_date,
                    "date": to_do.date
                }
                existing_tasks.append(new_to_do)
                list_of_tasks = []
    except AttributeError:
        pass
    form = CreateTaskForm()
    if form.validate_on_submit():
        new_task = CreateTask(
            title=form.name.data,
            author=current_user,
            date=date.today().strftime("%B %d, %Y"),
            task_date=form.task_date.data
        )
        db.session.add(new_task)
        db.session.commit()
        list_of_tasks = []
        return redirect(url_for("get_all_tasks"))
    return render_template("save_to_do.html", form=form, current_user=current_user, tasks=tasks,
                           old_tasks=existing_tasks)


@app.route("/about")
def about():
    return render_template("about.html", current_user=current_user)


@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        data = request.form
        massage = f'Name: {str(data["name"])}\nemail: {str(data["email"])}\nPhone: {str(data["phone"])}\nMassage: {str(data["message"])}'
        send_email(message=massage)
        return render_template("contact.html", msg_sent=True)
    return render_template("contact.html", current_user=current_user, msg_sent=False)


@app.route("/delete/<int:task_id>")
def delete_task(task_id):
    task_to_delete = db.get_or_404(CreateTask, task_id)
    db.session.delete(task_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_tasks'))


@app.route("/delete_current_task/<int:task_id>")
def delete_current_task(task_id):
    global list_of_tasks
    del list_of_tasks[task_id]
    return redirect(url_for('get_all_tasks'))


MAIL_ADDRESS = os.environ.get("EMAIL_KEY")
MAIL_APP_PW = os.environ.get("PASSWORD_KEY")
TO_MAIL = os.environ.get("TO_MAIL")


def send_email(message):
    email_message = f"Subject:New Message\n\n{message}"
    with smtplib.SMTP("smtp.gmail.com", 587) as connection:
        connection.starttls()
        connection.login(MAIL_ADDRESS, MAIL_APP_PW)
        connection.sendmail(MAIL_ADDRESS, TO_MAIL, email_message)

if __name__ == "__main__":
    app.run(debug=False)
