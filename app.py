from flask import Flask, render_template, redirect, url_for, flash, request
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, SelectField, TextAreaField
from wtforms.validators import DataRequired, Email, EqualTo, Length, Optional, ValidationError
from werkzeug.security import generate_password_hash, check_password_hash
import os
import datetime

# App Configuration
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your_strong_secret_key') # Change in production!
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///language_platform.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'

# Association table for User-Course many-to-many relationship
enrollments = db.Table('enrollments',
    db.Column('user_id', db.Integer, db.ForeignKey('users.id'), primary_key=True),
    db.Column('course_id', db.Integer, db.ForeignKey('courses.id'), primary_key=True)
)

# --- Database Models ---
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    chosen_language = db.Column(db.String(50), nullable=True)
    # progress = db.Column(db.JSON, nullable=True) # Or a separate table for progress

    # Relationships
    quiz_attempts = db.relationship('QuizAttempt', backref='user', lazy=True)
    forum_posts = db.relationship('ForumPost', backref='author', lazy=True)
    comments = db.relationship('Comment', backref='author', lazy=True)
    enrolled_courses = db.relationship(
        'Course', secondary=enrollments,
        backref=db.backref('enrolled_by_users', lazy='dynamic'),
        lazy='dynamic'
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.email}>'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class Course(db.Model):
    __tablename__ = 'courses'
    id = db.Column(db.Integer, primary_key=True)
    language = db.Column(db.String(50), nullable=False)
    level = db.Column(db.String(50), nullable=False) # Beginner, Intermediate, Advanced
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    image_url = db.Column(db.String(200), nullable=True) # For course thumbnail/banner
    learning_objectives = db.Column(db.Text, nullable=True) # What students will learn
    # Relationship to Modules
    modules = db.relationship('Module', backref='course', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f'<Course {self.title}>'

class Module(db.Model):
    __tablename__ = 'modules'
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    title = db.Column(db.String(150), nullable=False)
    order = db.Column(db.Integer, nullable=False) # To order modules within a course
    description = db.Column(db.Text, nullable=True) # Optional description for the module
    lessons = db.relationship('Lesson', backref='module', lazy=True, cascade="all, delete-orphan", order_by='Lesson.lesson_number')

    def __repr__(self):
        return f'<Module {self.title}>'

class Lesson(db.Model):
    __tablename__ = 'lessons'
    id = db.Column(db.Integer, primary_key=True)
    module_id = db.Column(db.Integer, db.ForeignKey('modules.id'), nullable=False)
    lesson_number = db.Column(db.Integer, nullable=False) # For ordering within a module
    title = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False) # Rich text, paths to images/audio
    video_url = db.Column(db.String(200), nullable=True)
    estimated_duration = db.Column(db.String(50), nullable=True) # e.g., "20 minutes"
    quizzes = db.relationship('Quiz', backref='lesson', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f'<Lesson {self.title}>'

class Quiz(db.Model):
    __tablename__ = 'quizzes'
    id = db.Column(db.Integer, primary_key=True)
    lesson_id = db.Column(db.Integer, db.ForeignKey('lessons.id'), nullable=False)
    question = db.Column(db.Text, nullable=False)
    # For MCQs, options can be a JSON string or separate columns/table
    # For fill-in-the-blanks, this might be different
    options = db.Column(db.String(500), nullable=True) # e.g., JSON: {"a": "Option A", "b": "Option B"}
    correct_answer = db.Column(db.String(100), nullable=False)
    quiz_type = db.Column(db.String(20), default='multiple_choice') # 'multiple_choice', 'fill_in_blank'
    quiz_attempts = db.relationship('QuizAttempt', backref='quiz', lazy=True)

    def __repr__(self):
        return f'<Quiz {self.question[:30]}>'

class QuizAttempt(db.Model):
    __tablename__ = 'quiz_attempts'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    quiz_id = db.Column(db.Integer, db.ForeignKey('quizzes.id'), nullable=False)
    selected_answer = db.Column(db.String(100), nullable=False)
    is_correct = db.Column(db.Boolean, nullable=False)
    attempted_at = db.Column(db.DateTime, server_default=db.func.now())

    def __repr__(self):
        return f'<QuizAttempt by User {self.user_id} for Quiz {self.quiz_id}>'

class ForumPost(db.Model):
    __tablename__ = 'forum_posts'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    language = db.Column(db.String(50), nullable=True) # Optional, can be general
    topic = db.Column(db.String(50), nullable=True) # e.g., Grammar, Vocabulary, Culture
    title = db.Column(db.String(150), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    comments = db.relationship('Comment', backref='post', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f'<ForumPost {self.title}>'

class Comment(db.Model):
    __tablename__ = 'comments'
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('forum_posts.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    def __repr__(self):
        return f'<Comment by User {self.user_id} on Post {self.post_id}>'

# --- Forms ---
class RegistrationForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Register')

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('That email is already taken. Please choose a different one.')

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

class ProfileUpdateForm(FlaskForm):
    chosen_language = SelectField('Preferred Language', choices=[
        ('', 'Select a language...'),
        ('Spanish', 'Spanish'),
        ('French', 'French'),
        ('German', 'German'),
        ('Italian', 'Italian'),
        ('Japanese', 'Japanese'),
        # Add more languages as needed
    ], validators=[Optional()])
    submit = SubmitField('Update Profile')

# --- Context Processors ---
@app.context_processor
def inject_current_year():
    return {'current_year': datetime.datetime.utcnow().year}

# --- Routes ---
@app.route('/')
@app.route('/index')
def index():
    return render_template('index.html', title='Home')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = RegistrationForm()
    if form.validate_on_submit():
        try:
            user = User(email=form.email.data)
            user.set_password(form.password.data)
            db.session.add(user)
            db.session.commit()
            flash('Your account has been created! You are now able to log in.', 'success')
            return redirect(url_for('login'))
        except ValueError as e:
            flash(str(e), 'danger')
        except Exception as e:
            db.session.rollback()
            flash('An error occurred during registration. Please try again.', 'danger')
            app.logger.error(f"Error during registration: {e}")
    return render_template('register.html', title='Register', form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and user.check_password(form.password.data):
            login_user(user, remember=True) # 'remember=True' can be a checkbox in the form
            next_page = request.args.get('next')
            flash('Login successful!', 'success')
            return redirect(next_page) if next_page else redirect(url_for('index'))
        else:
            flash('Login Unsuccessful. Please check email and password.', 'danger')
    return render_template('login.html', title='Login', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    form = ProfileUpdateForm()
    if form.validate_on_submit():
        current_user.chosen_language = form.chosen_language.data
        db.session.commit()
        flash('Your profile has been updated!', 'success')
        return redirect(url_for('profile'))
    elif request.method == 'GET':
        form.chosen_language.data = current_user.chosen_language
    return render_template('profile.html', title='Profile', form=form)

@app.route('/courses')
@login_required
def courses():
    all_courses = Course.query.order_by(Course.language, Course.level).all()
    return render_template('courses.html', title='Courses', courses=all_courses)

@app.route('/course/<int:course_id>')
@login_required
def course_detail(course_id):
    course = Course.query.get_or_404(course_id)
    # Eagerly load modules and their lessons to avoid N+1 queries in template
    modules = Module.query.filter_by(course_id=course.id).order_by(Module.order).options(db.joinedload(Module.lessons)).all()
    return render_template('course_detail.html', title=course.title, course=course, modules=modules)

@app.route('/lesson/<int:lesson_id>')
@app.route('/lesson_view/<int:lesson_id>') # Alias for template consistency
@login_required
def lesson_view(lesson_id):
    lesson = Lesson.query.options(
        db.joinedload(Lesson.module).joinedload(Module.course)
    ).get_or_404(lesson_id)
    
    module = lesson.module
    course = module.course
    
    return render_template('lesson.html', title=lesson.title, lesson=lesson, module=module, course=course)

@app.route('/quiz/<int:quiz_id>/take', methods=['GET', 'POST'])
@login_required
def take_quiz(quiz_id):
    quiz = Quiz.query.options(
        db.joinedload(Quiz.lesson).joinedload(Lesson.module).joinedload(Module.course)
    ).get_or_404(quiz_id)
    
    lesson = quiz.lesson
    module = lesson.module
    course = module.course

    if request.method == 'POST':
        selected_answer = request.form.get('selected_answer')
        if not selected_answer:
            flash('Please select an answer.', 'warning')
            # Re-render the quiz page if no answer was submitted
            options = quiz.options.split(',') if quiz.options else []
            return render_template('take_quiz.html', 
                                   title=f"Quiz: {quiz.question[:30]}...", 
                                   quiz=quiz, 
                                   options=options, 
                                   lesson=lesson, 
                                   module=module, 
                                   course=course)

        # Determine if the answer is correct
        # For simplicity, direct string comparison. Consider case-insensitivity or trimming for robustness.
        is_correct = (selected_answer.strip().lower() == quiz.correct_answer.strip().lower())

        # Create and save the quiz attempt
        attempt = QuizAttempt(
            user_id=current_user.id,
            quiz_id=quiz.id,
            selected_answer=selected_answer,
            is_correct=is_correct
        )
        db.session.add(attempt)
        db.session.commit()

        if is_correct:
            flash('Correct! Well done.', 'success')
        else:
            flash(f'Not quite. The correct answer was: {quiz.correct_answer}', 'danger')
        
        return redirect(url_for('lesson_view', lesson_id=lesson.id))

    # For GET request, display the quiz
    options = quiz.options.split(',') if quiz.options else []

    return render_template('take_quiz.html', 
                           title=f"Quiz: {quiz.question[:30]}...", 
                           quiz=quiz, 
                           options=options, 
                           lesson=lesson, 
                           module=module, 
                           course=course)

@app.route('/enroll/<int:course_id>', methods=['POST']) # POST to indicate an action
@login_required
def enroll_course(course_id):
    course = Course.query.get_or_404(course_id)
    if course in current_user.enrolled_courses:
        flash('You are already enrolled in this course.', 'info')
    else:
        current_user.enrolled_courses.append(course)
        db.session.commit()
        flash(f'Successfully enrolled in {course.title}!', 'success')
    return redirect(url_for('course_detail', course_id=course.id))

# Placeholder routes from memory
@app.route('/enrolled-courses')
@login_required
def enrolled_courses():
    user_enrolled_courses = current_user.enrolled_courses.all() # Get all enrolled courses
    return render_template('enrolled-courses.html', title='My Courses', enrolled_courses=user_enrolled_courses)

@app.route('/assignments') # Or quizzes per lesson
@login_required
def assignments():
    return render_template('assignments.html', title='Assignments')

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        # In a real application, you would process the form data here (e.g., send an email)
        # name = request.form.get('name')
        # email = request.form.get('email')
        # subject = request.form.get('subject')
        # message = request.form.get('message')
        flash('Thank you for your message! We will get back to you soon.', 'success')
        return redirect(url_for('contact')) # Redirect to clear the form and prevent resubmission
    return render_template('contact.html', title='Contact Us')

# --- Helper Functions --- 
def create_initial_data():
    with app.app_context():
        if Course.query.first() is None:
            print("Creating initial Spoken Language course data...")

            # --- Spanish Course ---
            spanish_course = Course(
                language='Spanish',
                level='Beginner',
                title='Spanish for Beginners: Start Speaking Today!',
                description='Embark on your journey to learn Spanish. This course covers basic vocabulary, grammar, and conversational phrases.',
                image_url='images/spanish_course.png',
                learning_objectives='Understand and use familiar everyday expressions and very basic phrases. Introduce yourself and others and can ask and answer questions about personal details such as where you live, people you know and things you have. Interact in a simple way provided the other person talks slowly and clearly.'
            )
            db.session.add(spanish_course)
            db.session.commit()

            # Spanish Module 1: Foundations
            spanish_module1 = Module(course_id=spanish_course.id, title='Module 1: ¡Hola! Getting Started', order=1, description='Greetings, alphabet, numbers, and basic introductions.')
            db.session.add(spanish_module1)
            db.session.commit()

            lesson_s1_1 = Lesson(module_id=spanish_module1.id, lesson_number=1, title='Greetings and Basic Introductions', content='Learn essential Spanish greetings like \'Hola\' (Hello), \'Buenos días\' (Good morning), \'Buenas tardes\' (Good afternoon/evening), and \'Adiós\' (Goodbye). Understand how to introduce yourself with \'Me llamo...\' (My name is...).', video_url='https://www.youtube.com/embed/t7-nb1wlnyA', estimated_duration='30 mins')
            lesson_s1_2 = Lesson(module_id=spanish_module1.id, lesson_number=2, title='The Spanish Alphabet (El Alfabeto)', content='Discover the Spanish alphabet and the pronunciation of each letter. Understand key differences from the English alphabet, such as the letter \'ñ\'.', video_url='https://www.youtube.com/embed/placeholder_video_id', estimated_duration='30 mins')
            lesson_s1_3 = Lesson(module_id=spanish_module1.id, lesson_number=3, title='Numbers 0-20 (Los Números)', content='Learn to count from zero to twenty in Spanish. Practice with interactive exercises.', estimated_duration='25 mins')
            db.session.add_all([lesson_s1_1, lesson_s1_2, lesson_s1_3])
            db.session.commit()

            quiz_s1_1_1 = Quiz(lesson_id=lesson_s1_1.id, question='How do you say \'Hello\' in Spanish?', options='Adiós,Gracias,Hola,Por favor', correct_answer='Hola', quiz_type='multiple_choice')
            quiz_s1_2_1 = Quiz(lesson_id=lesson_s1_2.id, question='The letter \'ñ\' is unique to the Spanish alphabet. (True/False)', options='True,False', correct_answer='True', quiz_type='true_false')
            quiz_s1_3_1 = Quiz(lesson_id=lesson_s1_3.id, question='What is \'cinco\' in English?', options='Three,Five,Six,Ten', correct_answer='Five', quiz_type='multiple_choice')
            quiz_s1_1_2 = Quiz(lesson_id=lesson_s1_1.id, question="'Buenos días' is a common greeting in the afternoon. (True/False)", options='True,False', correct_answer='False', quiz_type='true_false')
            db.session.add_all([quiz_s1_1_1, quiz_s1_1_2, quiz_s1_2_1, quiz_s1_3_1])
            db.session.commit()

            # Spanish Module 2: Basic Interactions
            spanish_module2 = Module(course_id=spanish_course.id, title='Module 2: Everyday Conversations', order=2, description='Learn to talk about yourself, your family, and basic needs.')
            db.session.add(spanish_module2)
            db.session.commit()

            lesson_s2_1 = Lesson(module_id=spanish_module2.id, lesson_number=1, title='Introducing Yourself (Presentarse)', content='Learn phrases to introduce yourself, such as \'Me llamo...\' (My name is...) and \'Soy de...\' (I am from...).', estimated_duration='30 mins')
            lesson_s2_2 = Lesson(module_id=spanish_module2.id, lesson_number=2, title='Asking and Answering Basic Questions', content='Practice asking simple questions like \'¿Cómo estás?\' (How are you?) and \'¿De dónde eres?\' (Where are you from?).', video_url='https://www.youtube.com/embed/placeholder_video_id', estimated_duration='35 mins')
            db.session.add_all([lesson_s2_1, lesson_s2_2])
            db.session.commit()

            quiz_s2_1_1 = Quiz(lesson_id=lesson_s2_1.id, question='\'Me llamo Juan\' means:', options='His name is Juan,My name is Juan,Her name is Juan,I like Juan', correct_answer='My name is Juan', quiz_type='multiple_choice')
            quiz_s2_2_1 = Quiz(lesson_id=lesson_s2_2.id, question='\'¿Cómo estás?\' is used to ask about someone\'s age. (True/False)', options='True,False', correct_answer='False', quiz_type='true_false')
            db.session.add_all([quiz_s2_1_1, quiz_s2_2_1])
            db.session.commit()

            # --- French Course ---
            french_course = Course(
                language='French',
                level='Beginner',
                title='French for Beginners: Your First Steps in French',
                description='Start your French language adventure. This course covers essential vocabulary, basic grammar, and common conversational phrases for beginners.',
                image_url='images/french_course.png',
                learning_objectives='Understand and use basic French expressions for everyday situations. Introduce yourself, ask simple questions, and understand simple answers. Build a foundation for further French studies.'
            )
            db.session.add(french_course)
            db.session.commit()

            # French Module 1: Les Bases
            french_module1 = Module(course_id=french_course.id, title='Module 1: Bonjour! Getting Started with French', order=1, description='Greetings, the French alphabet, numbers, and basic introductions.')
            db.session.add(french_module1)
            db.session.commit()

            lesson_f1_1 = Lesson(module_id=french_module1.id, lesson_number=1, title='French Greetings and Politeness', content='Learn essential French greetings like \'Bonjour\' (Hello/Good day), \'Salut\' (Hi), and polite expressions like \'Merci\' (Thank you) and \'S\'il vous plaît\' (Please).', estimated_duration='25 mins')
            lesson_f1_2 = Lesson(module_id=french_module1.id, lesson_number=2, title='The French Alphabet and Pronunciation Basics', content='Explore the French alphabet and learn the sounds of French letters and common combinations. Pay attention to accents like é, è, ç.', video_url='https://www.youtube.com/embed/placeholder_video_id', estimated_duration='30 mins')
            lesson_f1_3 = Lesson(module_id=french_module1.id, lesson_number=3, title='Counting in French 0-20', content='Learn numbers from zero to twenty in French. Practice pronunciation and recognition.', estimated_duration='25 mins')
            db.session.add_all([lesson_f1_1, lesson_f1_2, lesson_f1_3])
            db.session.commit()

            quiz_f1_1_1 = Quiz(lesson_id=lesson_f1_1.id, question='How do you say \'Thank you\' in French?', options='Bonjour,Oui,Merci,Au revoir', correct_answer='Merci', quiz_type='multiple_choice')
            quiz_f1_2_1 = Quiz(lesson_id=lesson_f1_2.id, question='The cedilla (ç) changes the pronunciation of \'c\' before a, o, u. (True/False)', options='True,False', correct_answer='True', quiz_type='true_false')
            quiz_f1_3_1 = Quiz(lesson_id=lesson_f1_3.id, question='What is \'dix\' in English?', options='One,Five,Ten,Twelve', correct_answer='Ten', quiz_type='multiple_choice')
            db.session.add_all([quiz_f1_1_1, quiz_f1_2_1, quiz_f1_3_1])
            db.session.commit()

            # French Module 2: Basic Interactions
            french_module2 = Module(course_id=french_course.id, title='Module 2: Everyday French Conversations', order=2, description='Learn to introduce yourself, talk about your nationality, and ask for simple things.')
            db.session.add(french_module2)
            db.session.commit()

            lesson_f2_1 = Lesson(module_id=french_module2.id, lesson_number=1, title='Introducing Yourself in French', content='Learn phrases like \'Je m\'appelle...\' (My name is...) and \'Je suis...\' (I am...).', estimated_duration='30 mins')
            lesson_f2_2 = Lesson(module_id=french_module2.id, lesson_number=2, title='Asking \'How are you?\' and Responding', content='Learn different ways to ask \'How are you?\' (e.g., \'Comment ça va?\', \'Comment allez-vous?\') and common responses.', video_url='https://www.youtube.com/embed/placeholder_video_id', estimated_duration='35 mins')
            db.session.add_all([lesson_f2_1, lesson_f2_2])
            db.session.commit()

            quiz_f2_1_1 = Quiz(lesson_id=lesson_f2_1.id, question='\'Je m\'appelle Marie\' means:', options='I like Marie,My name is Marie,Her name is Marie,Where is Marie?', correct_answer='My name is Marie', quiz_type='multiple_choice')
            quiz_f2_2_1 = Quiz(lesson_id=lesson_f2_2.id, question='\'Ça va bien\' is a positive response to \'Comment ça va?\'. (True/False)', options='True,False', correct_answer='True', quiz_type='true_false')
            db.session.add_all([quiz_f2_1_1, quiz_f2_2_1])
            db.session.commit()

            # --- German Course ---
            german_course = Course(
                language='German',
                level='Beginner',
                title='German for Absolute Beginners',
                description='Begin your German learning experience. This course introduces basic vocabulary, grammar essentials, and simple conversational phrases.',
                image_url='images/german_course.png',
                learning_objectives='Understand and use very basic German phrases. Introduce yourself and others, ask and answer simple questions about personal details. Interact in a basic way if the other person speaks slowly.'
            )
            db.session.add(german_course)
            db.session.commit()

            # German Module 1: Grundlagen
            german_module1 = Module(course_id=german_course.id, title='Module 1: Hallo! Starting with German', order=1, description='Greetings, the German alphabet, numbers, and basic introductions.')
            db.session.add(german_module1)
            db.session.commit()

            lesson_g1_1 = Lesson(module_id=german_module1.id, lesson_number=1, title='German Greetings and Goodbyes', content='Learn common German greetings like \'Hallo\' (Hello), \'Guten Tag\' (Good day), and farewells like \'Tschüss\' (Bye) and \'Auf Wiedersehen\' (Goodbye - formal).', estimated_duration='25 mins')
            lesson_g1_2 = Lesson(module_id=german_module1.id, lesson_number=2, title='The German Alphabet and Umlauts', content='Discover the German alphabet, including the special characters ä, ö, ü, and ß. Practice pronunciation.', video_url='https://www.youtube.com/embed/placeholder_video_id', estimated_duration='30 mins')
            lesson_g1_3 = Lesson(module_id=german_module1.id, lesson_number=3, title='Counting in German 0-20', content='Learn numbers from zero to twenty in German. Practice with interactive exercises.', estimated_duration='25 mins')
            db.session.add_all([lesson_g1_1, lesson_g1_2, lesson_g1_3])
            db.session.commit()

            quiz_g1_1_1 = Quiz(lesson_id=lesson_g1_1.id, question='How do you say \'Good day\' in German?', options='Danke,Bitte,Guten Tag,Ja', correct_answer='Guten Tag', quiz_type='multiple_choice')
            quiz_g1_2_1 = Quiz(lesson_id=lesson_g1_2.id, question='The character \'ß\' is called an Eszett or sharp S. (True/False)', options='True,False', correct_answer='True', quiz_type='true_false')
            quiz_g1_3_1 = Quiz(lesson_id=lesson_g1_3.id, question='What is \'sieben\' in English?', options='Six,Seven,Eight,Nine', correct_answer='Seven', quiz_type='multiple_choice')
            db.session.add_all([quiz_g1_1_1, quiz_g1_2_1, quiz_g1_3_1])
            db.session.commit()

            # German Module 2: Basic Interactions
            german_module2 = Module(course_id=german_course.id, title='Module 2: Simple German Conversations', order=2, description='Learn to introduce yourself, state your origin, and ask basic questions.')
            db.session.add(german_module2)
            db.session.commit()

            lesson_g2_1 = Lesson(module_id=german_module2.id, lesson_number=1, title='Introducing Yourself in German', content='Learn phrases such as \'Ich heiße...\' (My name is...) and \'Ich komme aus...\' (I come from...).', estimated_duration='30 mins')
            lesson_g2_2 = Lesson(module_id=german_module2.id, lesson_number=2, title='Asking \'How are you?\' and Responding in German', content='Learn how to ask \'Wie geht es Ihnen?\' (How are you? - formal) or \'Wie geht\'s?\' (How are you? - informal) and typical responses.', video_url='https://www.youtube.com/embed/placeholder_video_id', estimated_duration='35 mins')
            db.session.add_all([lesson_g2_1, lesson_g2_2])
            db.session.commit()

            quiz_g2_1_1 = Quiz(lesson_id=lesson_g2_1.id, question='\'Ich heiße Anna\' means:', options='I like Anna,My name is Anna,She is Anna,Anna is here', correct_answer='My name is Anna', quiz_type='multiple_choice')
            quiz_g2_2_1 = Quiz(lesson_id=lesson_g2_2.id, question='\'Sehr gut\' (Very good) is a possible answer to \'Wie geht\'s?\'. (True/False)', options='True,False', correct_answer='True', quiz_type='true_false')
            db.session.add_all([quiz_g2_1_1, quiz_g2_2_1])
            db.session.commit()

            print("Initial Spoken Language course data (Spanish, French, German) created with modules, lessons, and quizzes.")
        else:
            print("Database already contains data. Skipping initial data creation.")

# API Endpoints (example)
@app.route('/api/languages')
def api_languages():
    # In a real app, this would query the Course table for distinct languages
    # For now, using placeholder data similar to memory
    languages = [{'name': 'Spanish', 'levels': ['Beginner', 'Intermediate', 'Advanced']},
                 {'name': 'French', 'levels': ['Beginner', 'Intermediate', 'Advanced']}]
    return {'languages': languages}

@app.route('/api/courses/<language_name>')
def api_courses_by_language(language_name):
    courses_data = Course.query.filter_by(language=language_name.capitalize()).all()
    return {'courses': [{'id': c.id, 'title': c.title, 'level': c.level, 'description': c.description} for c in courses_data]}


if __name__ == '__main__':
    with app.app_context():
        # Ensure the database file is gone for a truly fresh start
        db_uri = app.config['SQLALCHEMY_DATABASE_URI']
        db_path = None
        if db_uri.startswith('sqlite:///'):
            db_path_relative = db_uri.replace('sqlite:///', '')
            db_path = os.path.join(app.root_path, db_path_relative)
            print(f"Database file path determined to be: {db_path}")
            if os.path.exists(db_path):
                try:
                    os.remove(db_path)
                    print(f"Successfully DELETED existing database file: {db_path}")
                except OSError as e:
                    print(f"Error DELETING database file {db_path}: {e}. Proceeding.")
            else:
                print(f"Database file not found at {db_path}, will be created by SQLAlchemy.")
        else:
            print(f"Database URI ({db_uri}) is not for a local SQLite file. Skipping explicit file deletion.")

        try:
            print("Attempting to call db.metadata.drop_all(bind=db.engine) to clear existing schema...")
            db.metadata.drop_all(bind=db.engine) # Drop all tables based on current SQLAlchemy metadata
            print("db.metadata.drop_all() completed. Any existing tables defined in models should be dropped.")
        except Exception as e:
            print(f"Error during db.metadata.drop_all(): {e}. This might be okay if DB was empty or tables didn't exist.")

        try:
            print("Attempting to call db.create_all(bind=db.engine) to build schema...")
            db.create_all() # Create database tables if they don't exist
            print("Database tables successfully created/verified by db.create_all().")
        except Exception as e:
            print(f"CRITICAL Error during db.create_all(): {e}")
            raise # Re-raise the exception to halt execution if db.create_all() fails

        print("Attempting to call create_initial_data()...")
        create_initial_data() # Populate with initial data if empty
        print("create_initial_data() completed.")

    print("Starting Flask development server...")
    app.run(debug=True, port=5001)
