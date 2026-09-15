import base64
import html as html_lib
import io
from datetime import datetime

import matplotlib
matplotlib.use("Agg")  # no display needed, just saving to file/memory
import matplotlib.pyplot as plt


def _make_metrics_bar_chart(results: dict, metric: str) -> str:
    """Builds a bar chart comparing one metric across all models, returns it
    as a base64-encoded PNG string embeddable directly in HTML (no separate
    image file needed).

    Models that don't report this metric are skipped from the chart (same
    "show what you can, don't crash" philosophy as the metrics table's N/A
    handling) rather than passing None into matplotlib, which crashes.
    """
    models = []
    values = []
    for m, model_metrics in results.items():
        v = model_metrics.get(metric)
        if isinstance(v, (int, float)):
            models.append(m)
            values.append(v)

    if not models:
        return None  # nothing to plot for this metric

    fig, ax = plt.subplots(figsize=(6, 4))
    ax.bar(models, values, color="#4a90d9")
    ax.set_ylabel(metric)
    ax.set_title(f"{metric} by model")
    plt.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8")


def generate_html_report(results: dict, baseline_comparison: dict = None,
                            significance_result: dict = None,
                            title: str = "Model Evaluation Report") -> str:
    """
    Builds a complete, self-contained HTML report from a model's results --
    the artifact a non-technical stakeholder can open in a browser and read,
    without needing to run any code or understand the underlying tools.

    results: {model_name: {metric: value}} -- same shape used everywhere
        else in this framework (compare.py, leaderboard.py)
    baseline_comparison: optional output of compare_to_baseline()
    significance_result: optional output of paired_significance_test()
    title: report heading

    All model names, metric names, and free-text values (title, significance
    interpretation) are HTML-escaped before being interpolated -- this report
    is meant to be opened in a browser or emailed, so unescaped values would
    be a real XSS vector (e.g. a model literally named "<script>...</script>").

    Returns the report as an HTML string (self-contained, images embedded
    inline as base64 -- no external files needed, so the report can be
    emailed or shared as a single .html file).
    """
    safe_title = html_lib.escape(str(title))

    all_metrics = []
    for model_metrics in results.values():
        for metric in model_metrics:
            if metric not in all_metrics:
                all_metrics.append(metric)

    metrics_table_rows = ""
    for model, model_metrics in results.items():
        safe_model = html_lib.escape(str(model))
        cells = "".join(
            f"<td>{model_metrics.get(m, 'N/A'):.4f}</td>" if isinstance(model_metrics.get(m), (int, float))
            else "<td>N/A</td>"
            for m in all_metrics
        )
        metrics_table_rows += f"<tr><td><b>{safe_model}</b></td>{cells}</tr>\n"

    metrics_header = "".join(f"<th>{html_lib.escape(str(m))}</th>" for m in all_metrics)

    charts_html = ""
    for metric in all_metrics:
        safe_metric = html_lib.escape(str(metric))
        img_b64 = _make_metrics_bar_chart(results, metric)
        if img_b64 is None:
            charts_html += f"""
            <h3>{safe_metric}</h3>
            <p><i>No models reported a numeric value for this metric.</i></p>
            """
        else:
            charts_html += f"""
            <h3>{safe_metric}</h3>
            <img src="data:image/png;base64,{img_b64}" alt="{safe_metric} chart" style="max-width:600px;">
            """

    baseline_html = ""
    if baseline_comparison:
        safe_mape_winner = html_lib.escape(str(baseline_comparison.get('mape_winner', 'N/A')))
        safe_rmse_winner = html_lib.escape(str(baseline_comparison.get('rmse_winner', 'N/A')))
        baseline_html = f"""
        <h2>Baseline Comparison</h2>
        <p>MAPE winner: <b>{safe_mape_winner}</b>
           (difference: {baseline_comparison.get('mape_diff', 0):.4f})</p>
        <p>RMSE winner: <b>{safe_rmse_winner}</b>
           (difference: {baseline_comparison.get('rmse_diff', 0):.4f})</p>
        """

    significance_html = ""
    if significance_result:
        safe_interpretation = html_lib.escape(
            str(significance_result.get('interpretation', 'No interpretation available.'))
        )
        p_value = significance_result.get("p_value")
        p_value_str = f"{p_value:.4f}" if isinstance(p_value, (int, float)) else "N/A"
        significance_html = f"""
        <h2>Statistical Significance</h2>
        <p>{safe_interpretation}</p>
        <ul>
            <li>Mean difference: {significance_result.get('mean_difference', 'N/A')}</li>
            <li>p-value: {p_value_str}</li>
            <li>Alpha: {significance_result.get('alpha', 'N/A')}</li>
        </ul>
        """

    report_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{safe_title}</title>
    <style>
        body {{ font-family: Arial, sans-serif; max-width: 900px; margin: 40px auto; color: #222; }}
        h1 {{ color: #2c5aa0; }}
        h2 {{ color: #2c5aa0; border-bottom: 1px solid #ccc; padding-bottom: 4px; }}
        table {{ border-collapse: collapse; width: 100%; margin: 16px 0; }}
        th, td {{ border: 1px solid #ccc; padding: 8px 12px; text-align: left; }}
        th {{ background: #f0f4fa; }}
        .timestamp {{ color: #888; font-size: 0.9em; }}
    </style>
</head>
<body>
    <h1>{safe_title}</h1>
    <p class="timestamp">Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>

    <h2>Metrics Summary</h2>
    <table>
        <tr><th>Model</th>{metrics_header}</tr>
        {metrics_table_rows}
    </table>

    {baseline_html}
    {significance_html}

    <h2>Charts</h2>
    {charts_html}
</body>
</html>"""

    return report_html


def save_html_report(results: dict, output_path: str, baseline_comparison: dict = None,
                        significance_result: dict = None, title: str = "Model Evaluation Report") -> None:
    """Generates the HTML report and writes it directly to a file."""
    report_html = generate_html_report(results, baseline_comparison, significance_result, title)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report_html)