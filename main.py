from typing import List, Union
import flask
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename
from flask import Flask, render_template, request
from os.path import isfile
from hashlib import sha224
from json import dumps, loads
from mimetypes import guess_type
from random import choices
from waitress import serve
from sys import argv

DEBUG = "debug" in argv
SERVE = "serve" in argv


app = Flask(__name__)

class Post:
    def __init__(self, title: str, content: str, id: int, media_url: str=None) -> None:
        """
        Create a post object with a title and content
        @param title: Title of the post
        @param content: Content of the post
        @param id: ID of the post
        @param media_url: URL of the media of the post
        """
        self.title = title
        self.content = content
        self.media_url = media_url
        self.id = id
        self.media_type = self.get_media_type()
    
    def get_media_type(self):
        """Get the media type of a post's media url"""
        if not self.media_url:
            return None
        mimetype, enc = guess_type(self.media_url)
        if mimetype is None:
            return None
        name = mimetype.split("/")[0]
        if name in ["video", "image", "audio"]:
            return name
        return None

    def __str__(self) -> str:
        """Convert Post object to string"""
        return self.ToJson()
    
    def __eq__(self, other) -> bool:
        """check if a post is equal to another post"""
        return self.__str__() == other.__str__()
    
    def ToJson(self) -> str:
        """Convert a post to JSON"""
        return dumps({"title": self.title, "content": self.content, "id": self.id, "media_url": self.media_url})

def FromJson(json: str) -> Post:
    """Make a post from JSON string"""
    postdict = loads(json)
    return Post(postdict["title"], postdict["content"], postdict["id"], postdict["media_url"])

def GenerateId(postlist: list) -> int:
    """Generate an unique ID from the postlist"""
    n = -1
    unique = False
    while not unique:
        n += 1
        unique = all(post.id != n for post in postlist)
    return n

def MakePost(title: str, content: str, media_url: str=None, existing_posts: list=[]) -> Post:
    """Easier method to create a post"""
    post = Post(title, content, GenerateId(existing_posts), media_url)
    existing_posts.insert(0, post)
    return post

def GetPost(postlist: list, id: int) -> Union[Post, None]:
    """Get a post from the postlist with the given id"""
    for post in postlist:
        if post.id == id:
            return post
    return None

def get_posts(page: int) -> List[Post]:
    """Get posts per page"""
    if page > len(POSTS) // 50:
        page = 0
    start = int(page*50)
    return POSTS[start:start+50]

def GenerateSID(n=64) -> str:
    """Generate a n-sized string of random digits and letters"""
    return "".join(choices("abcdefghijklmnopqrstuvwxyz0123456789", k=n))

def StoreFile(file: FileStorage) -> str:
    """Takes in a FileStorage object and saves it and returns url"""
    ext = str(file.filename).split('.')[-1]
    data = file.stream.read()
    name = sha224(data).hexdigest()
    with open(secure_filename(f"./mediastorage/{name}.{ext}"), "wb") as f:
        f.write(data)
    return f"/media/{name}.{ext}"

@app.route('/')
@app.route('/index.html')
def index():
    cnt = len(POSTS) // 50
    page = request.args.get('page')
    if page and page.isdigit():
        page = int(page)
    else:
        page = 0
    template = render_template(
        "index.html",
        posts=get_posts(page),
        page = page,
        page_cnt = cnt
    )
    return flask.Response(template)

@app.route('/<path:path>')
def path(path):
    if isfile('root/' + path):
        return flask.send_file('root/' + path)
    else:
        return flask.render_template("errorpage.html", errorcode="404", errormessage="the requested page could not be found")

@app.route('/view')
@app.route("/view.html")
def view():
    post_id = request.args.get('id')
    if not post_id:
        return flask.redirect("/")

    post = GetPost(POSTS, int(post_id))
    if post:
        return render_template("view.html", post=post)
    else:
        return flask.redirect('/')

@app.route("/addpost", methods=['POST', 'GET'])
@app.route("/addpost.html", methods=['GET'])
def addpost():
    global POSTS
    if request.method != "POST":
        return flask.send_file('root/addpost.html')

    title = str(request.form.get('title'))
    media = request.files['media']
    if title:
        content = str(request.form.get('content'))
        if media:
            #protection agains bad files
            file_type = media.mimetype
            if not file_type or file_type.split("/")[0] not in [
                "video",
                "image",
                "audio"
            ]:
                return flask.redirect("/")

            url = StoreFile(media)
            MakePost(
                title, content,
                existing_posts=POSTS,
                media_url=url
            )
        elif content:
            MakePost(title, content,
                existing_posts=POSTS
            )
    return flask.redirect('/')

@app.route('/media/<path:path>')
def media(path):
    if len(path.split('/')) > 1:
        return flask.Response(status=404)
    return flask.send_file(f"./mediastorage/{path}")

@app.route('/favicon.ico')
def favicon():
    return flask.send_file("./root/favicon.png", mimetype="image/png")

if DEBUG:
    @app.route('/clearposts')
    def clearposts():
        global POSTS
        POSTS = []
        return flask.redirect('/')

    @app.route('/clearcookies')
    def clearcookies():
        r = flask.redirect("/")
        for cookie in request.cookies.keys():
            r.delete_cookie(cookie)
        return r

if __name__ == "__main__":
    POSTS = []
    if not SERVE:
        app.run('localhost', 80, DEBUG)
    else:
        from socket import gethostname, gethostbyname
        print("hosting on {}".format(gethostbyname(gethostname())))
        serve(app, host='0.0.0.0', port=80)