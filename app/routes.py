# BHS Student council Flask web app
# Created 08/09/2024 by Shalika Chand
from app import app
from flask_sqlalchemy import SQLAlchemy
import os
import re
import base64
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask import (
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash
)

basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' +\
    os.path.join(basedir, "database.db")
db = SQLAlchemy(app)

import app.models as models

# secret key used to keep the session secure
SECRET_KEY = "3e4374ba682616c792e39b67a797570acbb448ac1a5950e9"
app.secret_key = SECRET_KEY

MIN_LENGTH = 8


def is_logged_in():
    """Check if the user is logged in by verifying session data"""
    return session.get("is_logged_in", False)


@app.context_processor
def inject_is_logged_in():
    """Inject session status for all routes"""
    return dict(is_logged_in=is_logged_in)


def validate_email(email):
    """Check if the email follows correct format 'xxxxx@burnside.school.nz'"""
    return re.match(r'^\d{5}@burnside\.school\.nz$', email) is not None


def is_valid_student_id(student_id):
    """Check if the student's id is currently as enrolled"""
    try:
        # get first two digits as the enrollment year
        enrollment = student_id[:2]

        enrollment_year = int("20" + enrollment)
        current_year = datetime.now().year

        # check if enrollment year is within 5-year window
        if current_year - 5 <= enrollment_year <= current_year:
            return True
        else:
            return False
    except ValueError:
        # if there's an issue with converting to an integer
        return False


def check_valid_id(id, model):
    """Check if a given ID exists in the provided table"""
    return db.session.query(model.query.filter_by(id=id).exists()).scalar()


def handle_login_error(username, password):
    """Handle login errors by checking username and password"""
    user = models.Admin.query.filter_by(username=username).first()
    if user is None:
        return "Account not found."
    if not check_password_hash(user.password_hash, password):
        return "Incorrect Password."
    return None


@app.route("/login", methods=["GET", "POST"])
def login():
    """If method is POST, validate login credential"""
    if request.method == "POST":
        # get username and password from the form
        username = request.form.get("username")
        password = request.form.get("password")
        # handle errors if username or password is incorrect
        error = handle_login_error(username, password)
        if error:
            return render_template("login.html", error=error)
        # successful login
        user = models.Admin.query.filter_by(username=username).first()
        session["user_id"] = user.id
        session["is_logged_in"] = True
        return redirect(url_for("success"))
    return render_template("login.html")


@app.route("/success")
def success():
    """Success page if user is logged in, otherwise redirect to login"""
    if is_logged_in():
        return render_template("tools.html", success="Successfully logged in.")
    return render_template("login.html", error="Session expired.")


@app.route("/")
def tools():
    """Show tools if user is logged in, otherwise redirect to login"""
    if not is_logged_in():
        return redirect(url_for("login"))
    return render_template("tools.html", logged_in=is_logged_in())


@app.route("/logout")
def logout():
    """Log user out by clearing session data and redirect to login"""
    session.pop("is_logged_in", None)
    session.pop("user_id", None)
    return redirect(url_for("login"))


@app.route('/vote', methods=['GET', 'POST'])
def vote():
    """Validate voters email and check if user has already voted"""
    error = None
    error = request.args.get("error")
    if request.method == 'POST':
        # get email and division from form
        email = request.form.get('email')
        division = request.form.get('division')

        # check email format and check if division is provided
        if not validate_email(email) or not division:
            error = "Invalid email format or missing division."
            return render_template('vote.html',
                                   divisions=models.Division.query.all(),
                                   error=error)

        # get student number from email
        student_number = email.split('@')[0]

        # if the user has already voted
        existing_vote = models.InAppResponse.query\
            .filter_by(student_number=student_number,
                       division=division).first()
        if existing_vote:
            error = "You have already voted."
            return render_template('vote.html',
                                   divisions=models.Division.query.all(),
                                   error=error)

        return redirect(url_for('select_nominees',
                                email=email,
                                division=division))

    return render_template('vote.html',
                           divisions=models.Division.query.all(),
                           error=error)


@app.route("/select-nominees", methods=["GET", "POST"])
def select_nominees():
    """Allow voter to select nominees"""
    email = request.args.get("email")
    division_id = request.args.get("division")

    # extract student number from the email
    student_number = email.split('@')[0]

    # check if student id is valid
    if not is_valid_student_id(student_number):
        error = "Invalid student ID. You are not currently enrolled."
        return redirect(url_for("vote", error=error))

    # check their email and division id
    if not validate_email(email) or not division_id:
        return redirect(url_for("vote"))

    # if division id exists
    if not check_valid_id(division_id, models.Division):
        return render_template("404.html"), 404

    # query nominees for the selected division
    nominees = db.session.query(models.Nominee)\
        .filter(models.Nominee.division == division_id)\
        .order_by(models.Nominee.last_name).all()

    # group nominees by year level
    nominees_by_year = {}
    for nominee in nominees:
        year_level = nominee.year_level_rel.year_level
        nominees_by_year.setdefault(year_level, []).append(nominee)

    # form submission
    if request.method == "POST":
        student_number = email.split('@')[0]  # get student number
        # get current UTC timestamp
        timestamp = datetime.now().astimezone()
        # create new vote response
        response = models.InAppResponse(
            division=division_id,
            student_number=student_number,
            email=email,
            timestamp=timestamp
        )
        db.session.add(response)
        db.session.flush()  # temporarily save to db

        # process selected nominees
        selected_nominees = []
        for year_level, nominees in nominees_by_year.items():
            nominee_id = request.form.get(f"nominee_{year_level}")
            if nominee_id:
                selected_nominees.append(models.NomineeBridge(
                    sid=response.id,
                    nid=int(nominee_id)
                ))

        # ensure at least one nominee is selected
        if not selected_nominees:
            db.session.rollback()
            return render_template("select-nominees.html",
                                   nominees_by_year=nominees_by_year,
                                   email=email, division_id=division_id)

        db.session.add_all(selected_nominees)
        db.session.commit()
        return redirect(url_for("success"))

    return render_template("select-nominees.html",
                           nominees_by_year=nominees_by_year,
                           email=email,
                           division_id=division_id)


@app.route("/select-division", methods=["POST"])
def select_division():
    """Handles division selection from form and redirects to results"""
    division_id = request.form.get("division")
    if division_id and check_valid_id(division_id, models.Division):
        return redirect(url_for("results", division=division_id))
    return redirect(url_for("results"))


@app.route("/results", methods=["GET"])
def results():
    """Displays results based on selected division and year level"""
    if not is_logged_in():
        return redirect(url_for("login"))

    # get division id and year level from query params
    division_id = request.args.get("division")
    selected_year_level = request.args.get("year_level")

    results = []
    year_levels = []

    if division_id:
        # show 404 if division id is invalid
        if not check_valid_id(division_id, models.Division):
            return render_template("404.html"), 404

        # get all year levels
        year_levels = db.session.query(models.YearLevel)\
            .order_by(models.YearLevel.year_level).all()

        # query to get nominees, their year levels, and vote counts
        query = db.session.query(
            models.Nominee.id,
            models.Nominee.first_name,
            models.Nominee.last_name,
            models.YearLevel.year_level,
            db.func.count(models.NomineeBridge.sid).label('votes')
        ).join(models.NomineeBridge,
               models.Nominee.id == models.NomineeBridge.nid)\
         .join(models.InAppResponse,
               models.NomineeBridge.sid == models.InAppResponse.id)\
         .join(models.YearLevel,
               models.Nominee.year_level == models.YearLevel.id)\
         .filter(models.Nominee.division == division_id)

        if selected_year_level:
            if not check_valid_id(selected_year_level, models.YearLevel):
                return render_template("404.html"), 404
            query = query\
                .filter(models.Nominee.year_level == selected_year_level)

        results = (
            query.group_by(models.Nominee.id)
            .order_by(db.func.count(models.NomineeBridge.sid).desc())
            .all()
        )

    divisions = db.session.query(models.Division).all()

    return render_template("results.html",
                           results=results,
                           divisions=divisions,
                           selected_division=division_id,
                           year_levels=year_levels,
                           selected_year_level=selected_year_level)


@app.route("/nominee-votes/<int:nominee_id>")
def nominee_votes(nominee_id):
    """Displays votes for a specific nominee"""
    if not is_logged_in():
        return redirect(url_for("login"))

    if not check_valid_id(nominee_id, models.Nominee):
        return render_template("404.html"), 404

    nominee = db.session.query(models.Nominee).filter_by(id=nominee_id).first()

    # query to get votes for nominee
    votes = db.session.query(
        models.InAppResponse.id,
        models.InAppResponse.email,
        models.InAppResponse.timestamp
    ).join(models.NomineeBridge,
           models.NomineeBridge.sid == models.InAppResponse.id)\
     .filter(models.NomineeBridge.nid == nominee_id)\
     .all()

    return render_template("nominee-votes.html", nominee=nominee, votes=votes)


@app.route("/remove-vote/<int:response_id>/<int:nominee_id>", methods=["POST"])
def remove_vote(response_id, nominee_id):
    """Removes a vote and updates database"""
    if not is_logged_in():
        return redirect(url_for("login"))

    if (
        not check_valid_id(response_id, models.InAppResponse) or
        not check_valid_id(nominee_id, models.Nominee)
    ):
        return render_template("404.html"), 404

    db.session.query(models.NomineeBridge)\
        .filter_by(sid=response_id, nid=nominee_id).delete()

    # check if there are remaining votes
    remaining_votes = db.session.query(models.NomineeBridge)\
        .filter_by(sid=response_id).count()
    if remaining_votes == 0:
        # remove response if no remaining votes
        db.session.query(models.InAppResponse)\
            .filter_by(id=response_id).delete()

    db.session.commit()

    return redirect(url_for("nominee_votes", nominee_id=nominee_id))


@app.route("/edit-nominees", methods=["GET"])
def edit_nominees():
    """Displays a form to edit nominees for selected division"""
    if not is_logged_in():
        return redirect(url_for("login"))

    division_id = request.args.get("division")
    nominees = []

    if division_id:
        if not check_valid_id(division_id, models.Division):
            return render_template("404.html"), 404

        # query to get nominees and their year levels for division
        nominees = db.session.query(
            models.Nominee,
            models.YearLevel.year_level
        ).join(
            models.YearLevel,
            models.Nominee.year_level == models.YearLevel.id
        ).filter(
            models.Nominee.division == division_id
        ).order_by(
            models.YearLevel.year_level
        ).all()

    divisions = db.session.query(models.Division).all()
    year_levels = db.session.query(models.YearLevel)\
        .order_by(models.YearLevel.year_level).all()

    return render_template("edit-nominees.html",
                           nominees=nominees,
                           divisions=divisions,
                           selected_division=division_id,
                           year_levels=year_levels)


@app.route("/edit-nominee/<int:nominee_id>", methods=["GET", "POST"])
def update_nominee(nominee_id):
    """Updates nominee details or displays form to edit nominee"""
    if not is_logged_in():
        return redirect(url_for("login"))

    nominee = models.Nominee.query.get(nominee_id)
    if not nominee:
        return render_template("404.html"), 404

    year_levels = db.session.query(models.YearLevel)\
        .order_by(models.YearLevel.year_level).all()

    if request.method == "POST":
        nominee.first_name = request.form.get("first_name")
        nominee.last_name = request.form.get("last_name")
        nominee.year_level = request.form.get("year_level")
        if 'photo' in request.files:
            file = request.files['photo']
            if file:
                nominee.photo = base64.b64encode(file.read()).decode('utf-8')
        db.session.commit()
        return redirect(url_for("edit_nominees", division=nominee.division))

    return render_template("update-nominee.html",
                           nominee=nominee,
                           year_levels=year_levels)


@app.route("/delete-nominee/<int:nominee_id>", methods=["POST"])
def delete_nominee(nominee_id):
    """Deletes a nominee from database"""
    if not is_logged_in():
        return redirect(url_for("login"))

    nominee = models.Nominee.query.get(nominee_id)
    if nominee:
        division_id = nominee.division
        db.session.delete(nominee)
        db.session.commit()
    return redirect(url_for("edit_nominees", division=division_id))


@app.route("/add-nominee", methods=["POST"])
def add_nominee():
    """Adds a new nominee to the database"""
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
    return redirect(url_for("edit_nominees", division=division))


@app.route("/create-new-form")
def create_new_form():
    """Clears all data and starts a new form"""
    if not is_logged_in():
        return redirect(url_for("login"))

    db.session.query(models.NomineeBridge).delete()
    db.session.query(models.Nominee).delete()
    db.session.query(models.InAppResponse).delete()
    db.session.commit()

    return redirect(url_for("edit_nominees"))


@app.route("/change-password", methods=["GET", "POST"])
def change_password():
    """Allows users to change their password"""
    if not is_logged_in():
        return redirect(url_for("login"))

    if request.method == "POST":
        current_password = request.form.get("current_password")
        new_password = request.form.get("new_password")
        confirm_password = request.form.get("confirm_password")

        user_id = session.get("user_id")
        user = models.Admin.query.get(user_id)

        if not check_password_hash(user.password_hash, current_password):
            flash("Incorrect current password.", "error")
            return render_template("change-password.html")

        if len(new_password) < MIN_LENGTH:
            flash("New password must be at least 8 characters long.", "error")
            return render_template("change-password.html")

        if new_password != confirm_password:
            flash("New password and confirm password do not match.", "error")
            return render_template("change-password.html")

        user.password_hash = generate_password_hash(new_password)
        db.session.commit()
        return render_template("change-password.html", success=True)

    return render_template("change-password.html")


@app.errorhandler(500)
def internal_server_error(error):
    """Handles internal server error"""
    error = "500 Internal server error"
    return render_template('error.html', error=error), 500


@app.errorhandler(404)
def page_not_found(error):
    """Handles 404 errors"""
    error = "404 Page not found"
    return render_template("error.html", error=error), 404


if __name__ == "__main__":
    app.run(debug=False, host='0.0.0.0', port=5000)
