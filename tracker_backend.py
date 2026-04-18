"""
tracker_backend.py — Tiny Flask endpoint that receives metrics
from siteaudit-tracker.js and pushes them to CloudWatch.

Deploy this alongside your website (e.g. as an AWS Lambda + API Gateway,
or as a route in your existing Flask/FastAPI app).

Install: pip install flask boto3
Run:     python tracker_backend.py
"""

from flask import Flask, request, jsonify
import boto3
import datetime
import os

app = Flask(__name__)

cw = boto3.client(
    "cloudwatch",
    region_name=os.getenv("AWS_REGION", "us-east-1"),
)

NAMESPACE = os.getenv("CLOUDWATCH_NAMESPACE", "SiteAudit")

ALLOWED_METRICS = {
    "ScrollDepth", "TimeOnSection", "CTAClickRate", "BounceRate"
}


@app.route("/metrics", methods=["POST"])
def receive_metric():
    try:
        data = request.get_json(silent=True) or {}
        metric  = data.get("metric")
        value   = data.get("value")
        section = data.get("section", "unknown")

        if metric not in ALLOWED_METRICS:
            return jsonify({"error": "unknown metric"}), 400
        if not isinstance(value, (int, float)):
            return jsonify({"error": "invalid value"}), 400

        cw.put_metric_data(
            Namespace=NAMESPACE,
            MetricData=[{
                "MetricName": metric,
                "Dimensions": [{"Name": "Section", "Value": section}],
                "Timestamp": datetime.datetime.utcnow(),
                "Value": float(value),
                "Unit": "Count" if metric != "TimeOnSection" else "Seconds",
            }],
        )
        return jsonify({"ok": True}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)
