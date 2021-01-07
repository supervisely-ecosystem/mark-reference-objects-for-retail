import os
import pandas as pd
import json
import pprint
import random
from collections import defaultdict
import supervisely_lib as sly

import globals as ag  # application globals

from utils import get_annotation
import catalog

my_app = sly.AppService()

TEAM_ID = int(os.environ['context.teamId'])
OWNER_ID = int(os.environ['context.userId'])
WORKSPACE_ID = int(os.environ['context.workspaceId'])

PROJECT_ID = int(os.environ['modal.state.slyProjectId'])
PROJECT = my_app.public_api.project.get_info_by_id(PROJECT_ID)
META: sly.ProjectMeta = sly.ProjectMeta.from_json(my_app.public_api.project.get_meta(PROJECT_ID))
if len(META.obj_classes) == 0:
    raise RuntimeError(f"Project {PROJECT.name} doesn't have classes")
if len(META.tag_metas) == 0:
    raise RuntimeError(f"Project {PROJECT.name} doesn't have tags (without value)")

CATALOG_PATH = os.environ['modal.state.catalogPath']
if CATALOG_PATH == '':
    raise ValueError("CSV catalog path is not defined")
FIELD_NAME = os.environ['modal.state.fieldName']
if FIELD_NAME == '':
    raise ValueError("Image metadata field is not defined")
COLUMN_NAME = os.environ['modal.state.columnName']
if COLUMN_NAME == '':
    raise ValueError("Catalog column name is not defined")
TARGET_CLASS_NAME = os.environ['modal.state.targetClassName']
if TARGET_CLASS_NAME == '':
    raise ValueError("Target class name is not defined")
REFERENCE_TAG_NAME = os.environ['modal.state.referenceTagName']
if REFERENCE_TAG_NAME == '':
    raise ValueError("Reference tag name is not defined")
MULTISELECT_CLASS_NAME = os.environ['modal.state.multiselectClassName']
if MULTISELECT_CLASS_NAME == '':
    raise ValueError("Multiselect class name is not defined")


CATALOG_DF = None
CATALOG_INDEX = None
ANNOTATIONS_CACHE = {}
FINISHED_INDEX_IMAGES = {}

REFERENCES = defaultdict(list)
image_grid_options = {
    "opacity": 0.5,
    "fillRectangle": False, #True
    "enableZoom": False,
    "syncViews": False,
    "showPreview": True,
    "selectable": True
}
image_preview_options = {
    "opacity": 0.5,
    "fillRectangle": False,
    "enableZoom": True,
    "resizeOnZoom": True
}

CNT_GRID_COLUMNS = 3


def reindex_references(api: sly.Api, task_id, app_logger):
    global REFERENCES
    REFERENCES = defaultdict(list)

    progress = sly.Progress("Collecting existing references", PROJECT.items_count, ext_logger=app_logger, need_info_log=True)
    for dataset_info in api.dataset.get_list(PROJECT.id):
        images_infos = api.image.get_list(dataset_info.id)
        for batch in sly.batched(images_infos):
            ids = [info.id for info in batch]
            anns_infos = api.annotation.download_batch(dataset_info.id, ids)
            anns = [sly.Annotation.from_json(info.annotation, META) for info in anns_infos]
            for ann, image_info in zip(anns, batch):
                if FIELD_NAME not in image_info.meta:
                    app_logger.warn(f"Field \"{FIELD_NAME}\" not found in metadata: "
                                    f"image \"{image_info.name}\"; id={image_info.id}")
                    continue

                for label in ann.labels:
                    label: sly.Label
                    if label.obj_class.name != TARGET_CLASS_NAME:
                        continue
                    if label.tags.get(REFERENCE_TAG_NAME) is not None:
                        REFERENCES[image_info.meta[field_name]].append(
                            {
                                "image_info": image_info,
                                "label": label
                            }
                        )
            progress.iters_done_report(len(batch))
            break #@TODO: for debug

    fields = [
        {"field": "data.referencesCount", "payload": sum([len(examples) for key, examples in REFERENCES.items()])},
    ]
    api.app.set_fields(task_id, fields)


@my_app.callback("manual_selected_figure_changed")
def event_next_figure(api: sly.Api, task_id, context, state, app_logger):
    print("context")
    pprint.pprint(context)
    # print("state")
    # pprint.pprint(state)
    pass


@my_app.callback("card_selected")
def card_selected(api: sly.Api, task_id, context, state, app_logger):
    app_logger.info(f"Card selected: {state['selectedCard']}")
    pass


@my_app.callback("manual_selected_image_changed")
def event_next_image(api: sly.Api, task_id, context, state, app_logger):
    image_id = context["imageId"]
    image_info = api.image.get_info_by_id(image_id)
    field = image_info.meta.get(FIELD_NAME, None)

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

        grid_data = {}
        grid_layout = [[] for i in range(CNT_GRID_COLUMNS)]
        # "zoomParams": {
        #     "annotationKey": "1",
        #     "figureId": 2,
        #     "factor": 2
        # }
        selectedCard = None
        for idx, ref_item in enumerate(current_refs):
            image_info = ref_item["image_info"]
            label = ref_item["label"]
            grid_key = str(label.geometry.sly_id)

            grid_data[grid_key] = {
                "url": image_info.full_storage_url,
                "figures": [label.to_json()],
                "zoomToFigure": {
                    "figureId": label.geometry.sly_id,
                    "factor": 1.2
                    }
            }
            grid_layout[idx % CNT_GRID_COLUMNS].append(grid_key)
            if selectedCard is None:
                selectedCard = grid_key

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
            {"field": "state.selectedCard", "payload": selectedCard},
        ])
    api.app.set_fields(task_id, fields)


@sly.timeit
def _assign_tag_to_object(api, figure_id, tag_meta, remove_duplicates=True):
    tags_json = api.advanced.get_object_tags(figure_id)
    tags = sly.TagCollection.from_json(tags_json, META.tag_metas)
    if remove_duplicates is True:
        for tag in tags:
            if tag.meta.sly_id == tag_meta.sly_id:
                api.advanced.remove_tag_from_object(tag_meta.sly_id, figure_id, tag.sly_id)
    api.advanced.add_tag_to_object(tag_meta.sly_id, figure_id)


def finish_images(images_ids):
    # finished_images = {}
    # for image_id in images_ids:
    #     finished_images[image_id] = 1
    #
    # FINISHED_INDEX_IMAGES[image_id] = 1
    # fields.extend([
    #     {"field": "data.processedImages", "payload": {image_id: 1 for image_id in images_ids}, "append": true},
    # ])
    # api.app.set_fields(task_id, fields)
    pass


@my_app.callback("assign_tag_to_object")
@sly.timeit
def assign_tag_to_object(api: sly.Api, task_id, context, state, app_logger):
    tag_name = state["referenceTag"]
    tag_meta = META.get_tag_meta(tag_name)
    _assign_tag_to_object(api, context["figureId"], tag_meta)

    image_id = context["imageId"]
    FINISHED_INDEX_IMAGES[image_id] = 1
    fields.extend([
        {"field": "data.processedImages", "payload": {image_id: 1}, "append": true},
    ])
    api.app.set_fields(task_id, fields)


@my_app.callback("multi_assign_tag_to_objects")
@sly.timeit
def assign_tag_to_object(api: sly.Api, task_id, context, state, app_logger):
    tag_name = state["referenceTag"]
    class_name = state["targetClass"]
    image_id = context["imageId"]
    figure_id = context["figureId"]

    tag_meta = META.get_tag_meta(tag_name)
    ann = get_annotation(META, ANNOTATIONS_CACHE, api, image_id, target_figure_id=figure_id)
    selected_label = None
    for label in ann.labels:
        if label.geometry.sly_id == figure_id:
            selected_label = label
            break

    _assign_tag_to_object(api, figure_id, tag_meta)
    for idx, label in enumerate(ann.labels):
        if label.geometry.sly_id == figure_id:
            continue
        if label.geometry.to_bbox().intersects_with(selected_label.geometry.to_bbox()) and label.obj_class.name == class_name:
            _assign_tag_to_object(api, label.geometry.sly_id, tag_meta)


def main():
    ag.init()

    data = {}
    data["catalog"] = {"columns": [], "data": []}
    data["ownerId"] = OWNER_ID
    data["targetProject"] = {"id": ag.project.id, "name": ag.project.name}
    data["currentMeta"] = {}
    data["fieldNotFound"] = ""
    data["fieldValue"] = ""
    data["catalogInfo"] = {}
    data["referenceExamples"] = 0
    data["referencesCount"] = 0
    data["previewRefs"] = {
        "content": {},
        "previewOptions": image_preview_options,
        "options": image_grid_options,
        "zoomParams": {}
    }
    data["processedImages"] = {}

    state = {}
    state["selectedTab"] = "product"
    state["selectedCard"] = None

    catalog.init()
    data["catalog"] = json.loads(catalog.df.to_json(orient="split"))

    #reindex_references(my_app.public_api, my_app.task_id, my_app.logger)
    my_app.run(data=data, state=state)

#@TODO: redme - Open properties when edit - disable
#@TODO: readme - create classes before start
#@TODO: support multiple-select object
#@TODO: readme- how to hide object properties on object select event
#@TODO: check that api saves userId that performed tagging action
if __name__ == "__main__":
    sly.main_wrapper("main", main)
