"""
Customer Transaction Analytics Platform: pipeline entry point.

Usage (from the project root, inside VS Code's terminal):

    python main.py                    run the full pipeline
    python main.py --dashboard        run the pipeline, then open the dashboard
    python main.py --dashboard-only   open the dashboard on the existing database

Pipeline stages
    1. Ingestion           read the 4 CSVs, identify tables, validate schema, detect relationships
    2. Cleaning            missing values, duplicates, invalid records, type conversion
    3. Merge               join dimensions onto the transaction fact
    4. Feature engineering time, amount, merchant, geo and channel features
    5. Anomaly detection   business rules, alerts and risk scores
    6. Database load       curated data into SQLite (star schema + views)
    7. KPI engine          SQL KPIs exported to CSV and Markdown reports
"""

import argparse
import subprocess
import sys
import uuid
from datetime import datetime

import pandas as pd

from src.anomaly.anomaly_detector import detect_anomalies
from src.database.db_loader import load_to_sqlite, record_pipeline_run
from src.features.feature_engineering import build_all_features
from src.ingestion.data_loader import ingest_raw_data
from src.ingestion.data_merger import merge_tables
from src.ingestion.relationship_detector import detect_relationships
from src.kpi.kpi_engine import KPIEngine, export_kpis, write_anomaly_report, write_kpi_report
from src.preprocessing.data_cleaner import clean_all_tables
from src.utils.config import DATABASE_PATH, OUTPUT_DATA_DIR, PROCESSED_DATA_DIR, PROJECT_ROOT, REPORTS_DIR
from src.utils.helpers import dataframe_to_markdown, ensure_project_directories, stage_timer, write_json
from src.utils.logger import get_logger

logger = get_logger("main")


def run_pipeline() -> dict:
    """
    Execute every stage of the batch pipeline.

    Returns:
        Run summary dictionary (also stored in the pipeline_run table).
    """
    ensure_project_directories()
    run_id = f"RUN_{datetime.now():%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:6]}"
    started_at = datetime.now()
    stage_times = {}
    logger.info("=" * 70)
    logger.info("Pipeline run %s started", run_id)

    # 1. Ingestion ---------------------------------------------------------
    with stage_timer(logger, "1. Data ingestion") as timing:
        ingestion = ingest_raw_data()
        relationships = detect_relationships(ingestion.tables)
    stage_times["ingestion"] = timing["seconds"]

    # 2. Cleaning and validation ------------------------------------------
    with stage_timer(logger, "2. Data cleaning and validation") as timing:
        cleaned, cleaning_report = clean_all_tables(ingestion.tables)
        cleaning_report.save()
        for name, frame in cleaned.items():
            frame.to_csv(PROCESSED_DATA_DIR / f"clean_{name}.csv", index=False)
    stage_times["cleaning"] = timing["seconds"]

    # 3. Merge ------------------------------------------------------------
    with stage_timer(logger, "3. Merge source tables") as timing:
        merged = merge_tables(cleaned, relationships)
    stage_times["merge"] = timing["seconds"]

    # 4. Feature engineering ---------------------------------------------
    with stage_timer(logger, "4. Feature engineering") as timing:
        features = build_all_features(merged, cleaned["customers"], cleaned["merchants"])
        features["transaction_features"].to_csv(PROCESSED_DATA_DIR / "transaction_features.csv", index=False)
        features["customer_features"].to_csv(PROCESSED_DATA_DIR / "customer_features.csv", index=False)
    stage_times["features"] = timing["seconds"]

    # 5. Rule based anomaly detection ------------------------------------
    with stage_timer(logger, "5. Rule based anomaly detection") as timing:
        anomalies = detect_anomalies(features["transaction_features"])
        anomalies["alerts"].to_csv(OUTPUT_DATA_DIR / "anomaly_alerts.csv", index=False)
        anomalies["transaction_risk"].to_csv(OUTPUT_DATA_DIR / "transaction_risk.csv", index=False)
    stage_times["anomaly"] = timing["seconds"]

    # 6. Load SQLite ------------------------------------------------------
    with stage_timer(logger, "6. Load curated data into SQLite") as timing:
        table_counts = load_to_sqlite(cleaned, features, anomalies)
    stage_times["database"] = timing["seconds"]

    # 7. KPI engine (SQL) -------------------------------------------------
    with stage_timer(logger, "7. KPI engine") as timing:
        kpi_results = KPIEngine().run_all()
        export_kpis(kpi_results)
        write_kpi_report(kpi_results)
        write_anomaly_report(kpi_results)
    stage_times["kpi"] = timing["seconds"]

    finished_at = datetime.now()
    run_info = {
        "run_id": run_id,
        "started_at": started_at.strftime("%Y-%m-%d %H:%M:%S"),
        "finished_at": finished_at.strftime("%Y-%m-%d %H:%M:%S"),
        "status": "SUCCESS",
        "raw_rows": ingestion.total_raw_rows,
        "clean_transactions": len(cleaned["transactions"]),
        "rejected_records": len(cleaning_report.rejected_records),
        "alerts_generated": len(anomalies["alerts"]),
        "duration_seconds": round((finished_at - started_at).total_seconds(), 3),
        "detected_relationships": " ; ".join(r.describe() for r in relationships),
    }
    record_pipeline_run(run_info, cleaning_report)
    _write_run_summary(run_info, stage_times, table_counts, ingestion, relationships)

    logger.info("Pipeline run %s finished in %.2f s", run_id, run_info["duration_seconds"])
    logger.info("=" * 70)
    return run_info


def _write_run_summary(run_info, stage_times, table_counts, ingestion, relationships) -> None:
    """Write reports/pipeline_summary.md and .json for the run."""
    validation_rows = [check.to_dict() for check in ingestion.validations.values()]
    write_json(
        {"run": run_info, "stage_seconds": stage_times, "schema_validation": validation_rows,
         "table_counts": table_counts.to_dict(orient="records")},
        REPORTS_DIR / "pipeline_summary.json",
    )

    lines = [
        "# Pipeline Run Summary",
        "",
        f"Run ID: `{run_info['run_id']}`  ",
        f"Started: {run_info['started_at']}  ",
        f"Finished: {run_info['finished_at']}  ",
        f"Duration: {run_info['duration_seconds']} s  ",
        f"Status: {run_info['status']}",
        "",
        "## Schema validation",
        "",
        dataframe_to_markdown(pd.DataFrame(validation_rows)),
        "## Detected relationships",
        "",
        *[f"- {r.describe()}" for r in relationships],
        "",
        "## Stage timings (seconds)",
        "",
        dataframe_to_markdown(pd.DataFrame([stage_times]), float_format="{:.3f}"),
        "## SQLite table row counts",
        "",
        dataframe_to_markdown(table_counts),
        f"Database file: `{DATABASE_PATH.relative_to(PROJECT_ROOT)}`",
    ]
    (REPORTS_DIR / "pipeline_summary.md").write_text("\n".join(lines), encoding="utf-8")


def launch_dashboard() -> None:
    """Start the Streamlit dashboard using the current Python interpreter."""
    app_path = PROJECT_ROOT / "src" / "dashboard" / "app.py"
    logger.info("Launching dashboard: streamlit run %s", app_path)
    subprocess.run([sys.executable, "-m", "streamlit", "run", str(app_path)], check=False)


def parse_arguments() -> argparse.Namespace:
    """Command line options."""
    parser = argparse.ArgumentParser(description="Customer Transaction Analytics Platform")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--dashboard", action="store_true", help="run the pipeline and then open the dashboard")
    group.add_argument("--dashboard-only", action="store_true", help="open the dashboard without re-running the pipeline")
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_arguments()
    if arguments.dashboard_only:
        launch_dashboard()
    else:
        try:
            run_pipeline()
        except Exception:
            logger.exception("Pipeline failed")
            sys.exit(1)
        if arguments.dashboard:
            launch_dashboard()
