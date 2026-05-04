from datetime import date, datetime, time
from functools import wraps

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from extensions import db
from models.staff_users import StaffUser
from models.reservations import Reservation, ReservationTable
from models.users import User
from models.tables import Table
from models.table_occupancies import TableOccupancy
from models.table_assignments import TableAssignment


admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

RESTAURANT_OPEN_TIME = time(10, 0)
RESTAURANT_CLOSE_TIME = time(22, 0)


def get_current_staff():
    staff_id = session.get('admin_staff_id')
    if not staff_id:
        return None

    return StaffUser.query.filter_by(id=staff_id, is_active=True).first()


def login_required(view_func):
    @wraps(view_func)
    def wrapped_view(*args, **kwargs):
        staff = get_current_staff()
        if not staff:
            flash('Для входа в админ-панель выполните авторизацию.', 'error')
            return redirect(url_for('admin.login'))

        return view_func(*args, **kwargs)

    return wrapped_view


def admin_required(view_func):
    @wraps(view_func)
    def wrapped_view(*args, **kwargs):
        staff = get_current_staff()
        if not staff:
            flash('Для входа в админ-панель выполните авторизацию.', 'error')
            return redirect(url_for('admin.login'))

        if staff.role != 'admin':
            flash('Это действие доступно только администратору.', 'error')
            return redirect(url_for('admin.dashboard'))

        return view_func(*args, **kwargs)

    return wrapped_view


def build_user_map(reservations: list[Reservation]) -> dict[int, User]:
    user_ids = {reservation.user_id for reservation in reservations if reservation.user_id}
    if not user_ids:
        return {}

    users = User.query.filter(User.id.in_(user_ids)).all()
    return {user.id: user for user in users}


def build_assignment_map(reservations: list[Reservation]) -> dict[tuple[date, int], TableAssignment]:
    reservation_dates = {reservation.booking_date for reservation in reservations if reservation.booking_date}
    table_ids = {
        link.table_id
        for reservation in reservations
        for link in reservation.reservation_tables
        if link.table_id
    }

    if not reservation_dates or not table_ids:
        return {}

    assignments = (
        TableAssignment.query
        .filter(
            TableAssignment.is_active.is_(True),
            TableAssignment.shift_date.in_(reservation_dates),
            TableAssignment.table_id.in_(table_ids)
        )
        .all()
    )

    return {
        (assignment.shift_date, assignment.table_id): assignment
        for assignment in assignments
    }


def serialize_reservation_for_admin(
    reservation: Reservation,
    users_map: dict[int, User],
    assignments_map: dict[tuple[date, int], TableAssignment]
) -> dict:
    user = users_map.get(reservation.user_id)

    table_items = []
    total_seats = 0
    assigned_waiter_names = []
    service_pairs = []

    for link in sorted(
        reservation.reservation_tables,
        key=lambda item: item.table.number if item.table else 0
    ):
        if not link.table:
            continue

        total_seats += link.table.seats or 0

        assignment = assignments_map.get((reservation.booking_date, link.table.id))
        waiter_name = assignment.staff_user.full_name if assignment and assignment.staff_user else None

        if waiter_name and waiter_name not in assigned_waiter_names:
            assigned_waiter_names.append(waiter_name)

        service_pairs.append(f'№{link.table.number} — {waiter_name or "не назначен"}')

        table_items.append({
            'id': link.table.id,
            'number': link.table.number,
            'seats': link.table.seats,
            'waiter_name': waiter_name or 'Не назначен'
        })

    return {
        'id': reservation.id,
        'guest_name': getattr(user, 'name', 'Гость') if user else 'Гость',
        'guest_phone': getattr(user, 'phone', '—') if user else '—',
        'booking_date': reservation.booking_date,
        'time_start': reservation.time_start.strftime('%H:%M') if reservation.time_start else '—',
        'time_end': reservation.time_end.strftime('%H:%M') if reservation.time_end else '—',
        'status': reservation.status,
        'comment': reservation.comment or '',
        'tables': table_items,
        'table_numbers': ', '.join(f'№{item["number"]}' for item in table_items) if table_items else '—',
        'tables_count': len(table_items),
        'total_seats': total_seats,
        'assigned_waiters': ', '.join(assigned_waiter_names) if assigned_waiter_names else 'Не назначен',
        'service_map': '; '.join(service_pairs) if service_pairs else 'Не назначен',
        'created_at': reservation.created_at.strftime('%d.%m.%Y %H:%M') if reservation.created_at else '—'
    }


def serialize_occupancy_for_admin(occupancy: TableOccupancy) -> dict:
    table_number = occupancy.table.number if occupancy.table else '—'
    opened_by = occupancy.opened_by_staff.full_name if occupancy.opened_by_staff else '—'

    return {
        'id': occupancy.id,
        'table_id': occupancy.table_id,
        'table_number': table_number,
        'booking_date': occupancy.booking_date,
        'time_start': occupancy.time_start.strftime('%H:%M') if occupancy.time_start else '—',
        'time_end': occupancy.time_end.strftime('%H:%M') if occupancy.time_end else '—',
        'comment': occupancy.comment or '',
        'source': occupancy.source,
        'status': occupancy.status,
        'opened_by_name': opened_by,
        'created_at': occupancy.created_at.strftime('%d.%m.%Y %H:%M') if occupancy.created_at else '—'
    }


def serialize_assignment_for_admin(assignment: TableAssignment) -> dict:
    return {
        'id': assignment.id,
        'shift_date': assignment.shift_date,
        'table_id': assignment.table_id,
        'table_number': assignment.table.number if assignment.table else '—',
        'staff_user_id': assignment.staff_user_id,
        'staff_name': assignment.staff_user.full_name if assignment.staff_user else '—',
        'staff_login': assignment.staff_user.login if assignment.staff_user else '—',
        'created_at': assignment.created_at.strftime('%d.%m.%Y %H:%M') if assignment.created_at else '—'
    }


def parse_iso_date(raw_value: str | None):
    if not raw_value:
        return None
    try:
        return datetime.strptime(raw_value, '%Y-%m-%d').date()
    except ValueError:
        return None


def parse_hhmm_time(raw_value: str | None):
    if not raw_value:
        return None
    try:
        return datetime.strptime(raw_value, '%H:%M').time()
    except ValueError:
        return None


def validate_manual_occupancy(booking_date, time_start, time_end):
    today = date.today()

    if not booking_date:
        return 'Укажите корректную дату.'

    if booking_date < today:
        return 'Нельзя вручную закрывать стол на прошедшую дату.'

    if not time_start or not time_end:
        return 'Укажите корректное время начала и окончания.'

    if time_start >= time_end:
        return 'Время окончания должно быть позже времени начала.'

    if time_start < RESTAURANT_OPEN_TIME:
        return f'Ресторан открывается в {RESTAURANT_OPEN_TIME.strftime("%H:%M")}.'

    if time_end > RESTAURANT_CLOSE_TIME:
        return f'Ресторан работает до {RESTAURANT_CLOSE_TIME.strftime("%H:%M")}.'

    return None


def table_has_reservation_conflict(table_id: int, booking_date, time_start, time_end) -> bool:
    conflict = (
        db.session.query(ReservationTable.id)
        .join(Reservation, ReservationTable.reservation_id == Reservation.id)
        .filter(
            ReservationTable.table_id == table_id,
            Reservation.status == 'active',
            Reservation.booking_date == booking_date,
            Reservation.time_start < time_end,
            Reservation.time_end > time_start
        )
        .first()
    )

    return conflict is not None


def table_has_occupancy_conflict(table_id: int, booking_date, time_start, time_end) -> bool:
    conflict = (
        TableOccupancy.query
        .filter(
            TableOccupancy.table_id == table_id,
            TableOccupancy.status == 'active',
            TableOccupancy.booking_date == booking_date,
            TableOccupancy.time_start < time_end,
            TableOccupancy.time_end > time_start
        )
        .first()
    )

    return conflict is not None


@admin_bp.route('/login', methods=['GET', 'POST'])
def login():
    current_staff = get_current_staff()
    if current_staff:
        return redirect(url_for('admin.dashboard'))

    if request.method == 'POST':
        login_value = (request.form.get('login') or '').strip()
        password_value = request.form.get('password') or ''

        if not login_value or not password_value:
            flash('Введите логин и пароль.', 'error')
            return render_template('admin/login.html')

        staff = StaffUser.query.filter_by(login=login_value).first()

        if not staff or not staff.is_active or not staff.check_password(password_value):
            flash('Неверный логин или пароль.', 'error')
            return render_template('admin/login.html')

        session['admin_staff_id'] = staff.id
        session['admin_staff_login'] = staff.login
        session['admin_staff_name'] = staff.full_name
        session['admin_staff_role'] = staff.role

        flash('Вход в админ-панель выполнен.', 'success')
        return redirect(url_for('admin.dashboard'))

    return render_template('admin/login.html')


@admin_bp.route('', strict_slashes=False)
@login_required
def dashboard():
    staff = get_current_staff()
    today = date.today()

    active_reservations = (
        Reservation.query
        .filter(
            Reservation.status == 'active',
            Reservation.booking_date >= today
        )
        .order_by(
            Reservation.booking_date.asc(),
            Reservation.time_start.asc(),
            Reservation.created_at.asc()
        )
        .all()
    )

    users_map = build_user_map(active_reservations)
    assignments_map = build_assignment_map(active_reservations)

    serialized_reservations = [
        serialize_reservation_for_admin(reservation, users_map, assignments_map)
        for reservation in active_reservations
    ]

    today_reservations = [
        item for item in serialized_reservations
        if item['booking_date'] == today
    ]

    upcoming_reservations = [
        item for item in serialized_reservations
        if item['booking_date'] > today
    ]

    active_occupancies = (
        TableOccupancy.query
        .filter(
            TableOccupancy.status == 'active',
            TableOccupancy.booking_date >= today
        )
        .order_by(
            TableOccupancy.booking_date.asc(),
            TableOccupancy.time_start.asc(),
            TableOccupancy.created_at.asc()
        )
        .all()
    )

    serialized_occupancies = [serialize_occupancy_for_admin(item) for item in active_occupancies]

    active_assignments = (
        TableAssignment.query
        .filter(
            TableAssignment.is_active.is_(True),
            TableAssignment.shift_date >= today
        )
        .order_by(
            TableAssignment.shift_date.asc(),
            Table.number.asc()
        )
        .join(Table, TableAssignment.table_id == Table.id)
        .all()
    )

    serialized_assignments = [serialize_assignment_for_admin(item) for item in active_assignments]

    tables = (
        Table.query
        .filter(Table.is_active.is_(True))
        .order_by(Table.number.asc())
        .all()
    )

    waiters = (
        StaffUser.query
        .filter(
            StaffUser.is_active.is_(True),
            StaffUser.role == 'waiter'
        )
        .order_by(StaffUser.full_name.asc())
        .all()
    )

    stats = {
        'today_count': len(today_reservations),
        'upcoming_count': len(upcoming_reservations),
        'all_active_count': len(serialized_reservations),
        'today_tables_count': sum(item['tables_count'] for item in today_reservations),
        'manual_occupancies_count': len(serialized_occupancies),
        'assignments_count': len(serialized_assignments),
    }

    return render_template(
        'admin/dashboard.html',
        staff=staff,
        today=today,
        today_reservations=today_reservations,
        upcoming_reservations=upcoming_reservations,
        active_occupancies=serialized_occupancies,
        active_assignments=serialized_assignments,
        tables=tables,
        waiters=waiters,
        stats=stats
    )


@admin_bp.route('/reservations/<int:reservation_id>/cancel', methods=['POST'])
@login_required
def cancel_reservation(reservation_id: int):
    reservation = Reservation.query.filter_by(id=reservation_id).first()

    if not reservation:
        flash('Бронь не найдена.', 'error')
        return redirect(url_for('admin.dashboard'))

    if reservation.status != 'active':
        flash('Эта бронь уже не является активной.', 'info')
        return redirect(url_for('admin.dashboard'))

    reservation.status = 'cancelled'
    db.session.commit()

    flash(f'Бронь №{reservation.id} отменена.', 'success')
    return redirect(url_for('admin.dashboard'))


@admin_bp.route('/reservations/<int:reservation_id>/complete', methods=['POST'])
@login_required
def complete_reservation(reservation_id: int):
    reservation = Reservation.query.filter_by(id=reservation_id).first()

    if not reservation:
        flash('Бронь не найдена.', 'error')
        return redirect(url_for('admin.dashboard'))

    if reservation.status != 'active':
        flash('Эта бронь уже не является активной.', 'info')
        return redirect(url_for('admin.dashboard'))

    reservation.status = 'completed'
    db.session.commit()

    flash(f'Бронь №{reservation.id} завершена.', 'success')
    return redirect(url_for('admin.dashboard'))


@admin_bp.route('/occupancies/open', methods=['POST'])
@login_required
def open_occupancy():
    staff = get_current_staff()

    raw_table_id = request.form.get('table_id')
    raw_booking_date = request.form.get('booking_date')
    raw_time_start = request.form.get('time_start')
    raw_time_end = request.form.get('time_end')
    comment = (request.form.get('comment') or '').strip()

    try:
        table_id = int(raw_table_id)
    except (TypeError, ValueError):
        flash('Выберите корректный стол.', 'error')
        return redirect(url_for('admin.dashboard'))

    table = Table.query.filter_by(id=table_id, is_active=True).first()
    if not table:
        flash('Стол не найден.', 'error')
        return redirect(url_for('admin.dashboard'))

    booking_date = parse_iso_date(raw_booking_date)
    time_start = parse_hhmm_time(raw_time_start)
    time_end = parse_hhmm_time(raw_time_end)

    validation_error = validate_manual_occupancy(booking_date, time_start, time_end)
    if validation_error:
        flash(validation_error, 'error')
        return redirect(url_for('admin.dashboard'))

    if table_has_reservation_conflict(table.id, booking_date, time_start, time_end):
        flash('На этот интервал уже существует активная бронь для выбранного стола.', 'error')
        return redirect(url_for('admin.dashboard'))

    if table_has_occupancy_conflict(table.id, booking_date, time_start, time_end):
        flash('Этот стол уже закрыт вручную на пересекающийся интервал.', 'error')
        return redirect(url_for('admin.dashboard'))

    occupancy = TableOccupancy(
        table_id=table.id,
        opened_by_staff_id=staff.id if staff else None,
        source='manual_block',
        status='active',
        booking_date=booking_date,
        time_start=time_start,
        time_end=time_end,
        comment=comment or None
    )
    db.session.add(occupancy)
    db.session.commit()

    flash(
        f'Стол №{table.number} вручную закрыт на {booking_date.strftime("%d.%m.%Y")} '
        f'с {time_start.strftime("%H:%M")} до {time_end.strftime("%H:%M")}.',
        'success'
    )
    return redirect(url_for('admin.dashboard'))


@admin_bp.route('/occupancies/<int:occupancy_id>/close', methods=['POST'])
@login_required
def close_occupancy(occupancy_id: int):
    staff = get_current_staff()

    occupancy = TableOccupancy.query.filter_by(id=occupancy_id).first()
    if not occupancy:
        flash('Ручная занятость не найдена.', 'error')
        return redirect(url_for('admin.dashboard'))

    if occupancy.status != 'active':
        flash('Эта запись уже закрыта.', 'info')
        return redirect(url_for('admin.dashboard'))

    occupancy.status = 'closed'
    occupancy.closed_at = datetime.utcnow()
    occupancy.closed_by_staff_id = staff.id if staff else None

    db.session.commit()

    table_number = occupancy.table.number if occupancy.table else occupancy.table_id
    flash(f'Ручная занятость стола №{table_number} снята.', 'success')
    return redirect(url_for('admin.dashboard'))


@admin_bp.route('/assignments/create', methods=['POST'])
@admin_required
def create_assignment():
    raw_table_id = request.form.get('table_id')
    raw_staff_user_id = request.form.get('staff_user_id')
    raw_shift_date = request.form.get('shift_date')

    try:
        table_id = int(raw_table_id)
        staff_user_id = int(raw_staff_user_id)
    except (TypeError, ValueError):
        flash('Выберите корректные значения для стола и официанта.', 'error')
        return redirect(url_for('admin.dashboard'))

    shift_date = parse_iso_date(raw_shift_date)
    if not shift_date:
        flash('Укажите корректную дату назначения.', 'error')
        return redirect(url_for('admin.dashboard'))

    if shift_date < date.today():
        flash('Нельзя назначать официанта на прошедшую дату.', 'error')
        return redirect(url_for('admin.dashboard'))

    table = Table.query.filter_by(id=table_id, is_active=True).first()
    if not table:
        flash('Стол не найден.', 'error')
        return redirect(url_for('admin.dashboard'))

    waiter = StaffUser.query.filter_by(id=staff_user_id, is_active=True, role='waiter').first()
    if not waiter:
        flash('Официант не найден.', 'error')
        return redirect(url_for('admin.dashboard'))

    existing_assignment = (
        TableAssignment.query
        .filter(
            TableAssignment.table_id == table.id,
            TableAssignment.shift_date == shift_date,
            TableAssignment.is_active.is_(True)
        )
        .first()
    )

    if existing_assignment:
        if existing_assignment.staff_user_id == waiter.id:
            flash(
                f'Официант {waiter.full_name} уже назначен на стол №{table.number} '
                f'на {shift_date.strftime("%d.%m.%Y")}.',
                'info'
            )
            return redirect(url_for('admin.dashboard'))

        existing_assignment.staff_user_id = waiter.id
        db.session.commit()

        flash(
            f'Назначение обновлено: стол №{table.number} на {shift_date.strftime("%d.%m.%Y")} '
            f'теперь обслуживает {waiter.full_name}.',
            'success'
        )
        return redirect(url_for('admin.dashboard'))

    assignment = TableAssignment(
        table_id=table.id,
        staff_user_id=waiter.id,
        shift_date=shift_date,
        is_active=True
    )
    db.session.add(assignment)
    db.session.commit()

    flash(
        f'Официант {waiter.full_name} назначен на стол №{table.number} '
        f'на {shift_date.strftime("%d.%m.%Y")}.',
        'success'
    )
    return redirect(url_for('admin.dashboard'))


@admin_bp.route('/assignments/<int:assignment_id>/delete', methods=['POST'])
@admin_required
def delete_assignment(assignment_id: int):
    assignment = TableAssignment.query.filter_by(id=assignment_id).first()

    if not assignment:
        flash('Назначение не найдено.', 'error')
        return redirect(url_for('admin.dashboard'))

    if not assignment.is_active:
        flash('Это назначение уже снято.', 'info')
        return redirect(url_for('admin.dashboard'))

    assignment.is_active = False
    db.session.commit()

    table_number = assignment.table.number if assignment.table else assignment.table_id
    waiter_name = assignment.staff_user.full_name if assignment.staff_user else 'официант'

    flash(
        f'Назначение снято: {waiter_name} больше не закреплён за столом №{table_number}.',
        'success'
    )
    return redirect(url_for('admin.dashboard'))


@admin_bp.route('/logout')
def logout():
    session.pop('admin_staff_id', None)
    session.pop('admin_staff_login', None)
    session.pop('admin_staff_name', None)
    session.pop('admin_staff_role', None)

    flash('Вы вышли из админ-панели.', 'info')
    return redirect(url_for('admin.login'))