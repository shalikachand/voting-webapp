from flask import (
    Flask,
    render_template
)

import sqlite3

app = Flask(__name__)


@app.route("/")
def home():
    return render_template("home.html")


@app.route("/results")
def results():
    return render_template("results.html")

@app.route("/login")
def login():
    return render_template("login.html")

# abort 404

if __name__ == "__main__":  
    app.run(debug=True, host='0.0.0.0', port=5000)
