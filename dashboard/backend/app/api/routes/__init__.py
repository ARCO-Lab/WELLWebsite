# This file registers all API routes for the WELL backend Flask application.
# It wires up each route handler.

from .data import register_data_route
from .latest import register_latest_route
# AI ANALYSIS DISABLED: the OpenAI-backed /api/analysis/* routes (routes/analysis/) are switched off and not imported.
# To restore the feature, uncomment every block marked "AI ANALYSIS DISABLED" (here and in dashboard/frontend), add
# openai back to requirements.txt and set OPENAI_API_KEY. Uncommenting is not enough on its own: the analysis routes
# read summaries (latest_summaries, latest_sampling_summaries) that data.py and samples.py no longer fill. Rebuild
# that summary step too; the old code is in the commit before 5b501eb, e.g.
# `git show 5b501eb^:dashboard/backend/app/api/routes/data.py` (and samples.py).
# from .analysis.alltime import register_analysis_alltime_route
# from .analysis.recent import register_analysis_recent_route
# from .analysis.wind import register_analysis_wind_route
# from .analysis.complete import register_analysis_complete_route
from .samples import register_samples_route
from .series import register_series_route
from .recent import register_recent_route
from .exports import register_export_routes

def register_routes(app):
    register_data_route(app)
    register_latest_route(app)
    register_samples_route(app)
    register_series_route(app)
    register_recent_route(app)
    register_export_routes(app)
    # AI ANALYSIS DISABLED: the shared state and OpenAI client the analysis routes take, and their registration.
    # Something has to fill latest_summaries and latest_sampling_summaries first (see the note at the top).
    # latest_summaries = {"data": {}}
    # latest_sampling_summaries = {"data": {}}
    # latest_metrics_cache = {"data": {}}
    # from openai import OpenAI
    # client = OpenAI()
    # register_analysis_alltime_route(app, latest_summaries, client)
    # register_analysis_recent_route(app, latest_metrics_cache, client)
    # register_analysis_wind_route(app, latest_summaries, client)
    # register_analysis_complete_route(app, latest_summaries, latest_sampling_summaries, client)
