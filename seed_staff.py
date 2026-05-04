from app import app
from extensions import db
from models.staff_users import StaffUser


STAFF_TO_CREATE = [
    {
        "login": "admin",
        "password": "admin123",
        "full_name": "Главный администратор",
        "role": "admin",
    },
    {
        "login": "waiter1",
        "password": "waiter123",
        "full_name": "Официант 1",
        "role": "waiter",
    },
    {
        "login": "waiter2",
        "password": "waiter123",
        "full_name": "Официант 2",
        "role": "waiter",
    },
]


def create_or_update_staff():
    with app.app_context():
        created_count = 0
        updated_count = 0

        for item in STAFF_TO_CREATE:
            staff = StaffUser.query.filter_by(login=item["login"]).first()

            if staff is None:
                staff = StaffUser(
                    login=item["login"],
                    full_name=item["full_name"],
                    role=item["role"],
                    is_active=True,
                )
                staff.set_password(item["password"])
                db.session.add(staff)
                created_count += 1
                print(f"[CREATED] {item['login']} ({item['role']})")
            else:
                staff.full_name = item["full_name"]
                staff.role = item["role"]
                staff.is_active = True
                staff.set_password(item["password"])
                updated_count += 1
                print(f"[UPDATED] {item['login']} ({item['role']})")

        db.session.commit()

        print()
        print(f"Создано: {created_count}")
        print(f"Обновлено: {updated_count}")
        print("Готово.")


if __name__ == "__main__":
    create_or_update_staff()