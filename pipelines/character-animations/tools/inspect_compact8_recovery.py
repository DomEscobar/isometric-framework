import json
import sqlite3
import urllib.request
from pathlib import Path

root = Path(__file__).resolve().parents[1]
connection = sqlite3.connect(root / "review/compact8-cold-01/private-service-data/jobs.sqlite3")
connection.row_factory = sqlite3.Row
rows = []
for row in connection.execute("select id,state,error,result_json from stage_jobs order by created_at"):
    item = dict(row)
    if item["result_json"]:
        item["result_json"] = json.loads(item["result_json"])
    rows.append(item)
reviews = []
for row in connection.execute("select id,stage_job_id,status,record_json from automatic_reviews order by created_at"):
    item = dict(row)
    item["record_json"] = json.loads(item["record_json"])
    reviews.append(item)
connection.close()
models = json.load(urllib.request.urlopen("https://openrouter.ai/api/v1/models", timeout=30))
model = next(item for item in models["data"] if item.get("id") == "google/gemini-3.8-flash")
print(json.dumps({"stages": rows, "reviews": reviews, "live_model": {
    "id": model["id"], "reasoning": model.get("reasoning"),
    "supported_parameters": model.get("supported_parameters"),
}}, indent=2, sort_keys=True))
