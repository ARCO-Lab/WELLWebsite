# This file registers all API routes for the WELL backend Flask application.
# It wires up each route handler.

from .data import register_data_route
from .latest import register_latest_route
from .samples import register_samples_route
from .series import register_series_route
from .windrose import register_windrose_route
from .recent import register_recent_route
from .exports import register_export_routes

def register_routes(app):
    register_data_route(app)
    register_latest_route(app)
    register_samples_route(app)
    register_series_route(app)
    register_windrose_route(app)
    register_recent_route(app)
    register_export_routes(app)