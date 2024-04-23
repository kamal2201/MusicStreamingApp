from ZoroMusic import bcrypt, db, login_manager
from flask_login import UserMixin
from datetime import datetime
from sqlalchemy import Sequence
from flask_wtf import FlaskForm
from flask_wtf.file import FileRequired, FileAllowed
from wtforms import StringField, PasswordField, SubmitField, SelectField, TextAreaField, IntegerField, FileField, \
    SelectMultipleField, widgets
from wtforms.validators import DataRequired, EqualTo, ValidationError, Length, URL, InputRequired


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


class User(db.Model, UserMixin):
    id = db.Column(db.Integer(), Sequence('user_id_seq', start=1, increment=1), primary_key=True)
    username = db.Column(db.String(length=30), nullable=False, unique=True)
    password_hash = db.Column(db.String(length=128), nullable=False)
    role = db.Column(db.String(length=15), nullable=False)
    is_flagged = db.Column(db.Boolean(), default=False)

    @property
    def password(self):
        return self.password

    @password.setter
    def password(self, plain_text_password):
        self.password_hash = bcrypt.generate_password_hash(plain_text_password).decode('utf-8')

    def check_password_correction(self, attempted_password):
        return bcrypt.check_password_hash(self.password_hash, attempted_password)


class Song(db.Model, UserMixin):
    id = db.Column(db.Integer, Sequence('song_id_seq', start=1, increment=1), primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    lyrics = db.Column(db.Text, nullable=False)
    duration = db.Column(db.Integer, nullable=False)
    genre = db.Column(db.String(20), nullable=False)
    artist_name = db.Column(db.String(100), nullable=False)
    release_date = db.Column(db.String(5))
    audio_link = db.Column(db.String(255), nullable=True)
    rating = db.Column(db.Float, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    creator_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    likes = db.relationship('Like', backref='song', lazy='dynamic')
    creator = db.relationship('User', backref='songs')

    def delete_song_and_related_records(self):
        deleted_song = DeletedSong(
            title=self.title,
            artist=self.artist_name,
            genre=self.genre
        )
        db.session.add(deleted_song)
        db.session.query(Like).filter(Like.song_id == self.id).delete()
        db.session.execute(album_songs.delete().where(album_songs.c.song_id == self.id))
        db.session.execute(songs_playlists.delete().where(songs_playlists.c.song_id == self.id))
        db.session.delete(self)
        db.session.commit()

    def calculate_rating(self):
        total_likes = Like.query.filter_by(song_id=self.id, value=True).count()
        total_dislikes = Like.query.filter_by(song_id=self.id, value=False).count()

        total_votes = total_likes + total_dislikes

        if total_votes == 0:
            return 0

        rating = (total_likes / total_votes) * 100
        return round(rating, 2)


songs_playlists = db.Table('songs_playlists',
    db.Column('song_id', db.Integer, db.ForeignKey('song.id'), primary_key=True),
    db.Column('playlist_id', db.Integer, db.ForeignKey('playlist.id'), primary_key=True)
)


class Playlist(db.Model, UserMixin):
    id = db.Column(db.Integer, Sequence('playlist_id_seq', start=1, increment=1), primary_key=True)
    name = db.Column(db.String(50), nullable=False)

    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship('User', backref='playlists')

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    songs = db.relationship('Song', secondary=songs_playlists, backref=db.backref('playlists', lazy='dynamic'))

    def __repr__(self):
        return f"Playlist('{self.name}', '{self.user.username}')"

    def add_song(self, song):
        if song not in self.songs:
            self.songs.append(song)
            db.session.commit()

    def remove_song(self, song):
        if song in self.songs:
            self.songs.remove(song)
            db.session.commit()


class Album(db.Model, UserMixin):
    id = db.Column(db.Integer, Sequence('album_id_seq', start=1, increment=1), primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    genre = db.Column(db.String(20), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    creator_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    creator = db.relationship('User', backref='albums')

    songs = db.relationship('Song', secondary='album_songs', backref=db.backref('albums', lazy='dynamic'))

    def __repr__(self):
        return f"Album('{self.title}', '{self.creator.username}')"

    def add_song(self, song):
        if song not in self.songs:
            self.songs.append(song)
            db.session.commit()

    def disassociate_deleted_song(self, deleted_song_id):
        self.songs = [song for song in self.songs if song.id != deleted_song_id]
        db.session.commit()


album_songs = db.Table('album_songs',
    db.Column('album_id', db.Integer, db.ForeignKey('album.id'), primary_key=True),
    db.Column('song_id', db.Integer, db.ForeignKey('song.id'), primary_key=True)
)


class Like(db.Model):
    id = db.Column(db.Integer, Sequence('like_id_seq', start=1, increment=1), primary_key=True)
    value = db.Column(db.Boolean(), nullable=True)
    song_id = db.Column(db.Integer, db.ForeignKey('song.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    liked_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"Rating('{self.value}', '{self.song.title}', '{self.user.username}')"


class DeletedSong(db.Model):
    id = db.Column(db.Integer, Sequence('deleted_song_id_seq', start=1, increment=1), primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    artist = db.Column(db.String(100), nullable=False)
    genre = db.Column(db.String(100), nullable=False)
    deleted_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"DeletedSong('{self.title}', '{self.artist}', '{self.genre}', '{self.deleted_at}')"


class SignupForm(FlaskForm):
    def validate_username(self, username_to_check):
        user = User.query.filter_by(username=username_to_check.data).first()
        if user:
            raise ValidationError('User already exists! Please try a different Username')

    username = StringField('Username', validators=[Length(min=3, max=30), DataRequired()])
    role = SelectField('Role', choices=[('creator', 'Creator'), ('user', 'User')], validators=[DataRequired()])
    pwd1 = PasswordField('Password', validators=[Length(min=6, max=60), DataRequired()])
    pwd2 = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('pwd1', message='Passwords must match')])
    submit = SubmitField(label='Create Account')


class LoginForm(FlaskForm):
    username = StringField(label='User Name:', validators=[DataRequired()])
    password = PasswordField(label='Password:', validators=[DataRequired()])
    submit = SubmitField(label='Login')


class SongForm(FlaskForm):
    title = StringField('Title', validators=[DataRequired(), Length(min=3, max=100)])
    lyrics = TextAreaField('Lyrics', validators=[DataRequired()])
    duration = IntegerField('Duration (seconds)', validators=[DataRequired()])
    genre = SelectField('Genre', choices=[
        ('rock', 'Rock'),
        ('pop', 'Pop'),
        ('hip_hop', 'Hip Hop'),
        ('electronic_dance', 'Electronic/Dance'),
        ('jazz', 'Jazz'),
    ], validators=[DataRequired()])
    artist_name = StringField('Artist Name', validators=[DataRequired(), Length(min=3, max=100)])
    release_date = StringField("Release Date", validators=[DataRequired(), Length(min=4, max=4)])
    audio_link = FileField('Audio Link', validators=[FileAllowed(['mp3'], 'MP3 Files only!')])

    submit = SubmitField('Add Song')


class PlaylistForm(FlaskForm):
    name = StringField('Playlist Name', validators=[DataRequired()])
    songs = SelectMultipleField('Songs', choices=[], coerce=int, widget=widgets.ListWidget(prefix_label=False), option_widget=widgets.CheckboxInput())
    submit = SubmitField('Create Playlist')


class AlbumForm(FlaskForm):
    title = StringField('Album Title', validators=[InputRequired()])
    description = TextAreaField('Description')
    genre = SelectField('Genre', choices=[
        ('rock', 'Rock'),
        ('pop', 'Pop'),
        ('hip_hop', 'Hip Hop'),
        ('electronic_dance', 'Electronic/Dance'),
        ('jazz', 'Jazz'),
        ('mixed', 'Mixed')
    ], validators=[InputRequired()])
    songs = SelectMultipleField('Select Songs', coerce=int, widget=widgets.ListWidget(prefix_label=False), option_widget=widgets.CheckboxInput())


class EditAlbumSongsForm(FlaskForm):
    songs = SelectMultipleField('Select Songs', coerce=int, widget=widgets.ListWidget(prefix_label=False), option_widget=widgets.CheckboxInput())

