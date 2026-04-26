import re

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from extensions import db
from models.users import User

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


def normalize_phone(phone_raw: str) -> str | None:
    digits = re.sub(r'\D', '', phone_raw or '')

    if len(digits) == 10:
        digits = '7' + digits
    elif len(digits) == 11 and digits.startswith('8'):
        digits = '7' + digits[1:]

    if len(digits) != 11 or not digits.startswith('7'):
        return None

    return f'+{digits}'


def clear_pending_auth():
    session.pop('pending_name', None)
    session.pop('pending_phone', None)


def login_user(user: User):
    session['user_id'] = user.id
    session['user_name'] = user.name
    session['user_phone'] = user.phone


def logout_user():
    session.pop('user_id', None)
    session.pop('user_name', None)
    session.pop('user_phone', None)
    clear_pending_auth()


@auth_bp.get('/login')
def login():
    return render_template('login.html')


@auth_bp.post('/request-code')
def request_code():
    if session.get('user_id'):
        flash('Вы уже вошли в аккаунт.', 'info')
        return redirect(url_for('auth.login'))

    name = (request.form.get('name') or '').strip()
    phone_raw = (request.form.get('phone') or '').strip()
    phone = normalize_phone(phone_raw)

    if not name:
        flash('Введите имя.', 'error')
        return redirect(url_for('auth.login'))

    if not phone:
        flash('Введите корректный номер телефона.', 'error')
        return redirect(url_for('auth.login'))

    session['pending_name'] = name
    session['pending_phone'] = phone

    flash('Код отправлен. Для текущего этапа используйте код 1234.', 'success')
    return redirect(url_for('auth.login'))


@auth_bp.post('/verify-code')
def verify_code():
    if session.get('user_id'):
        flash('Вы уже вошли в аккаунт.', 'info')
        return redirect(url_for('auth.login'))

    pending_name = session.get('pending_name')
    pending_phone = session.get('pending_phone')
    code = (request.form.get('code') or '').strip()

    if not pending_name or not pending_phone:
        flash('Сначала запросите код подтверждения.', 'error')
        return redirect(url_for('auth.login'))

    if code != '1234':
        flash('Неверный код. Для текущего этапа используйте 1234.', 'error')
        return redirect(url_for('auth.login'))

    user = User.query.filter_by(phone=pending_phone).first()

    if user:
        user.name = pending_name
    else:
        user = User(
            name=pending_name,
            phone=pending_phone,
            is_active=True
        )
        db.session.add(user)

    db.session.commit()

    login_user(user)
    clear_pending_auth()

    flash('Вход выполнен успешно.', 'success')
    return redirect(url_for('main.index'))


@auth_bp.get('/reset-login')
def reset_login():
    clear_pending_auth()
    flash('Ввод кода сброшен. Можно ввести данные заново.', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.get('/logout')
def logout():
    logout_user()
    flash('Вы вышли из аккаунта.', 'success')
    return redirect(url_for('main.index'))