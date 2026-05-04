import calendar
from datetime import date, datetime, time, timedelta

from flask import Blueprint, flash, jsonify, redirect, render_template, request, session, url_for

from extensions import db
from models.tables import Table
from models.users import User
from models.reservations import Reservation, ReservationTable
from models.table_occupancies import TableOccupancy


booking_bp = Blueprint('booking', __name__, url_prefix='/booking')

RESTAURANT_OPEN_TIME = time(10, 0)
RESTAURANT_CLOSE_TIME = time(22, 0)

DEFAULT_DURATION_MINUTES = 120
MIN_DURATION_MINUTES = 60
MAX_DURATION_MINUTES = 720

MAX_TABLES_PER_RESERVATION = 2


def add_one_month(source_date: date) -> date:
    if source_date.month == 12:
        target_year = source_date.year + 1
        target_month = 1
    else:
        target_year = source_date.year
        target_month = source_date.month + 1

    last_day = calendar.monthrange(target_year, target_month)[1]
    target_day = min(source_date.day, last_day)

    return date(target_year, target_month, target_day)


def parse_iso_date(raw_value: str | None) -> date | None:
    if not raw_value:
        return None

    try:
        return datetime.strptime(raw_value, '%Y-%m-%d').date()
    except ValueError:
        return None


def parse_hhmm_time(raw_value: str | None) -> time | None:
    if not raw_value:
        return None

    try:
        return datetime.strptime(raw_value, '%H:%M').time()
    except ValueError:
        return None


def format_time_value(value: time | None) -> str | None:
    return value.strftime('%H:%M') if value else None


def validate_duration(raw_value: str | None) -> tuple[int | None, str | None]:
    if raw_value is None or raw_value == '':
        return DEFAULT_DURATION_MINUTES, None

    try:
        duration_minutes = int(raw_value)
    except (TypeError, ValueError):
        return None, 'Длительность бронирования должна быть числом.'

    if duration_minutes < MIN_DURATION_MINUTES or duration_minutes > MAX_DURATION_MINUTES:
        return None, (
            f'Длительность бронирования должна быть в диапазоне '
            f'от {MIN_DURATION_MINUTES} до {MAX_DURATION_MINUTES} минут.'
        )

    if duration_minutes % 60 != 0:
        return None, 'Длительность бронирования должна быть только в целых часах.'

    return duration_minutes, None


def calculate_time_end(booking_date: date, time_start: time, duration_minutes: int) -> time:
    start_dt = datetime.combine(booking_date, time_start)
    end_dt = start_dt + timedelta(minutes=duration_minutes)
    return end_dt.time()


def validate_booking_window(
    booking_date: date,
    time_start: time,
    duration_minutes: int
) -> tuple[time | None, str | None]:
    today = date.today()
    max_booking_date = add_one_month(today)

    if booking_date < today:
        return None, 'Нельзя бронировать столы на прошедшую дату.'

    if booking_date > max_booking_date:
        return None, (
            f'Бронирование доступно только на месяц вперёд. '
            f'Максимальная дата: {max_booking_date.isoformat()}.'
        )

    if time_start < RESTAURANT_OPEN_TIME:
        return None, f'Ресторан открывается в {format_time_value(RESTAURANT_OPEN_TIME)}.'

    time_end = calculate_time_end(booking_date, time_start, duration_minutes)

    if time_end > RESTAURANT_CLOSE_TIME:
        return None, (
            f'Выбранный интервал выходит за пределы режима работы ресторана '
            f'до {format_time_value(RESTAURANT_CLOSE_TIME)}.'
        )

    return time_end, None


def get_current_user() -> User | None:
    user_id = session.get('user_id')
    if not user_id:
        return None

    return User.query.filter_by(id=user_id, is_active=True).first()


def get_occupied_table_ids(
    booking_date: date,
    time_start: time,
    time_end: time,
    exclude_reservation_id: int | None = None
) -> list[int]:
    reservation_query = (
        db.session.query(ReservationTable.table_id)
        .join(Reservation, ReservationTable.reservation_id == Reservation.id)
        .filter(
            Reservation.status == 'active',
            Reservation.booking_date == booking_date,
            Reservation.time_start < time_end,
            Reservation.time_end > time_start
        )
    )

    if exclude_reservation_id is not None:
        reservation_query = reservation_query.filter(Reservation.id != exclude_reservation_id)

    reservation_rows = reservation_query.all()
    reservation_table_ids = {row[0] for row in reservation_rows}

    occupancy_rows = (
        db.session.query(TableOccupancy.table_id)
        .filter(
            TableOccupancy.status == 'active',
            TableOccupancy.booking_date == booking_date,
            TableOccupancy.time_start < time_end,
            TableOccupancy.time_end > time_start
        )
        .all()
    )
    occupancy_table_ids = {row[0] for row in occupancy_rows}

    return sorted(reservation_table_ids | occupancy_table_ids)


def serialize_table(table: Table, occupied_table_ids: list[int]) -> dict:
    return {
        'id': table.id,
        'number': table.number,
        'seats': table.seats,
        'description': table.description,
        'image': table.image,
        'image_panorama': table.image_panorama,
        'is_available': table.id not in occupied_table_ids
    }


def normalize_table_ids(raw_table_ids) -> tuple[list[int] | None, str | None]:
    if not isinstance(raw_table_ids, list):
        return None, 'Передайте table_ids в виде массива.'

    normalized_ids = []
    for raw_id in raw_table_ids:
        try:
            table_id = int(raw_id)
        except (TypeError, ValueError):
            return None, 'Все идентификаторы столов должны быть числами.'

        if table_id not in normalized_ids:
            normalized_ids.append(table_id)

    if not normalized_ids:
        return None, 'Выберите хотя бы один стол.'

    if len(normalized_ids) > MAX_TABLES_PER_RESERVATION:
        return None, 'Бронирование более двух столов доступно только по телефону ресторана.'

    return normalized_ids, None


def serialize_reservation_for_api(reservation: Reservation) -> dict:
    table_items = []
    for link in reservation.reservation_tables:
        if link.table:
            table_items.append({
                'id': link.table.id,
                'number': link.table.number,
                'seats': link.table.seats
            })

    return {
        'id': reservation.id,
        'user_id': reservation.user_id,
        'booking_date': reservation.booking_date.isoformat() if reservation.booking_date else None,
        'time_start': format_time_value(reservation.time_start),
        'time_end': format_time_value(reservation.time_end),
        'status': reservation.status,
        'comment': reservation.comment,
        'tables': table_items,
        'created_at': reservation.created_at.isoformat() if reservation.created_at else None
    }


@booking_bp.get('/available-tables')
def get_available_tables():
    raw_date = request.args.get('date')
    raw_time_start = request.args.get('time_start')
    raw_duration = request.args.get('duration_minutes')

    booking_date = parse_iso_date(raw_date)
    if not booking_date:
        return jsonify({'error': 'Передайте корректную дату в формате YYYY-MM-DD.'}), 400

    time_start = parse_hhmm_time(raw_time_start)
    if not time_start:
        return jsonify({'error': 'Передайте корректное время начала в формате HH:MM.'}), 400

    duration_minutes, duration_error = validate_duration(raw_duration)
    if duration_error:
        return jsonify({'error': duration_error}), 400

    time_end, booking_window_error = validate_booking_window(
        booking_date=booking_date,
        time_start=time_start,
        duration_minutes=duration_minutes
    )
    if booking_window_error:
        return jsonify({'error': booking_window_error}), 400

    occupied_table_ids = get_occupied_table_ids(
        booking_date=booking_date,
        time_start=time_start,
        time_end=time_end
    )

    tables = (
        Table.query
        .filter(Table.is_active.is_(True))
        .order_by(Table.number.asc())
        .all()
    )

    available_table_ids = []
    serialized_tables = []

    for table in tables:
        is_available = table.id not in occupied_table_ids

        if is_available:
            available_table_ids.append(table.id)

        serialized_tables.append(serialize_table(table, occupied_table_ids))

    return jsonify({
        'booking_date': booking_date.isoformat(),
        'time_start': format_time_value(time_start),
        'time_end': format_time_value(time_end),
        'duration_minutes': duration_minutes,
        'max_tables_per_reservation': MAX_TABLES_PER_RESERVATION,
        'available_table_ids': available_table_ids,
        'occupied_table_ids': occupied_table_ids,
        'tables': serialized_tables
    })


@booking_bp.post('/create')
def create_booking():
    user = get_current_user()
    if not user:
        return jsonify({
            'error': 'Для бронирования необходимо войти в аккаунт.'
        }), 401

    payload = request.get_json(silent=True) or {}

    raw_date = payload.get('date')
    raw_time_start = payload.get('time_start')
    raw_duration = payload.get('duration_minutes')
    raw_table_ids = payload.get('table_ids')
    comment = (payload.get('comment') or '').strip()

    booking_date = parse_iso_date(raw_date)
    if not booking_date:
        return jsonify({'error': 'Передайте корректную дату в формате YYYY-MM-DD.'}), 400

    time_start = parse_hhmm_time(raw_time_start)
    if not time_start:
        return jsonify({'error': 'Передайте корректное время начала в формате HH:MM.'}), 400

    duration_minutes, duration_error = validate_duration(raw_duration)
    if duration_error:
        return jsonify({'error': duration_error}), 400

    table_ids, table_ids_error = normalize_table_ids(raw_table_ids)
    if table_ids_error:
        return jsonify({'error': table_ids_error}), 400

    time_end, booking_window_error = validate_booking_window(
        booking_date=booking_date,
        time_start=time_start,
        duration_minutes=duration_minutes
    )
    if booking_window_error:
        return jsonify({'error': booking_window_error}), 400

    selected_tables = (
        Table.query
        .filter(
            Table.id.in_(table_ids),
            Table.is_active.is_(True)
        )
        .order_by(Table.number.asc())
        .all()
    )

    if len(selected_tables) != len(table_ids):
        return jsonify({
            'error': 'Один или несколько выбранных столов недоступны.'
        }), 400

    occupied_table_ids = get_occupied_table_ids(
        booking_date=booking_date,
        time_start=time_start,
        time_end=time_end
    )

    conflicting_table_ids = [table_id for table_id in table_ids if table_id in occupied_table_ids]
    if conflicting_table_ids:
        return jsonify({
            'error': 'Один или несколько выбранных столов уже заняты на это время.',
            'occupied_table_ids': conflicting_table_ids
        }), 409

    reservation = Reservation(
        user_id=user.id,
        booking_date=booking_date,
        time_start=time_start,
        time_end=time_end,
        status='active',
        comment=comment or None
    )
    db.session.add(reservation)
    db.session.flush()

    for table_id in table_ids:
        db.session.add(
            ReservationTable(
                reservation_id=reservation.id,
                table_id=table_id
            )
        )

    db.session.commit()

    return jsonify({
        'message': 'Бронирование успешно создано.',
        'reservation': reservation.to_dict(),
        'user': user.to_dict(),
        'selected_tables': [
            {
                'id': table.id,
                'number': table.number,
                'seats': table.seats
            }
            for table in selected_tables
        ]
    }), 201


@booking_bp.get('/account')
def account():
    user = get_current_user()
    if not user:
        flash('Для доступа к личному кабинету необходимо войти в аккаунт.', 'error')
        return redirect(url_for('auth.login'))

    reservations = (
        Reservation.query
        .filter_by(user_id=user.id)
        .order_by(
            Reservation.booking_date.desc(),
            Reservation.time_start.desc(),
            Reservation.created_at.desc()
        )
        .all()
    )

    active_reservations = [reservation for reservation in reservations if reservation.status == 'active']
    archived_reservations = [reservation for reservation in reservations if reservation.status != 'active']

    return render_template(
        'account.html',
        user=user,
        active_reservations=active_reservations,
        archived_reservations=archived_reservations
    )


@booking_bp.get('/my-reservations')
def my_reservations():
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Необходим вход в аккаунт.'}), 401

    reservations = (
        Reservation.query
        .filter_by(user_id=user.id)
        .order_by(
            Reservation.booking_date.desc(),
            Reservation.time_start.desc(),
            Reservation.created_at.desc()
        )
        .all()
    )

    return jsonify({
        'user': user.to_dict(),
        'reservations': [serialize_reservation_for_api(reservation) for reservation in reservations]
    })


@booking_bp.post('/cancel/<int:reservation_id>')
def cancel_booking(reservation_id: int):
    user = get_current_user()
    if not user:
        if request.is_json:
            return jsonify({'error': 'Необходим вход в аккаунт.'}), 401

        flash('Для отмены бронирования необходимо войти в аккаунт.', 'error')
        return redirect(url_for('auth.login'))

    reservation = Reservation.query.filter_by(
        id=reservation_id,
        user_id=user.id
    ).first()

    if not reservation:
        if request.is_json:
            return jsonify({'error': 'Бронирование не найдено.'}), 404

        flash('Бронирование не найдено.', 'error')
        return redirect(url_for('booking.account'))

    if reservation.status == 'cancelled':
        if request.is_json:
            return jsonify({
                'message': 'Бронирование уже было отменено.',
                'reservation': serialize_reservation_for_api(reservation)
            }), 200

        flash('Это бронирование уже отменено.', 'info')
        return redirect(url_for('booking.account'))

    reservation.status = 'cancelled'
    db.session.commit()

    if request.is_json:
        return jsonify({
            'message': 'Бронирование успешно отменено.',
            'reservation': serialize_reservation_for_api(reservation)
        }), 200

    flash('Бронирование успешно отменено.', 'success')
    return redirect(url_for('booking.account'))