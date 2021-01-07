import json
import supervisely_lib as sly
import pandas as pd
import os


def _build_catalog_index(catalog_df, catalog_index, column):
    if column not in catalog_df.columns:
        raise KeyError(f"Column {column} not found in CSV columns: {catalog_df.columns}")
    if type(catalog_index) is not dict:
        raise TypeError("Catalog index has to be of type \"dict\"")
    if len(catalog_index) != 0:
        raise ValueError("Catalog index has to be empty")

    records = json.loads(catalog_df.to_json(orient="records"))
    catalog_index = {}
    for row in records:
        catalog_index[str(row[column])] = row


def init_catalog(api: sly.Api, task_id, app_data_dir, team_id, project_id, catalog_path, column_name):
    CATALOG_DF = None


    local_path = os.path.join(app_data_dir, catalog_path.lstrip("/"))
    api.file.download(team_id, catalog_path, local_path)
    CATALOG_DF = pd.read_csv(local_path)

    _build_catalog_index()

    data = {}
    data["targetProject"] = {"id": PROJECT.id, "name": PROJECT.name}
    data["catalog"] = json.loads(CATALOG_DF.to_json(orient="split"))
    return data
