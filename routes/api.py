from flask import Blueprint, jsonify
from models.tables import Table

api_bp = Blueprint('api', __name__, url_prefix='/api')


@api_bp.route('/table/<int:table_id>')
def get_table(table_id):
    table = Table.query.get(table_id)
    if not table:
        return jsonify({'error': 'Table not found'}), 404

    return jsonify({
        'id': table.id,
        'number': table.number,
        'seats': table.seats,
        'description': table.description,
        'image': table.image,
        'image_panorama': table.image_panorama
    })