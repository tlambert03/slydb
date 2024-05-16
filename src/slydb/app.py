from pathlib import Path

from flask import Flask, render_template, request, url_for
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.debug = True
app.config["UPLOAD_FOLDER"] = Path("uploads")


@app.route("/")
def hello_world():
    return render_template("index.html", upload_url=url_for(upload_file.__name__))


@app.route("/upload", methods=["POST"])
def upload_file():
    file = request.files["file"]
    filename = secure_filename(file.filename)
    dest: Path = app.config["UPLOAD_FOLDER"]
    dest.mkdir(exist_ok=True, parents=True)
    file.save(dest / filename)
    return "File uploaded successfully"


def main():
    app.run()
