from flask import Blueprint, render_template, request, jsonify
from .services.price_service import search_products

main = Blueprint('main', __name__)


@main.route('/')
def home():
    return render_template('index.html')


@main.route('/api/search')
def api_search():
    query = request.args.get('q', '').strip()

    if not query:
        return jsonify({
            'error': 'Please provide a search query, e.g. /api/search?q=iphone 15'
        }), 400

    try:
        result = search_products(query)
    except RuntimeError as e:
        return jsonify({'error': str(e)}), 500

    return jsonify({
        'query': query,
        **result
    })