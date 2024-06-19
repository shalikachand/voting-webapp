from app import app
from flask import render_template
from flask_sqlalchemy import SQLAlchemy
import os

basedir = os.path.abspath(os.path.dirname(__file__))
db = SQLAlchemy()
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, "database.db")
db.init_app(app)


import app.models as models


@app.route("/")
def home():
    responses = models.InAppResponse.query.all()
    print("All Responses:", responses)
    return render_template("home.html", responses=responses)


@app.route("/vote")
def vote():
    return render_template("vote.html")


@app.route("/nominees")
def nominees():
    return render_template("nominees.html")


@app.route("/tools")
def tools():
    return render_template("tools.html")


@app.route("/edit-nominees")
def edit_nominees():
    return render_template("edit-nominees.html")


@app.route("/results")
def results():
    return render_template("results.html")


# Handling errors
@app.errorhandler(404)
def page_not_found(error):
    # Error page for invalid URL
    return render_template("404.html"), 404

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)
