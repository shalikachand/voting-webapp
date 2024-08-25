from app import app
from flask import render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
import os
import base64
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, "database.db")
db = SQLAlchemy(app)

import app.models as models

# Random generated key to confirm individual user session
SECRET_KEY = "3e4374ba682616c792e39b67a797570acbb448ac1a5950e9"
app.secret_key = SECRET_KEY

# Login system
def is_logged_in():
    return session.get("is_logged_in", False)

@app.context_processor
def inject_is_logged_in():
    return dict(is_logged_in=is_logged_in)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        user = models.Admin.query.filter_by(username=username).first()
        if user is None:
            return render_template("login.html", error="Account not found.")
        if not check_password_hash(user.password_hash, password):
            return render_template("login.html", error="Incorrect Password.")
        session["user_id"] = user.id
        session["is_logged_in"] = True
        return redirect(url_for("success"))
    return render_template("login.html")

@app.route("/success")
def success():
    if is_logged_in():
        return render_template("tools.html")
    else:
        return render_template("login.html", error="Session expired.")

@app.route("/")
def tools():
    if not is_logged_in():
        return redirect(url_for("login"))
    return render_template("tools.html", logged_in=is_logged_in())

@app.route("/logout")
def logout():
    session.pop("is_logged_in", None)
    session.pop("user_id", None)
    return redirect(url_for("login"))

@app.route("/vote")
def vote():
    divisions = db.session.query(models.Division).all()
    return render_template("vote.html", divisions=divisions)

@app.route("/nominees")
def nominees():
    return render_template("nominees.html")

@app.route("/results")
def results():
    if not is_logged_in():
        return redirect(url_for("login"))
    divisions = db.session.query(models.Division).all()
    division_stats = []
    for division in divisions:
        year_levels = db.session.query(models.YearLevel).all()
        division_data = {
            "division": division.division,
            "year_levels": []
        }
        for year_level in year_levels:
            year_nominees = db.session.query(models.Nominee).filter_by(year_level=year_level.id, division=division.id).all()
            year_votes = {
                "year_level": year_level.year_level,
                "nominees": []
            }
            for nominee in year_nominees:
                votes_count = db.session.query(models.NomineeBridge).filter_by(nid=nominee.id).count()
                year_votes["nominees"].append({
                    "first": f"{nominee.first_name}",
                    "last": f"{nominee.last_name}",
                    "votes": votes_count
                })
            division_data["year_levels"].append(year_votes)
        division_stats.append(division_data)
    return render_template("results.html", division_stats=division_stats)

@app.route("/edit-nominees", methods=["GET"])
def edit_nominees():
    if not is_logged_in():
        return redirect(url_for("login"))

    division_id = request.args.get("division")
    if division_id:
        # Retrieve nominees for the selected division, sorted by year level
        nominees = db.session.query(models.Nominee).filter_by(division=division_id).order_by(models.Nominee.year_level).all()
        division = db.session.query(models.Division).filter_by(id=division_id).first()
    else:
        nominees = []
        division = None

    # Retrieve all divisions
    divisions = db.session.query(models.Division).all()

    return render_template("edit-nominees.html", nominees=nominees, divisions=divisions, selected_division=division_id)


@app.route("/edit-nominee/<int:nominee_id>", methods=["GET", "POST"])
def update_nominee(nominee_id):
    if not is_logged_in():
        return redirect(url_for("login"))
    nominee = models.Nominee.query.get(nominee_id)
    if request.method == "POST":
        if nominee:
            nominee.first_name = request.form.get("first_name")
            nominee.last_name = request.form.get("last_name")
            nominee.year_level = request.form.get("year_level")
            if 'photo' in request.files:
                file = request.files['photo']
                if file:
                    nominee.photo = base64.b64encode(file.read()).decode('utf-8')
            db.session.commit()
            flash("Nominee updated successfully.")
        return redirect(url_for("edit_nominees", division=nominee.division))
    return render_template("update-nominee.html", nominee=nominee)

@app.route("/delete-nominee/<int:nominee_id>", methods=["POST"])
def delete_nominee(nominee_id):
    if not is_logged_in():
        return redirect(url_for("login"))
    nominee = models.Nominee.query.get(nominee_id)
    if nominee:
        division_id = nominee.division
        db.session.delete(nominee)
        db.session.commit()
        flash("Nominee deleted successfully.")
    return redirect(url_for("edit_nominees", division=division_id))

@app.route("/add-nominee", methods=["POST"])
def add_nominee():
    if not is_logged_in():
        return redirect(url_for("login"))
    first_name = request.form.get("first_name")
    last_name = request.form.get("last_name")
    year_level = request.form.get("year_level")
    division = request.form.get("division")
    photo = None
    if 'photo' in request.files:
        file = request.files['photo']
        if file:
            photo = base64.b64encode(file.read()).decode('utf-8')
    new_nominee = models.Nominee(
        first_name=first_name,
        last_name=last_name,
        year_level=year_level,
        division=division,
        photo=photo
    )
    db.session.add(new_nominee)
    db.session.commit()
    flash("Nominee added successfully.")
    return redirect(url_for("edit_nominees", division=division))

@app.errorhandler(404)
def page_not_found(error):
    return render_template("404.html"), 404

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)
