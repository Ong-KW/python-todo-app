import os
from dotenv import load_dotenv

from datetime import date, datetime
import hashlib
from urllib.parse import urlencode

from flask import Flask, abort, render_template, redirect, url_for, request
from flask_bootstrap import Bootstrap5
from flask_ckeditor import CKEditor

from flask_login import UserMixin, login_user, LoginManager, current_user, logout_user, login_required
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, String, Text, Boolean, and_, or_
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from forms import LoginForm, RegisterForm, CreateProjectForm, CreateTaskForm, CommentForm, AssigneeEditTaskForm

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY")
ckeditor = CKEditor(app)
Bootstrap5(app)

def gravatar_url(email, size=100, default='retro'):

    # Encode the email to lowercase and then to bytes
    email_encoded = email.lower().encode('utf-8')

    # Generate the SHA256 hash of the email
    email_hash = hashlib.sha256(email_encoded).hexdigest()

    # Construct the URL with encoded query parameters
    query_params = urlencode({'d': default, 's': str(size)})
    return f"https://www.gravatar.com/avatar/{email_hash}?{query_params}"




# Set up the login manager
login_manager = LoginManager()
login_manager.init_app(app)

# Create Database
class Base(DeclarativeBase):
    pass

app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DB_URI",'sqlite:///todos.db')
db = SQLAlchemy(model_class=Base)
db.init_app(app)

# User Table
class User(UserMixin,db.Model):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(100), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    password: Mapped[str] = mapped_column(String(100))
    projects = db.relationship("Project", back_populates="creator")
    # tasks = db.relationship("Task", back_populates="creator")
    # assigned_tasks = db.relationship("Task", back_populates="assignee")
    comments = db.relationship("Comment", back_populates="comment_author")

# Project Table
class Project(db.Model):
    __tablename__ = "projects"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(250), nullable=False)
    description: Mapped[str] = mapped_column(Text)
    date: Mapped[str] = mapped_column(String(250), nullable=False)
    creator_id: Mapped[int] = mapped_column(Integer, db.ForeignKey("users.id"))
    creator = db.relationship("User", back_populates="projects")
    tasks = db.relationship("Task", back_populates="project")

# Task Table
class Task(db.Model):
    __tablename__ = "tasks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_text: Mapped[str] = mapped_column(String(100), nullable=False)
    due_date: Mapped[str] = mapped_column(String(250), nullable=False)
    is_complete: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    creator_id: Mapped[int] = mapped_column(Integer, db.ForeignKey("users.id"))
    creator = db.relationship("User", foreign_keys=[creator_id])
    assignee_id: Mapped[int] = mapped_column(Integer, db.ForeignKey("users.id"))
    assignee = db.relationship("User", foreign_keys=[assignee_id])
    project_id: Mapped[int] = mapped_column(Integer, db.ForeignKey("projects.id"))
    project = db.relationship("Project", back_populates="tasks")
    comments = db.relationship("Comment", back_populates="task")

# Comment Table
class Comment(db.Model):
    __tablename__ = "comments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    comment_text: Mapped[str] = mapped_column(String(100), nullable=False)
    comment_author_id: Mapped[int] = mapped_column(Integer, db.ForeignKey("users.id"))
    comment_author = db.relationship("User", back_populates="comments")
    task_id: Mapped[int] = mapped_column(Integer, db.ForeignKey("tasks.id"))
    task = db.relationship("Task", back_populates="comments")

with app.app_context():
    db.create_all()


@login_manager.user_loader
def load_user(user_id):
    return db.get_or_404(User, user_id)

# Decorator function for admin only
def admin_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.id != 1:
            return abort(403)
        return f(*args, **kwargs)
    return decorated_function

# Decorator function for creator only
def creator_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):

        index = int(request.path.split("/")[2])

        if request.endpoint == ("add_new_task" or "edit_project" or "delete_project"):
            project = db.get_or_404(Project, index)

            if current_user.id != project.creator_id:
                return abort(403)

            return f(*args, **kwargs)

        elif request.endpoint == ("edit_task" or "delete task"):
            task = db.get_or_404(Task, index)

            if current_user.id != task.creator_id:
                return abort(403)

            return f(*args, **kwargs)

    return decorated_function

# Decorator function for assignee only
def assignee_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):

        index = int(request.path.split("/")[2])

        task = db.get_or_404(Task, index)

        if current_user.id != task.assignee_id:
            return abort(403)

        return f(*args, **kwargs)

    return decorated_function

# Decorator function for collaborators only
def collaborators_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):

        index = int(request.path.split("/")[2])

        if request.endpoint == "show_project":
            project = db.get_or_404(Project, index)
            task_assignee_ids = [task.assignee_id for task in project.tasks]

            if current_user.id != project.creator_id:
                if current_user.id not in task_assignee_ids:
                    return abort(403)
                else:
                    return f(*args, **kwargs)

            return f(*args, **kwargs)

        elif request.endpoint == "show_task":
            # Get the task from the index
            task = db.get_or_404(Task, index)

            # Get the project from the task
            required_project = task.project

            # Get all task creator_ids and assignee_ids from the project
            task_assignee_ids = [task.assignee_id for task in required_project.tasks]
            task_creator_ids = [task.creator_id for task in required_project.tasks]

            if current_user.id not in (task_assignee_ids or task_creator_ids):
                return abort(403)

            return f(*args, **kwargs)

        elif request.endpoint == "mark_task":
            # Get the task from the index
            task = db.get_or_404(Task, index)

            if current_user.id != (task.assignee_id or task.creator_id):
                return abort(403)

            return f(*args, **kwargs)

    return decorated_function

@app.route("/register", methods=['GET','POST'])
@login_required
@admin_only
def register():
    form=RegisterForm()

    if form.validate_on_submit():

        # Check if user already exists in database
        result = db.session.execute(db.select(User).where(User.email == form.email.data))
        user = result.scalar()

        # If user email already exists, redirect to login page
        if user:
            return redirect(url_for('login'))

        hash_and_salted_password = generate_password_hash(
            form.password.data,
            method="pbkdf2:sha256",
            salt_length=8
        )

        new_user = User(
            email = form.email.data,
            name = form.name.data,
            password = hash_and_salted_password,
        )
        db.session.add(new_user)
        db.session.commit()

        return redirect(url_for('home'))

    return render_template("register.html", form=form, gravatar_url=gravatar_url, current_user=current_user)

@app.route("/login", methods=['GET','POST'])
def login():
    form=LoginForm()

    if form.validate_on_submit():

        result = db.session.execute(db.select(User).where(User.email == form.email.data))
        user = result.scalar()

        # User does not exist
        if not user:
            return redirect(url_for('login'))
        # Incorrect password
        elif not check_password_hash(user.password, form.password.data):
            return redirect(url_for('login'))
        else:
            login_user(user)
            return redirect(url_for('home'))

    return render_template("login.html", form=form, gravatar_url=gravatar_url, current_user=current_user)

@app.route("/login-guest", methods=['GET','POST'])
def login_guest():

    result = db.session.execute(db.select(User).where(User.email == "guest@email.com"))
    user = result.scalar()

    login_user(user)
    return redirect(url_for('home'))

@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for('home'))

# Show all the registered users (Only admin has access)
@app.route("/users")
@login_required
@admin_only
def get_all_users():

    results = db.session.execute(db.select(User))
    all_users = results.scalars().all()

    return render_template("users.html", gravatar_url=gravatar_url, users = all_users, current_user=current_user)

# Get the home page
@app.route("/")
def home():

    x = datetime.now()

    if 0 <= int(x.strftime("%H")) <= 11:
        greeting = "Good morning"
    elif 12 <= int(x.strftime("%H")) <= 15:
        greeting = "Good afternoon"
    else:
        greeting = "Good evening"

    return render_template("index.html", gravatar_url=gravatar_url, greeting=greeting, weekday=x.strftime("%A"), dt=x.strftime("%B %d"), current_user=current_user)

# Get the current user's projects page
@app.route("/current-user-projects")
@login_required
def get_current_user_projects():

    # Get all current user's assigned tasks
    results = db.session.execute(db.select(Task).where(Task.assignee_id == current_user.id))
    tasks = results.scalars().all()

    # Get all the project_id of projects containing current user's assigned tasks
    project_ids = [task.project_id for task in tasks]
    # print(project_ids)

    # Get all projects created by current user or projects that have tasks assigned to current user from the database
    results = db.session.execute(db.select(Project).filter(or_(Project.creator_id == current_user.id, Project.id.in_(project_ids))))
    all_projects = results.scalars().all()

    return render_template("user-projects.html", gravatar_url=gravatar_url, current_user=current_user, projects=all_projects)

# Add new projects
@app.route("/new-project", methods=['GET','POST'])
@login_required
def add_new_project():

    form = CreateProjectForm()

    # Add the new project to database
    if form.validate_on_submit():

        new_project = Project(
            title = form.title.data,
            description = form.description.data,
            date = date.today().strftime("%B %d, %Y"),
            creator = current_user
        )
        db.session.add(new_project)
        db.session.commit()

        return redirect(url_for("get_current_user_projects"))

    return render_template("make-project.html", gravatar_url=gravatar_url, form=form)

# Show project details
@app.route("/show-project/<int:project_id>")
@login_required
@collaborators_only
def show_project(project_id):

    project = db.get_or_404(Project, project_id)

    return render_template("project.html", gravatar_url=gravatar_url, project=project)

# Edit project
@app.route("/edit-project/<int:project_id>", methods=['GET', 'POST'])
@login_required
@creator_only
def edit_project(project_id):

    project_to_edit = db.get_or_404(Project, project_id)

    form = CreateProjectForm(
        title = project_to_edit.title,
        description = project_to_edit.description
    )

    if form.validate_on_submit():

        project_to_edit.title = form.title.data
        project_to_edit.description = form.description.data

        db.session.commit()

        return redirect(url_for("show_project", project_id=project_id))

    return render_template("make-project.html", is_edit=True, gravatar_url=gravatar_url, form=form)

# Delete project
@app.route("/delete-project/<int:project_id>")
@login_required
@creator_only
def delete_project(project_id):

    # Get project to delete from database
    project_to_delete = db.get_or_404(Project, project_id)

    # Get all the ids of the tasks in the project to delete
    tasks = project_to_delete.tasks
    task_ids = [task.id for task in tasks]

    # Delete the tasks
    db.session.execute(db.delete(Task).where(Task.id.in_(task_ids)))

    # Delete the project
    db.session.delete(project_to_delete)
    db.session.commit()

    return redirect(url_for("get_current_user_projects"))

# Show only current user's assigned tasks
@app.route("/current-user-tasks")
@login_required
def get_current_user_tasks():

    if request.args.get("sort_by") == "project":
        results = db.session.execute(
            db.select(Task).filter(and_(Task.assignee_id == current_user.id, Task.is_complete == False)).order_by(
                Task.project_id))
    elif request.args.get("sort_by") == "creator":
        results = db.session.execute(
            db.select(Task).filter(and_(Task.assignee_id == current_user.id, Task.is_complete == False)).order_by(
                Task.creator_id))
    else:
        results = db.session.execute(
            db.select(Task).filter(and_(Task.assignee_id == current_user.id, Task.is_complete == False)).order_by(
                Task.due_date))

    assigned_tasks = results.scalars().all()

    return render_template("assigned-tasks.html", gravatar_url=gravatar_url, tasks=assigned_tasks)

@app.route("/order-tasks-by-due-date")
@login_required
def order_tasks_by_due_date():
    return redirect(url_for("get_current_user_tasks", sort_by="due_date"))

@app.route("/order-tasks-by-project")
@login_required
def order_tasks_by_project():
    return redirect(url_for("get_current_user_tasks", sort_by="project"))

@app.route("/order-tasks-by-creator")
@login_required
def order_tasks_by_creator():
    return redirect(url_for("get_current_user_tasks", sort_by="creator"))

# Show task details
@app.route("/task/<int:task_id>", methods=['GET', 'POST'])
@login_required
@collaborators_only
def show_task(task_id):

    task = db.get_or_404(Task, task_id)

    form=CommentForm()

    if form.validate_on_submit():

        new_comment = Comment(
            comment_author_id = current_user.id,
            task_id = task_id,
            comment_text=form.comment_text.data
        )
        db.session.add(new_comment)
        db.session.commit()

        return redirect(url_for("show_task", task_id=task.id))

    return render_template("task.html", gravatar_url=gravatar_url, project_id=task.project_id, task=task, form=form)

# Edit comment
@app.route("/edit-comment", methods=['GET', 'POST'])
@login_required
def edit_comment():

    comment = db.get_or_404(Comment, request.args.get('comment_id'))

    task = db.get_or_404(Task, request.args.get('task_id'))

    form=CommentForm(
        comment_text=comment.comment_text
    )

    if form.validate_on_submit():

        comment.comment_text=form.comment_text.data
        db.session.commit()

        return redirect(url_for("show_task", task_id=request.args.get('task_id')))

    return render_template("task.html", is_edit_comment=True, comment_id=int(request.args.get('comment_id')), gravatar_url=gravatar_url, task=task, form=form)

# Delete comment
@app.route("/delete-comment")
@login_required
def delete_comment():

    comment_to_delete = db.get_or_404(Comment, request.args.get('comment_id'))
    db.session.delete(comment_to_delete)
    db.session.commit()

    return redirect(url_for("show_task", task_id=request.args.get('task_id')))


# Mark task (Change the state of is_complete)
@app.route("/mark-my-task/<int:task_id>")
@login_required
@assignee_only
def mark_my_task(task_id):

    task = db.get_or_404(Task, task_id)
    task.is_complete = not task.is_complete
    db.session.commit()

    return redirect(url_for("get_current_user_tasks"))

# Mark task (Change the state of is_complete)
@app.route("/mark-task/<int:task_id>")
@login_required
@collaborators_only
def mark_task(task_id):

    task = db.get_or_404(Task, task_id)
    task.is_complete = not task.is_complete
    db.session.commit()

    return redirect(url_for("show_project", project_id=request.args.get("project_id")))

# Add new tasks
@app.route("/new-task/<int:project_id>", methods=['GET','POST'])
@login_required
@creator_only
def add_new_task(project_id):

    # Get the project from the database
    project = db.get_or_404(Project, project_id)

    # Get all the users from the database
    results = db.session.execute(db.select(User))
    users = results.scalars().all()

    # Form a list of tuples for SelectField in CreateTaskForm
    user_emails = [(user.id, user.email) for user in users]

    form = CreateTaskForm()

    if current_user.email == "guest@email.com":
        # Only allow guest to assign task to guest
        form.assignee.choices = [(current_user.id, current_user.email)]
    else:
        # Pass the list of tuples into the form
        form.assignee.choices = user_emails

    # Add the new task to database
    if form.validate_on_submit():

        # Get the assignee from the database
        assigned_user = db.get_or_404(User,form.assignee.data)

        new_task = Task(
            task_text=form.task.data,
            due_date=form.due_date.data,
            assignee=assigned_user,
            creator=current_user,
            project=project
        )
        db.session.add(new_task)
        db.session.commit()

        return redirect(url_for("show_project", project_id=project.id))

    return render_template("make-task.html", gravatar_url=gravatar_url, form=form)

# Edit task by task creator
@app.route("/edit-task/<int:task_id>", methods=['GET', 'POST'])
@login_required
@creator_only
def edit_task(task_id):

    task_to_edit = db.get_or_404(Task,task_id)

    # Get all the users from the database
    results = db.session.execute(db.select(User))
    users = results.scalars().all()

    # Form a list of tuples for SelectField in CreateTaskForm
    user_emails = [(user.id, user.email) for user in users]

    form = CreateTaskForm(
        task = task_to_edit.task_text,
        due_date = datetime.strptime(task_to_edit.due_date, "%Y-%m-%d"),
        assignee = task_to_edit.assignee.id
    )
    # Pass the list of tuples into the form
    form.assignee.choices = user_emails

    if form.validate_on_submit():

        # Get the assignee from the database
        assigned_user = db.get_or_404(User, form.assignee.data)

        task_to_edit.task_text = form.task.data
        task_to_edit.due_date = form.due_date.data
        task_to_edit.assignee = assigned_user

        db.session.commit()

        return redirect(url_for("show_project", project_id=task_to_edit.project_id))

    return render_template("make-task.html", is_edit=True, gravatar_url=gravatar_url, form=form)

# Edit task due date by task assignee
@app.route("/edit-task-due-date/<int:task_id>", methods=['GET', 'POST'])
@login_required
@assignee_only
def edit_task_due_date(task_id):

    task_to_edit = db.get_or_404(Task,task_id)

    form = AssigneeEditTaskForm(
        due_date = datetime.strptime(task_to_edit.due_date, "%Y-%m-%d")
    )

    if form.validate_on_submit():

        task_to_edit.due_date = form.due_date.data
        db.session.commit()

        return redirect(url_for("show_project", project_id=task_to_edit.project_id))

    return render_template("make-task.html", is_edit=True, gravatar_url=gravatar_url, form=form)

# Delete tasks
@app.route("/delete-task/<int:task_id>")
@login_required
@creator_only
def delete_task(task_id):

    task_to_delete = db.get_or_404(Task, task_id)
    db.session.delete(task_to_delete)
    db.session.commit()

    return redirect(url_for("show_project", project_id=task_to_delete.project_id))

if __name__ == "__main__":
    app.run(debug=False)