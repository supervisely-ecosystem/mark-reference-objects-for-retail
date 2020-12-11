import os
import pandas as pd
import json
import pprint

import supervisely_lib as sly

my_app = sly.AppService()
TEAM_ID = int(os.environ['context.teamId'])
WORKSPACE_ID = int(os.environ['context.workspaceId'])
CATALOG_PATH = os.environ['modal.state.catalogPath']

FIELD_NAME = os.environ['modal.state.fieldName']
COLUMN_NAME = os.environ['modal.state.columnName']

CATALOG_DF = None
CATALOG_INDEX = None


def build_catalog_index():
    global CATALOG_INDEX
    if CATALOG_INDEX is not None:
        return
    records = json.loads(CATALOG_DF.to_json(orient="records"))
    CATALOG_INDEX = {}
    for row in records:
        CATALOG_INDEX[row[COLUMN_NAME]] = row


@my_app.callback("init_catalog")
@sly.timeit
def init_catalog(api: sly.Api, task_id, context, state, app_logger):
    global CATALOG_DF
    local_path = os.path.join(my_app.data_dir, CATALOG_PATH.lstrip("/"))
    api.file.download(TEAM_ID, CATALOG_PATH, local_path)
    CATALOG_DF = pd.read_csv(local_path)

    if COLUMN_NAME not in CATALOG_DF.columns:
        raise KeyError(f"Column {COLUMN_NAME} not found in CSV columns: {CATALOG_DF.columns}")
    build_catalog_index()

    fields = [
        {"field": "data.catalog", "payload": json.loads(CATALOG_DF.to_json(orient="split"))}
    ]
    api.app.set_fields(task_id, fields)


@my_app.callback("manual_selected_figure_changed")
def event_next_image(api: sly.Api, task_id, context, state, app_logger):
    print("context")
    pprint.pprint(context)
    print("state")
    pprint.pprint(state)


@my_app.callback("manual_selected_image_changed")
def event_next_image(api: sly.Api, task_id, context, state, app_logger):
    # print("context")
    # pprint.pprint(context)
    # print("state")
    # pprint.pprint(state)
    pass

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
    state["fieldName"] = FIELD_NAME
    state["columnName"] = COLUMN_NAME
    state["perPage"] = 7
    my_app.run(data=data, state=state, initial_events=[{"command": "init_catalog"}])


#@TODO: FOR debug randomize image metadata field value, then implement using real fields
#@TODO: create tag if not exists
#@TODO: support multiple-select object
if __name__ == "__main__":
    sly.main_wrapper("main", main)


#events from image-annotation-tool
# export const ANNOTATION_TOOL_API_ACTIONS = {
#   SET_FIGURE: 'figures/setFigure',
#   NEXT_IMAGE: 'images/nextImage',
#   PREV_IMAGE: 'images/prevImage',
#   SET_IMAGE: 'images/setImage',
#   SET_VIEWPORT: 'scene/setViewport',
#   ZOOM_TO_OBJECT: 'scene/zoomToObject',
# };

# export const ANNOTATION_TOOL_ACTIONS_APP = {
#   MANUAL_SELECTED_IMAGE_CHANGED: 'manual_selected_image_changed',
#   MANUAL_SELECTED_FIGURE_CHANGED: 'manual_selected_figure_changed',
# };