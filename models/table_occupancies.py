from extensions import db


class TableOccupancy(db.Model):
    __tablename__ = 'table_occupancies'

    id = db.Column(db.Integer, primary_key=True)

    table_id = db.Column(db.Integer, db.ForeignKey('tables.id'), nullable=False, index=True)

    opened_by_staff_id = db.Column(db.Integer, db.ForeignKey('staff_users.id'), nullable=True)
    closed_by_staff_id = db.Column(db.Integer, db.ForeignKey('staff_users.id'), nullable=True)

    source = db.Column(db.String(30), nullable=False, default='manual_block')
    status = db.Column(db.String(20), nullable=False, default='active')

    booking_date = db.Column(db.Date, nullable=False, index=True)
    time_start = db.Column(db.Time, nullable=False)
    time_end = db.Column(db.Time, nullable=False)

    comment = db.Column(db.Text)

    created_at = db.Column(db.DateTime, server_default=db.func.current_timestamp())
    closed_at = db.Column(db.DateTime, nullable=True)

    table = db.relationship('Table', backref='table_occupancies')
    opened_by_staff = db.relationship('StaffUser', foreign_keys=[opened_by_staff_id])
    closed_by_staff = db.relationship('StaffUser', foreign_keys=[closed_by_staff_id])

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'table_id': self.table_id,
            'opened_by_staff_id': self.opened_by_staff_id,
            'closed_by_staff_id': self.closed_by_staff_id,
            'source': self.source,
            'status': self.status,
            'booking_date': self.booking_date.isoformat() if self.booking_date else None,
            'time_start': self.time_start.strftime('%H:%M') if self.time_start else None,
            'time_end': self.time_end.strftime('%H:%M') if self.time_end else None,
            'comment': self.comment,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'closed_at': self.closed_at.isoformat() if self.closed_at else None,
        }