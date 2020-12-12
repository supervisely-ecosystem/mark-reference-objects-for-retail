import os
import pandas as pd
import json
import pprint

import supervisely_lib as sly

my_app = sly.AppService()
TEAM_ID = int(os.environ['context.teamId'])
OWNER_ID = int(os.environ['context.userId'])
WORKSPACE_ID = int(os.environ['context.workspaceId'])
PROJECT_ID = int(os.environ['modal.state.slyProjectId'])
CATALOG_PATH = os.environ['modal.state.catalogPath']
FIELD_NAME = os.environ['modal.state.fieldName']
COLUMN_NAME = os.environ['modal.state.columnName']

PROJECT = None
META = None
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
    global CATALOG_DF, META, PROJECT
    local_path = os.path.join(my_app.data_dir, CATALOG_PATH.lstrip("/"))
    api.file.download(TEAM_ID, CATALOG_PATH, local_path)
    CATALOG_DF = pd.read_csv(local_path)

    if COLUMN_NAME not in CATALOG_DF.columns:
        raise KeyError(f"Column {COLUMN_NAME} not found in CSV columns: {CATALOG_DF.columns}")
    build_catalog_index()

    PROJECT = api.project.get_info_by_id(PROJECT_ID)

    meta_json = api.project.get_meta(PROJECT_ID)
    META = sly.ProjectMeta.from_json(meta_json)
    if len(META.obj_classes) == 0:
        raise RuntimeError(f"Project {PROJECT.name} doesn't have classes")

    class_names = []
    for obj_class in META.obj_classes:
        class_names.append(obj_class.name)
    tag_names = []
    for tag_meta in META.tag_metas:
        tag_meta: sly.TagMeta
        if tag_meta.value_type == sly.TagValueType.NONE:
            tag_names.append(tag_meta.name)
    if len(META.tag_metas) == 0:
        raise RuntimeError(f"Project {PROJECT.name} doesn't have tags (without value)")

    fields = [
        {"field": "data.targetProject", "payload": {"id": PROJECT.id, "name": PROJECT.name}},
        {"field": "data.catalog", "payload": json.loads(CATALOG_DF.to_json(orient="split"))},
        {"field": "data.objectClasses", "payload": class_names},
        {"field": "state.targetClass", "payload": class_names[0]},
        {"field": "data.tags", "payload": tag_names},
        {"field": "state.referenceTag", "payload": tag_names[0]},
        {"field": "state.multiselectClass", "payload": ""},
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
    data["ownerId"] = OWNER_ID
    state["selectedTab"] = "product"
    state["fieldName"] = FIELD_NAME
    state["columnName"] = COLUMN_NAME
    state["perPage"] = 7
    state["targetClass"] = ""
    state["referenceTag"] = ""
    state["objectClasses"] = []
    state["multiselectClass"] = ""
    my_app.run(data=data, state=state, initial_events=[{"command": "init_catalog"}])


# classId - multiselect mark
#@TODO: check project from context in HTML?
#@TODO: FOR debug randomize image metadata field value, then implement using real fields
#@TODO: support multiple-select object
#@TODO: readme - hide object properties when edit
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