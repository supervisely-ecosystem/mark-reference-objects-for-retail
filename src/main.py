import os
import pandas as pd
import json

import supervisely_lib as sly

my_app = sly.AppService()
TEAM_ID = int(os.environ['context.teamId'])
WORKSPACE_ID = int(os.environ['context.workspaceId'])
CATALOG_PATH = os.environ['modal.state.catalogPath']

CATALOG_DF = None
CATALOG_INDEX = None


@my_app.callback("init_catalog")
@sly.timeit
def init_catalog(api: sly.Api, task_id, context, state, app_logger):
    global CATALOG_DF
    local_path = os.path.join(my_app.data_dir, CATALOG_PATH.lstrip("/"))
    api.file.download(TEAM_ID, CATALOG_PATH, local_path)
    CATALOG_DF = pd.read_csv(local_path)

    CATALOG_INDEX

    fields = [
        {"field": "data.catalog", "payload": json.loads(CATALOG_DF.to_json(orient="split"))}
    ]
    api.app.set_fields(task_id, fields)


def main():
    sly.logger.info("Script arguments", extra={
        "TEAM_ID": TEAM_ID,
        "WORKSPACE_ID": WORKSPACE_ID,
        "CATALOG_PATH": CATALOG_PATH
    })

    data = {}
    state = {}
    data["catalog"] = {"columns": [], "data": []}
    state["selectedTab"] = "product"
    my_app.run(data=data, state=state, initial_events=[{"command": "init_catalog"}])


if __name__ == "__main__":
    sly.main_wrapper("main", main)