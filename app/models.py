from app.routes import db


class Admin(db.Model):
    __tablename__ = 'Admin'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String, nullable=False)
    password_hash = db.Column(db.String, nullable=False)


class NomineeBridge(db.Model):
    __tablename__ = 'NomineeBridge'
    sid = db.Column(db.Integer, db.ForeignKey('InAppResponse.id'), primary_key=True)
    nid = db.Column(db.Integer, db.ForeignKey('Nominee.id'), primary_key=True)


class Division(db.Model):
    __tablename__ = 'Division'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    division = db.Column(db.String, nullable=False)


class YearLevel(db.Model):
    __tablename__ = 'YearLevel'
    id = db.Column(db.Integer, primary_key=True)
    year_level = db.Column(db.Integer, nullable=False)


class InAppResponse(db.Model):
    __tablename__ = 'InAppResponse'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    division = db.Column(db.Integer, db.ForeignKey('Division.id'), nullable=False)
    student_number = db.Column(db.Integer, nullable=False)
    email = db.Column(db.String, nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False)
    # nominees = db.relationship('Nominee', secondary='NomineeBridge')


class Nominee(db.Model):
    __tablename__ = 'Nominee'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    last_name = db.Column(db.String, nullable=False)
    first_name = db.Column(db.String, nullable=False)
    year_level = db.Column(db.Integer, db.ForeignKey('YearLevel.id'), nullable=False)
    photo = db.Column(db.LargeBinary)
    division = db.Column(db.Integer, db.ForeignKey('Division.id'))
