import json
import pandas as pd
import os
import globals as ag

df = None
index = None


def _build_catalog_index():
    global index
    if ag.column_name not in df.columns:
        raise KeyError(f"Column {ag.column_name} not found in CSV columns: {df.columns}")
    records = json.loads(df.to_json(orient="records"))
    index = {str(row[ag.column_name]): row for row in records}


def init():
    global df
    local_path = os.path.join(ag.app.data_dir, ag.catalog_path.lstrip("/"))
    ag.api.file.download(ag.team_id, ag.catalog_path, local_path)
    df = pd.read_csv(local_path)
    _build_catalog_index()