"""
Milestone 4 - MLOps Dashboard.

Read-only dashboard for the unified multi-model serving platform.

Displays:
- Model health
- Production versions
- Request volume
- Latency
- A/B testing metrics
- Retraining configuration
"""

from __future__ import annotations

import html
from typing import Any

from fastapi import APIRouter
from fastapi.responses import HTMLResponse


MODEL_NAMES = (
    "forecast",
    "eta",
    "anomaly",
    "risk",
)


def safe(value: Any) -> str:
    """Escape values before rendering them into HTML."""
    return html.escape(str(value))


def create_dashboard_router(
    model_manager: Any,
    orchestrator: Any | None = None,
) -> APIRouter:
    """
    Create the Milestone 4 MLOps dashboard router.
    """

    router = APIRouter(
        prefix="/mlops",
        tags=["MLOps Dashboard"],
    )

    @router.get(
        "/dashboard",
        response_class=HTMLResponse,
    )
    def dashboard() -> HTMLResponse:
        """Render the MLOps dashboard."""

        # --------------------------------------------------
        # Overall health
        # --------------------------------------------------

        try:
            health = model_manager.health()
        except Exception as exc:
            health = {
                "status": "unhealthy",
                "error": str(exc),
                "models": {},
            }

        health_status = health.get(
            "status",
            "unknown",
        )

        # --------------------------------------------------
        # Build model cards
        # --------------------------------------------------

        model_cards = []

        for model_name in MODEL_NAMES:

            # ----------------------------------------------
            # Model information
            # ----------------------------------------------

            try:
                model_info = model_manager.get_model_info(
                    model_name
                )
            except Exception as exc:
                model_info = {
                    "model": model_name,
                    "production_version": "unknown",
                    "status": f"error: {exc}",
                }

            # ----------------------------------------------
            # A/B metrics
            # ----------------------------------------------

            try:
                ab_metrics = model_manager.get_ab_metrics(
                    model_name
                )
            except Exception:
                ab_metrics = {}

            total_requests = 0
            total_successes = 0
            total_failures = 0
            total_latency = 0.0

            for metrics in ab_metrics.values():

                requests = int(
                    metrics.get(
                        "requests",
                        0,
                    )
                )

                successes = int(
                    metrics.get(
                        "successes",
                        0,
                    )
                )

                failures = int(
                    metrics.get(
                        "failures",
                        0,
                    )
                )

                average_latency = float(
                    metrics.get(
                        "average_latency_ms",
                        0.0,
                    )
                )

                total_requests += requests
                total_successes += successes
                total_failures += failures

                total_latency += (
                    average_latency * requests
                )

            # ----------------------------------------------
            # Aggregate metrics
            # ----------------------------------------------

            if total_requests:
                average_latency = (
                    total_latency / total_requests
                )

                success_rate = (
                    total_successes / total_requests
                )
            else:
                average_latency = 0.0
                success_rate = 0.0

            # ----------------------------------------------
            # A/B table
            # ----------------------------------------------

            ab_rows = ""

            if ab_metrics:

                for variant, metrics in ab_metrics.items():

                    ab_rows += f"""
                    <tr>
                        <td>{safe(variant)}</td>

                        <td>
                            {safe(metrics.get("requests", 0))}
                        </td>

                        <td>
                            {safe(metrics.get("successes", 0))}
                        </td>

                        <td>
                            {safe(metrics.get("failures", 0))}
                        </td>

                        <td>
                            {safe(
                                metrics.get(
                                    "success_rate",
                                    0,
                                )
                            )}
                        </td>

                        <td>
                            {safe(
                                metrics.get(
                                    "average_latency_ms",
                                    0,
                                )
                            )}
                        </td>
                    </tr>
                    """

            else:

                ab_rows = """
                <tr>
                    <td colspan="6">
                        No A/B traffic recorded
                    </td>
                </tr>
                """

            # ----------------------------------------------
            # Model card
            # ----------------------------------------------

            model_cards.append(
                f"""
                <section class="model-card">

                    <div class="model-title">

                        <h2>
                            {safe(model_name.title())}
                        </h2>

                        <span class="badge">
                            {safe(
                                model_info.get(
                                    "status",
                                    "unknown",
                                )
                            )}
                        </span>

                    </div>

                    <div class="metrics">

                        <div class="metric">

                            <span>
                                Production Version
                            </span>

                            <strong>
                                {safe(
                                    model_info.get(
                                        "production_version",
                                        "unknown",
                                    )
                                )}
                            </strong>

                        </div>

                        <div class="metric">

                            <span>
                                Requests
                            </span>

                            <strong>
                                {total_requests}
                            </strong>

                        </div>

                        <div class="metric">

                            <span>
                                Success Rate
                            </span>

                            <strong>
                                {success_rate:.2%}
                            </strong>

                        </div>

                        <div class="metric">

                            <span>
                                Avg Latency
                            </span>

                            <strong>
                                {average_latency:.3f} ms
                            </strong>

                        </div>

                    </div>

                    <h3>
                        A/B Metrics
                    </h3>

                    <table>

                        <thead>

                            <tr>
                                <th>Variant</th>
                                <th>Requests</th>
                                <th>Successes</th>
                                <th>Failures</th>
                                <th>Success Rate</th>
                                <th>Latency</th>
                            </tr>

                        </thead>

                        <tbody>
                            {ab_rows}
                        </tbody>

                    </table>

                </section>
                """
            )

        # --------------------------------------------------
        # Retraining status
        # --------------------------------------------------

        if orchestrator is not None:
            retraining_status = "Configured"
        else:
            retraining_status = "Unavailable"

        # --------------------------------------------------
        # Final HTML
        # --------------------------------------------------

        page = f"""
<!DOCTYPE html>

<html lang="en">

<head>

    <meta charset="UTF-8">

    <meta
        name="viewport"
        content="width=device-width, initial-scale=1.0"
    >

    <meta
        http-equiv="refresh"
        content="30"
    >

    <title>MLOps Dashboard</title>

    <style>

        * {{
            box-sizing: border-box;
        }}

        body {{
            margin: 0;
            font-family:
                Arial,
                Helvetica,
                sans-serif;
            background: #f4f6f8;
            color: #1f2937;
        }}

        .container {{
            max-width: 1400px;
            margin: auto;
            padding: 30px;
        }}

        header {{
            margin-bottom: 25px;
        }}

        h1 {{
            margin-bottom: 5px;
        }}

        .subtitle {{
            color: #6b7280;
        }}

        .overview {{
            display: grid;
            grid-template-columns:
                repeat(
                    auto-fit,
                    minmax(200px, 1fr)
                );
            gap: 16px;
            margin-bottom: 25px;
        }}

        .overview-card {{
            background: white;
            padding: 20px;
            border-radius: 12px;
            box-shadow:
                0 2px 8px
                rgba(0, 0, 0, 0.08);
        }}

        .overview-card span {{
            display: block;
            font-size: 13px;
            color: #6b7280;
            margin-bottom: 8px;
        }}

        .overview-card strong {{
            font-size: 24px;
        }}

        .model-card {{
            background: white;
            padding: 24px;
            margin-bottom: 20px;
            border-radius: 12px;
            box-shadow:
                0 2px 8px
                rgba(0, 0, 0, 0.08);
        }}

        .model-title {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
        }}

        .model-title h2 {{
            margin: 0;
        }}

        .badge {{
            padding: 6px 12px;
            border-radius: 20px;
            background: #e5e7eb;
            font-size: 13px;
            font-weight: bold;
        }}

        .metrics {{
            display: grid;
            grid-template-columns:
                repeat(
                    auto-fit,
                    minmax(180px, 1fr)
                );
            gap: 12px;
            margin-bottom: 25px;
        }}

        .metric {{
            background: #f9fafb;
            padding: 15px;
            border-radius: 8px;
        }}

        .metric span {{
            display: block;
            color: #6b7280;
            font-size: 12px;
            margin-bottom: 6px;
        }}

        .metric strong {{
            font-size: 20px;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
        }}

        th,
        td {{
            padding: 10px;
            border-bottom:
                1px solid #e5e7eb;
            text-align: left;
        }}

        th {{
            background: #f9fafb;
            font-size: 13px;
        }}

        footer {{
            margin-top: 30px;
            text-align: center;
            color: #6b7280;
            font-size: 13px;
        }}

    </style>

</head>

<body>

<div class="container">

    <header>

        <h1>
            MLOps Dashboard
        </h1>

        <div class="subtitle">
            Unified Multi-Model Serving Platform
        </div>

    </header>


    <section class="overview">

        <div class="overview-card">

            <span>
                Served Models
            </span>

            <strong>
                4
            </strong>

        </div>


        <div class="overview-card">

            <span>
                Service Health
            </span>

            <strong>
                {safe(health_status)}
            </strong>

        </div>


        <div class="overview-card">

            <span>
                Retraining
            </span>

            <strong>
                {safe(retraining_status)}
            </strong>

        </div>


        <div class="overview-card">

            <span>
                Auto Refresh
            </span>

            <strong>
                30s
            </strong>

        </div>

    </section>


    {''.join(model_cards)}


    <footer>

        Milestone 4 — MLOps Dashboard

        <br>

        Dashboard automatically refreshes
        every 30 seconds.

    </footer>

</div>

</body>

</html>
        """

        return HTMLResponse(
            content=page
        )

    return router