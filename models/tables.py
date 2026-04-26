from extensions import db

class Table(db.Model):
    __tablename__ = 'tables'

    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.Integer, nullable=False)
    seats = db.Column(db.Integer, nullable=False)
    location = db.Column(db.String(255))
    description = db.Column(db.Text)
    image = db.Column(db.String(255))
    image_panorama = db.Column(db.String(255))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, server_default=db.func.current_timestamp())
