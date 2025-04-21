from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, PasswordField, DateField, SelectField, FormField
from wtforms.validators import DataRequired, URL
from flask_ckeditor import CKEditorField

class RegisterForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired()])
    password = PasswordField("Password", validators=[DataRequired()])
    name = StringField("Name", validators=[DataRequired()])
    submit = SubmitField("Sign Up")

class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Log In")

class CreateProjectForm(FlaskForm):
    title = StringField("Project Title", validators=[DataRequired()])
    description = CKEditorField("Project Description (optional)")
    submit = SubmitField("Submit")

class CreateTaskForm(FlaskForm):
    task = StringField("Task", validators=[DataRequired()])
    due_date = DateField("Due Date", format='%Y-%m-%d', validators=[DataRequired()])
    assignee = SelectField("Assignee", validators=[DataRequired()])
    submit = SubmitField("Submit")

class AssigneeEditTaskForm(FlaskForm):
    due_date = DateField("Due Date", format='%Y-%m-%d', validators=[DataRequired()])
    submit = SubmitField("Submit")

class CommentForm(FlaskForm):
    comment_text = CKEditorField("Comment", validators=[DataRequired()])
    submit = SubmitField("Submit")
