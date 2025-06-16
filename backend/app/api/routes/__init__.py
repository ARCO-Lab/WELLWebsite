from .data import register_data_route
from .latest import register_latest_route
from .analysis.alltime import register_analysis_alltime_route
from .analysis.recent import register_analysis_recent_route
from .analysis.wind import register_analysis_wind_route

def register_routes(app):
    # Shared/global state
    latest_summaries = {"data": {}}
    latest_metrics_cache = {"data": {}}
    from openai import OpenAI
    client = OpenAI()

    # Register each route, passing shared state as needed
    register_data_route(app, latest_summaries)
    register_latest_route(app, latest_metrics_cache)
    register_analysis_alltime_route(app, latest_summaries, client)
    register_analysis_recent_route(app, latest_metrics_cache, client)
    register_analysis_wind_route(app, latest_summaries, client)