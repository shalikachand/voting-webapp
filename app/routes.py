from app import app
from flask_sqlalchemy import SQLAlchemy
import os
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
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, "database.db")
db = SQLAlchemy(app)

import app.models as models

# Random generated key to confirm individual user session
SECRET_KEY = "3e4374ba682616c792e39b67a797570acbb448ac1a5950e9"
app.secret_key = SECRET_KEY


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
        return render_template("tools.html", success="Successfully logged in.")
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


@app.route('/vote', methods=['GET', 'POST'])
def vote():
    error = None

    if request.method == 'POST':
        email = request.form.get('email')
        division = request.form.get('division')

        if email and '@' in email and division:
            student_number = email.split('@')[0]

            # Check if the user has already voted
            existing_vote = models.InAppResponse.query.filter_by(student_number=student_number, division=division).first()
            if existing_vote:
                error = "You have already voted."
                return render_template('vote.html', divisions=models.Division.query.all(), error=error)

            # Redirect to the select_nominees page and pass email and division as query parameters
            return redirect(url_for('select_nominees', email=email, division=division))

    divisions = models.Division.query.all()
    return render_template('vote.html', divisions=divisions, error=error)


@app.route("/select-nominees", methods=["GET", "POST"])
def select_nominees():
    email = request.args.get("email")
    division_id = request.args.get("division")

    # If email or division is not provided, redirect to vote page
    if not email or not division_id:
        flash("Invalid access. Please enter your email and division.")
        return redirect(url_for("vote"))

    # Query to get all nominees for the selected division
    nominees = db.session.query(models.Nominee).filter(
        models.Nominee.division == division_id
    ).order_by(models.Nominee.last_name).all()

    # Group nominees by year level
    nominees_by_year = {}
    for nominee in nominees:
        year_level = nominee.year_level_rel.year_level
        if year_level not in nominees_by_year:
            nominees_by_year[year_level] = []
        nominees_by_year[year_level].append(nominee)

    if request.method == "POST":
        student_number = email.split('@')[0]
        timestamp = datetime.utcnow()

        # Save response
        response = models.InAppResponse(
            division=division_id,
            student_number=student_number,
            email=email,
            timestamp=timestamp
        )
        db.session.add(response)
        db.session.flush()  # Get response.id before committing

        # Process nominee selections
        selected_nominees = []
        for year_level, nominees in nominees_by_year.items():
            nominee_id = request.form.get(f"nominee_{year_level}")
            if nominee_id:
                selected_nominees.append(models.NomineeBridge(
                    sid=response.id,
                    nid=int(nominee_id)
                ))

        # If no nominees were selected, show an error
        if not selected_nominees:
            db.session.rollback()  # Discard the response if no nominees are selected
            flash("Please select at least one nominee.")
            return render_template("select-nominees.html", nominees_by_year=nominees_by_year, email=email, division_id=division_id)

        # Save nominees
        db.session.add_all(selected_nominees)
        db.session.commit()

        # flash("Nominee selections saved successfully.")
        return redirect(url_for("success"))

    return render_template("select-nominees.html", nominees_by_year=nominees_by_year, email=email, division_id=division_id)


# New route to handle division selection via POST
@app.route("/select-division", methods=["POST"])
def select_division():
    division_id = request.form.get("division")
    if division_id:
        # Redirect to results with the selected division ID
        return redirect(url_for("results", division=division_id))
    return redirect(url_for("results"))


# results route
@app.route("/results", methods=["GET"])
def results():
    if not is_logged_in():
        return redirect(url_for("login"))

    division_id = request.args.get("division")
    selected_year_level = request.args.get("year_level")

    results = []
    year_levels = []

    if division_id:
        # Query all year levels to populate the dropdown
        year_levels = db.session.query(models.YearLevel).order_by(models.YearLevel.year_level).all()

        # Start building the query to get the results
        query = db.session.query(
            models.Nominee.id,  # Select the ID
            models.Nominee.first_name,
            models.Nominee.last_name,
            models.YearLevel.year_level,
            db.func.count(models.NomineeBridge.sid).label('votes')
        ).join(models.NomineeBridge, models.Nominee.id == models.NomineeBridge.nid)\
         .join(models.InAppResponse, models.NomineeBridge.sid == models.InAppResponse.id)\
         .join(models.YearLevel, models.Nominee.year_level == models.YearLevel.id)\
         .filter(models.Nominee.division == division_id)

        # Filter by selected year level if specified
        if selected_year_level:
            query = query.filter(models.Nominee.year_level == selected_year_level)

        results = query.group_by(models.Nominee.id)\
                       .order_by(db.func.count(models.NomineeBridge.sid).desc())\
                       .all()

    # Retrieve all divisions
    divisions = db.session.query(models.Division).all()

    return render_template("results.html", 
                           results=results, 
                           divisions=divisions, 
                           selected_division=division_id, 
                           year_levels=year_levels, 
                           selected_year_level=selected_year_level)


@app.route("/nominee-votes/<int:nominee_id>")
def nominee_votes(nominee_id):
    if not is_logged_in():
        return redirect(url_for("login"))

    # Query nominee information
    nominee = db.session.query(models.Nominee).filter_by(id=nominee_id).first()

    # Query all votes for this nominee
    votes = db.session.query(
        models.InAppResponse.id,
        models.InAppResponse.email,
        models.InAppResponse.timestamp
    ).join(models.NomineeBridge, models.NomineeBridge.sid == models.InAppResponse.id)\
     .filter(models.NomineeBridge.nid == nominee_id)\
     .all()

    return render_template("nominee-votes.html", nominee=nominee, votes=votes)


@app.route("/remove-vote/<int:response_id>/<int:nominee_id>", methods=["POST"])
def remove_vote(response_id, nominee_id):
    if not is_logged_in():
        return redirect(url_for("login"))

    # Delete the entry from NomineeBridge table
    db.session.query(models.NomineeBridge).filter_by(sid=response_id, nid=nominee_id).delete()

    # Check if this response was the only vote in the NomineeBridge table
    remaining_votes = db.session.query(models.NomineeBridge).filter_by(sid=response_id).count()
    if remaining_votes == 0:
        # If no more votes are linked to this response, delete the response itself
        db.session.query(models.InAppResponse).filter_by(id=response_id).delete()

    db.session.commit()

    return redirect(url_for("nominee_votes", nominee_id=nominee_id))


@app.route("/edit-nominees", methods=["GET"])
def edit_nominees():
    if not is_logged_in():
        return redirect(url_for("login"))

    division_id = request.args.get("division")
    if division_id:
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
        division = db.session.query(models.Division).filter_by(id=division_id).first()
    else:
        nominees = []
        division = None

    # Retrieve all divisions and year levels
    divisions = db.session.query(models.Division).all()
    year_levels = db.session.query(models.YearLevel).order_by(models.YearLevel.year_level).all()

    return render_template("edit-nominees.html",
                           nominees=nominees,
                           divisions=divisions,
                           selected_division=division_id,
                           year_levels=year_levels)


@app.route("/edit-nominee/<int:nominee_id>", methods=["GET", "POST"])
def update_nominee(nominee_id):
    if not is_logged_in():
        return redirect(url_for("login"))

    nominee = models.Nominee.query.get(nominee_id)
    year_levels = db.session.query(models.YearLevel).order_by(models.YearLevel.year_level).all()

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
            return redirect(url_for("edit_nominees", division=nominee.division))

    return render_template("update-nominee.html", nominee=nominee, year_levels=year_levels)


@app.route("/delete-nominee/<int:nominee_id>", methods=["POST"])
def delete_nominee(nominee_id):
    if not is_logged_in():
        return redirect(url_for("login"))
    nominee = models.Nominee.query.get(nominee_id)
    if nominee:
        division_id = nominee.division
        db.session.delete(nominee)
        db.session.commit()
        # flash("Nominee deleted successfully.")
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
    # flash("Nominee added successfully.")
    return redirect(url_for("edit_nominees", division=division))


@app.route("/create-new-form")
def create_new_form():
    if not is_logged_in():
        return redirect(url_for("login"))

    # Delete all entries from NomineeBridge, Nominee, and InAppResponse tables
    db.session.query(models.NomineeBridge).delete()
    db.session.query(models.Nominee).delete()
    db.session.query(models.InAppResponse).delete()
    db.session.commit()

    # flash("All vote data has been erased. You can now start a new form.")
    return redirect(url_for("edit_nominees"))


@app.route("/change-password", methods=["GET", "POST"])
def change_password():
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

        if len(new_password) < 8:
            flash("New password must be at least 8 characters long.", "error")
            return render_template("change-password.html")

        if new_password != confirm_password:
            flash("New password and confirm password do not match.", "error")
            return render_template("change-password.html")

        # Update the password hash
        user.password_hash = generate_password_hash(new_password)
        db.session.commit()

        flash("Password changed successfully.", "success")
        return render_template("change-password.html", success=True)

    return render_template("change-password.html")


@app.errorhandler(404)
def page_not_found(error):
    return render_template("404.html"), 404


if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)
