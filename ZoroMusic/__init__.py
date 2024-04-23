from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///ZoroMusic.db'
app.config['SECRET_KEY'] = 'c2bc341a9651bf6458c6423c'
app.config['UPLOAD_FOLDER'] = 'ZoroMusic/static/Songs'
db = SQLAlchemy(app)
app.app_context().push()
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = "login_page"
login_manager.login_message_category = "info"
from ZoroMusic import routes

