import base64
import os
from io import BytesIO
from werkzeug.utils import secure_filename
from ZoroMusic import app
from flask import render_template, redirect, url_for, flash, request
from ZoroMusic.models import SignupForm, LoginForm, SongForm, PlaylistForm, AlbumForm, EditAlbumSongsForm
from ZoroMusic.models import User, Song, Playlist, Album, Like, DeletedSong
from ZoroMusic import db
from flask_login import login_user, logout_user, login_required, current_user
from os.path import basename, join
from sqlalchemy import or_
import matplotlib.pyplot as plt


@app.route('/')
@app.route('/landingPage')
def landing_page():
    return render_template('landingPage.html')


@app.route('/search', methods=['GET', 'POST'])
def search():
    if request.method == 'POST':
        search_query = request.form.get('search_query')
        songs = Song.query.all()
        results = (Song.query.filter(or_(
            Song.title.ilike(f"%{search_query}%"),
            Song.artist_name.ilike(f"%{search_query}%"),
            Song.genre.ilike(f"%{search_query}%")
        )).all())

        return render_template('search_results.html', results=results, query=search_query, songs=songs)

    return render_template('search.html')


@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    form = LoginForm()
    if form.validate_on_submit():
        form.username.data = 'admin'
        form.password.data = 'password'
        flash(f'Success! You are logged in as: Admin', category='success')
        return redirect(url_for('admin_dashboard'))
    return render_template('admin_login.html', form=form)


def generate_plot():
    songs = Song.query.all()
    genre_counts = {}
    for song in songs:
        genre = song.genre
        genre_counts[genre] = genre_counts.get(genre, 0) + 1
    genres = list(genre_counts.keys())
    song_counts = list(genre_counts.values())
    plt.switch_backend('Agg')
    plt.bar(genres, song_counts, color='blue')
    plt.xlabel('Genre')
    plt.ylabel('Number of Songs')
    plt.title('Number of Songs in Each Genre')
    plt.tight_layout()
    image_data = BytesIO()
    plt.savefig(image_data, format='png')
    image_data.seek(0)
    image_base64 = base64.b64encode(image_data.read()).decode('utf-8')
    image_path = 'static'
    if os.path.exists(image_path):
        os.remove(image_path)
    plt.savefig(image_path)
    plt.close()
    return image_base64


@app.route('/admin_dashboard')
def admin_dashboard():
    songs = Song.query.all()
    users = User.query.all()
    albums = Album.query.all()
    album_count = 0
    song_count = 0
    user_count = 0
    creator_count = 0
    image_base64 = generate_plot()
    for _ in albums:
        album_count += 1
    for _ in songs:
        song_count += 1
    for user in users:
        user_count += 1
        if user.role == "creator":
            creator_count += 1
    return render_template('admin_dashboard.html', song_count=song_count, user_count=user_count, creator_count=creator_count, album_count=album_count, image_base64=image_base64)


@app.route('/admin_delete_song/<int:song_id>')
def admin_delete_song(song_id):
    song = Song.query.get(song_id)
    if song:
        song.delete_song_and_related_records()
    flash('Song deleted successfully!', 'success')
    return redirect(url_for('songs_page'))


@app.route('/admin_del_songs')
def admin_del_songs():
    deleted_songs = DeletedSong.query.all()
    return render_template('admin_del_songs.html', deleted_songs=deleted_songs)


@app.route('/music')
@login_required
def music_page():
    songs = Song.query.order_by(Song.release_date.desc()).all()
    return render_template('music.html', songs=songs)


@app.route('/songs_page')
def songs_page():
    songs = Song.query.order_by(Song.release_date.desc()).all()
    return render_template('admin_songs.html', songs=songs)


@app.route('/signup', methods=['GET', 'POST'])
def signup_page():
    form = SignupForm()
    if form.validate_on_submit():
        user_to_create = User(username=form.username.data,
                              role=form.role.data,
                              password=form.pwd1.data)
        db.session.add(user_to_create)
        db.session.commit()
        login_user(user_to_create)
        flash(f'Account created successfully! You are logged in as: {user_to_create.username}', category='success')
        return redirect(url_for('music_page'))
    if form.errors != {}:
        for error in form.errors.values():
            flash(error, category='danger')
    return render_template('signup.html', form=form)


@app.route('/login', methods=['GET', 'POST'])
def login_page():
    form = LoginForm()
    if form.validate_on_submit():
        attempted_user = User.query.filter_by(username=form.username.data).first()
        if attempted_user and attempted_user.check_password_correction(attempted_password=form.password.data):
            login_user(attempted_user)
            flash(f'Success! You are logged in as: {attempted_user.username}', category='success')
            return redirect(url_for('music_page'))
        else:
            flash('Username and Password do not match! Please try again', category='danger')
    return render_template('login.html', form=form)


@app.route('/logout')
def logout_page():
    logout_user()
    flash("You have been logged out!", category='info')
    return redirect(url_for("landing_page"))


@app.route('/creator_dashboard')
@login_required
def creator_dashboard():
    songs = Song.query.filter_by(creator_id=current_user.id).all()
    return render_template('creator_dashboard.html', songs=songs)


@app.route('/register_as_creator', methods=['GET', 'POST'])
def register_as_creator():
    current_user.role = 'creator'
    db.session.commit()
    return redirect(url_for('profile_page'))


@app.route('/lyrics/<int:song_id>')
def lyrics(song_id):
    song = Song.query.get(song_id)
    return render_template('lyrics.html', song=song)


@app.route('/add_song', methods=['GET', 'POST'])
@login_required
def add_song():
    form = SongForm()

    if form.validate_on_submit():
        audio_file = form.audio_link.data

        if audio_file:
            filename = secure_filename(audio_file.filename)
            file_path = join(app.config['UPLOAD_FOLDER'], filename)
            audio_file.save(file_path)
            relative_path = 'Songs/' + basename(file_path)
        else:
            relative_path = None

        new_song = Song(title=form.title.data, lyrics=form.lyrics.data, duration=form.duration.data, genre=form.genre.data, artist_name=form.artist_name.data, release_date=form.release_date.data, audio_link=relative_path, creator=current_user)

        db.session.add(new_song)
        db.session.commit()

        flash('Song added successfully!', 'success')
        return redirect(url_for('creator_dashboard'))

    return render_template('add_song.html', form=form)


@app.route('/add_album', methods=['GET', 'POST'])
@login_required
def add_album():
    form = AlbumForm()
    form.songs.choices = [(song.id, song.title) for song in current_user.songs]

    if form.validate_on_submit():
        title, description, genre = form.title.data, form.description.data, form.genre.data
        selected_song_ids = form.songs.data

        album = Album(title=title, description=description, genre=genre, creator=current_user)

        for song_id in selected_song_ids:
            song = Song.query.get(song_id)
            if song:
                album.songs.append(song)

        db.session.add(album)
        db.session.commit()

        flash('Album created successfully!', 'success')
        return redirect(url_for('creator_dashboard'))

    return render_template('add_album.html', form=form)


@app.route('/edit_song/<int:song_id>', methods=['GET', 'POST'])
@login_required
def edit_song(song_id):
    song = Song.query.get(song_id)

    if not song or song.creator != current_user:
        flash('Song not found or you do not have permission to edit.', 'error')
        return redirect(url_for('creator_dashboard'))

    form = SongForm(obj=song)

    if form.validate_on_submit():
        audio_file = form.audio_link.data

        if audio_file:
            filename = secure_filename(audio_file.filename)

            file_path = join(app.config['UPLOAD_FOLDER'], filename)
            audio_file.save(file_path)

            relative_path = 'Songs/' + basename(file_path)
            song.audio_link = relative_path
        else:
            song.audio_link = None

        song.title = form.title.data
        song.lyrics = form.lyrics.data
        song.duration = form.duration.data
        song.genre = form.genre.data
        song.artist_name = form.artist_name.data

        db.session.commit()

        flash('Song updated successfully!', 'success')
        return redirect(url_for('creator_dashboard'))

    return render_template('edit_song.html', form=form, song=song)


@app.route('/delete_song/<int:song_id>', methods=['GET', 'POST'])
@login_required
def delete_song(song_id):
    song = Song.query.get(song_id)
    if song:
        song.delete_song_and_related_records()
    flash('Song deleted successfully!', 'success')
    return redirect(url_for('creator_dashboard'))


@app.route('/playlists', methods=['GET'])
@login_required
def playlists_page():
    playlists = Playlist.query.filter_by(user_id=current_user.id).all()
    return render_template('playlists.html', playlists=playlists)


@app.route('/create_playlist', methods=['GET', 'POST'])
@login_required
def create_playlist():
    form = PlaylistForm()

    form.songs.choices = [(song.id, f'{song.title} by {song.artist_name}') for song in Song.query.all()]

    if form.validate_on_submit():
        new_playlist = Playlist(name=form.name.data, user=current_user)
        db.session.add(new_playlist)
        db.session.commit()

        selected_songs = Song.query.filter(Song.id.in_(form.songs.data)).all()
        for song in selected_songs:
            new_playlist.add_song(song)

        flash('Playlist created successfully!', 'success')
        return redirect(url_for('playlists_page'))

    return render_template('create_playlist.html', form=form)


@app.route('/delete_playlist/<int:playlist_id>', methods=['POST'])
@login_required
def delete_playlist(playlist_id):
    playlist = Playlist.query.get_or_404(playlist_id)

    if playlist.user != current_user:
        flash("You don't have permission to delete this playlist.", 'danger')
        return redirect(url_for('playlists_page'))

    db.session.delete(playlist)
    db.session.commit()

    flash('Playlist deleted successfully!', 'success')
    return redirect(url_for('playlists_page'))


@app.route('/modify_playlist/<int:playlist_id>', methods=['GET', 'POST'])
@login_required
def modify_playlist(playlist_id):
    target_playlist = Playlist.query.get_or_404(playlist_id)

    if target_playlist.user != current_user:
        flash('You lack the authorization to modify this playlist.', 'danger')
        return redirect(url_for('playlists_page'))

    all_songs = Song.query.all()

    form = PlaylistForm(obj=target_playlist)
    form.songs.choices = [(song.id, song.title) for song in all_songs]

    if form.validate_on_submit():
        target_playlist.name = form.name.data

        target_playlist.songs.clear()
        selected_song_ids = form.songs.data
        selected_songs = Song.query.filter(Song.id.in_(selected_song_ids)).all()
        target_playlist.songs.extend(selected_songs)

        db.session.commit()
        flash('Playlist successfully updated!', 'success')
        return redirect(url_for('playlists_page'))

    return render_template('modify_playlist.html', form=form, playlist=target_playlist, all_songs=all_songs)


@app.route('/album/<int:album_id>/songs')
def album_songs(album_id):
    album = Album.query.get_or_404(album_id)
    songs = album.songs

    return render_template('album_songs.html', album=album, songs=songs)


@app.route('/add_edit_album/<int:album_id>', methods=['GET', 'POST'])
@login_required
def add_edit_album(album_id):
    album = Album.query.get_or_404(album_id)

    if album.creator != current_user:
        flash("You don't have permission to edit songs in this album.", 'danger')
        return redirect(url_for('album_songs', album_id=album.id))

    current_user_id = current_user.id
    available_songs = Song.query.filter_by(creator_id=current_user_id).all()

    form = EditAlbumSongsForm(obj=album)
    form.songs.choices = [(song.id, song.title) for song in available_songs]

    if form.validate_on_submit():
        album.songs.clear()
        selected_song_ids = form.songs.data
        selected_songs = Song.query.filter(Song.id.in_(selected_song_ids)).all()
        album.songs.extend(selected_songs)
        db.session.commit()

        flash('Songs in the album updated successfully!', 'success')
        return redirect(url_for('album_songs', album_id=album.id))

    return render_template('edit_album_songs.html', form=form, album=album, available_songs=available_songs)


@app.route('/like_dislike/<int:song_id>/<int:value>', methods=['POST'])
def like_dislike(song_id, value):
    user_id = current_user.id
    existing_like = Like.query.filter_by(song_id=song_id, user_id=user_id).first()

    if existing_like:
        existing_like.value = value
        db.session.commit()
    else:
        new_like = Like(value=value, song_id=song_id, user_id=user_id)
        db.session.add(new_like)
        db.session.commit()

    return redirect(url_for('music_page'))


@app.route('/change_flag/<int:user_id>', methods=['POST'])
def change_flag(user_id):
    user = User.query.get_or_404(user_id)

    user.is_flagged = not user.is_flagged
    db.session.commit()

    flash(f'Flag status for {user.username} changed successfully!', 'success')
    return redirect(url_for('admin_creators'))


@app.route("/admin_creators", methods=['GET', 'POST'])
def admin_creators():
    users = User.query.filter_by(role="creator").all()
    return render_template('admin_creators.html', users=users)


@app.route("/profile", methods=['GET', 'POST'])
@login_required
def profile_page():
    albums = Album.query.all()
    return render_template('profile.html', albums=albums)


