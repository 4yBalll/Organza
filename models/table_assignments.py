from extensions import db


class TableAssignment(db.Model):
    __tablename__ = 'table_assignments'

    id = db.Column(db.Integer, primary_key=True)

    table_id = db.Column(db.Integer, db.ForeignKey('tables.id'), nullable=False, index=True)
    staff_user_id = db.Column(db.Integer, db.ForeignKey('staff_users.id'), nullable=False, index=True)

    shift_date = db.Column(db.Date, nullable=False, index=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    created_at = db.Column(db.DateTime, server_default=db.func.current_timestamp())

    table = db.relationship('Table', backref='table_assignments')
    staff_user = db.relationship('StaffUser', backref='table_assignments')

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'table_id': self.table_id,
            'staff_user_id': self.staff_user_id,
            'shift_date': self.shift_date.isoformat() if self.shift_date else None,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }