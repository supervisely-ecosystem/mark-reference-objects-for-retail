import os
import pandas as pd
import json
import pprint
import random
from collections import defaultdict

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

REFERENCES = defaultdict(list)
image_grid_options = {
    "opacity": 0.5,
    "fillRectangle": False, #True, False
    "enableZoom": False,
    "syncViews": False,
    "showPreview": True
}
image_preview_options = {
    "opacity": 0.5,
    "fillRectangle": False,
    "enableZoom": True,
}

CNT_GRID_COLUMNS = 3


def build_catalog_index():
    global CATALOG_INDEX
    if CATALOG_INDEX is not None:
        return
    records = json.loads(CATALOG_DF.to_json(orient="records"))
    CATALOG_INDEX = {}
    for row in records:
        CATALOG_INDEX[str(row[COLUMN_NAME])] = row


@my_app.callback("reindex_references")
@sly.timeit
def reindex_references(api: sly.Api, task_id, context, state, app_logger):
    global REFERENCES
    REFERENCES = defaultdict(list)
    fields = [
        {"field": "data.reindexing", "payload": True},
    ]
    api.app.set_fields(task_id, fields)

    reference_tag_name = state["referenceTag"]
    target_class_name = state["targetClass"]
    field_name = state["fieldName"]

    for dataset_info in api.dataset.get_list(PROJECT.id):
        images_infos = api.image.get_list(dataset_info.id)
        for batch in sly.batched(images_infos):
            ids = [info.id for info in batch]
            anns_infos = api.annotation.download_batch(dataset_info.id, ids)
            anns = [sly.Annotation.from_json(info.annotation, META) for info in anns_infos]
            for ann, image_info in zip(anns, batch):
                if field_name not in image_info.meta:
                    # @TODO: for debug
                    image_info.meta[field_name] = str(857717004131)
                    # logger.warn(f"Field {state['fieldName']} not found in metadata: "
                    #             f"image \"{image_info.name}\"; id={image_info.id}")
                    # continue

                for label in ann.labels:
                    label: sly.Label
                    if label.obj_class.name != target_class_name:
                        continue
                    if label.tags.get(reference_tag_name) is not None:
                        REFERENCES[image_info.meta[field_name]].append(
                            {
                                "image_info": image_info,
                                "label": label
                            }
                        )

    fields = [
        {"field": "data.reindexing", "payload": False},
        {"field": "data.referencesCount", "payload": sum([len(examples) for key, examples in REFERENCES.items()])},
    ]
    api.app.set_fields(task_id, fields)


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
        {"field": "data.referenceExamples", "payload": 0},
        {"field": "state.referenceTag", "payload": tag_names[0]},
        {"field": "state.multiselectClass", "payload": ""},
        {"field": "data.reindexing", "payload": False},
        {"field": "data.referencesCount", "payload": 0},
        {"field": "data.previewRefs", "payload": {"content": {},
                                                  "previewOptions": image_preview_options,
                                                  "options": image_grid_options,
                                                  "zoomParams": {}}},
    ]
    api.app.set_fields(task_id, fields)


@my_app.callback("manual_selected_figure_changed")
def event_next_figure(api: sly.Api, task_id, context, state, app_logger):
    # print("context")
    # pprint.pprint(context)
    # print("state")
    # pprint.pprint(state)
    pass


@my_app.callback("manual_selected_image_changed")
def event_next_image(api: sly.Api, task_id, context, state, app_logger):
    image_id = context["imageId"]
    image_info = api.image.get_info_by_id(image_id)
    meta = dict((k.lower(), v) for k, v in image_info.meta.items())
    field = meta.get(state["fieldName"], None)
    #@TODO: for debug
    field = str(857717004131)

    fields = []
    if field is None:
        fields.extend([
            {"field": "data.fieldNotFound", "payload": "Field {!r} not found".format(state["state.fieldName"])},
            {"field": "data.fieldValue", "payload": ""},
            {"field": "data.catalogInfo", "payload": ""},
        ])
    else:
        catalog_info = CATALOG_INDEX.get(field, None)
        current_refs = REFERENCES.get(field, [])
        # random.shuffle(current_refs)

        grid_data = {}
        grid_layout = [[] for i in range(CNT_GRID_COLUMNS)]
        # "zoomParams": {
        #     "annotationKey": "1",
        #     "figureId": 2,
        #     "factor": 2
        # }
        for idx, ref_item in enumerate(current_refs):
            image_info = ref_item["image_info"]
            label = ref_item["label"]
            grid_data[label.geometry.sly_id] = {
                "url": image_info.full_storage_url,
                "figures": [label.to_json()],
                "zoomToFigure": {
                    "figureId": label.geometry.sly_id,
                    "factor": 2
                    }
            }
            grid_layout[idx % CNT_GRID_COLUMNS].append(label.geometry.sly_id)

        fieldNotFound = ""
        if catalog_info is None:
            fieldNotFound = "Key {!r} not found in catalog".format(field)

        content = {
            "projectMeta": META.to_json(),
            "annotations": grid_data,
            "layout": grid_layout
        }

        fields.extend([
            {"field": "data.fieldNotFound", "payload": fieldNotFound},
            {"field": "data.fieldValue", "payload": field},
            {"field": "data.catalogInfo", "payload": catalog_info},
            {"field": "data.refCount", "payload": len(current_refs)},
            {"field": "data.previewRefs.content", "payload": content},
        ])
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
    data["ownerId"] = OWNER_ID
    data["currentMeta"] = {}
    data["fieldNotFound"] = ""
    data["fieldValue"] = ""
    data["catalogInfo"] = {}

    state["selectedTab"] = "product"
    state["fieldName"] = FIELD_NAME
    state["columnName"] = COLUMN_NAME
    state["perPage"] = 7
    state["targetClass"] = ""
    state["referenceTag"] = ""
    state["objectClasses"] = []
    state["multiselectClass"] = ""

    # build_references(api, referenceTag, app_logger)


    my_app.run(data=data, state=state, initial_events=[{"command": "init_catalog"}])


# classId - multiselect mark
#@TODO: support multiple-select object
#@TODO: readme- how to hide object properties on object select event
#@TODO: check that api saves userId that performed tagging action
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