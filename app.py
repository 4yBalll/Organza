from flask import Flask
from config import Config
from extensions import db

from routes.main import main_bp
from routes.api import api_bp
from routes.auth import auth_bp
from routes.booking import booking_bp


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)

    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(booking_bp)

    with app.app_context():
        from models.tables import Table
        from models.users import User
        from models.reservations import Reservation, ReservationTable
        db.create_all()

    return app


app = create_app()

if __name__ == '__main__':
    app.run(debug=True)