from extensions import db


class Reservation(db.Model):
    __tablename__ = 'reservations'

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey('users.id'),
        nullable=False,
        index=True
    )

    booking_date = db.Column(db.Date, nullable=False, index=True)
    time_start = db.Column(db.Time, nullable=False)
    time_end = db.Column(db.Time, nullable=False)

    status = db.Column(db.String(20), nullable=False, default='active', index=True)
    comment = db.Column(db.Text)

    created_at = db.Column(
        db.DateTime,
        server_default=db.func.current_timestamp(),
        nullable=False
    )

    user = db.relationship(
        'User',
        backref=db.backref('reservations', lazy=True)
    )

    reservation_tables = db.relationship(
        'ReservationTable',
        back_populates='reservation',
        cascade='all, delete-orphan',
        lazy=True
    )

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'booking_date': self.booking_date.isoformat() if self.booking_date else None,
            'time_start': self.time_start.strftime('%H:%M') if self.time_start else None,
            'time_end': self.time_end.strftime('%H:%M') if self.time_end else None,
            'status': self.status,
            'comment': self.comment,
            'table_ids': [item.table_id for item in self.reservation_tables],
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

    def __repr__(self):
        return f'<Reservation {self.id}: user={self.user_id}, date={self.booking_date}>'


class ReservationTable(db.Model):
    __tablename__ = 'reservation_tables'

    id = db.Column(db.Integer, primary_key=True)

    reservation_id = db.Column(
        db.Integer,
        db.ForeignKey('reservations.id'),
        nullable=False,
        index=True
    )

    table_id = db.Column(
        db.Integer,
        db.ForeignKey('tables.id'),
        nullable=False,
        index=True
    )

    created_at = db.Column(
        db.DateTime,
        server_default=db.func.current_timestamp(),
        nullable=False
    )

    __table_args__ = (
        db.UniqueConstraint(
            'reservation_id',
            'table_id',
            name='uq_reservation_table_pair'
        ),
    )

    reservation = db.relationship(
        'Reservation',
        back_populates='reservation_tables'
    )

    table = db.relationship(
        'Table',
        backref=db.backref('reservation_links', lazy=True)
    )

    def to_dict(self):
        return {
            'id': self.id,
            'reservation_id': self.reservation_id,
            'table_id': self.table_id,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

    def __repr__(self):
        return f'<ReservationTable reservation={self.reservation_id}, table={self.table_id}>'