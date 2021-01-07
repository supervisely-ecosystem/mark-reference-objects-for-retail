import json
import pprint
import supervisely_lib as sly

import globals as ag  # application globals
import catalog
import references
from utils import get_annotation
from tagging import assign

CNT_GRID_COLUMNS = 3


@ag.app.callback("manual_selected_figure_changed")
def event_next_figure(api: sly.Api, task_id, context, state, app_logger):
    print("context")
    pprint.pprint(context)
    # print("state")
    # pprint.pprint(state)
    pass


@ag.app.callback("card_selected")
def card_selected(api: sly.Api, task_id, context, state, app_logger):
    app_logger.info(f"Card selected: {state['selectedCard']}")
    pass


@ag.app.callback("manual_selected_image_changed")
def event_next_image(api: sly.Api, task_id, context, state, app_logger):
    image_id = context["imageId"]
    image_info = api.image.get_info_by_id(image_id)
    field = image_info.meta.get(ag.field_name, None)

    fields = []
    if field is None:
        fields.extend([
            {"field": "data.fieldNotFound", "payload": "Field {!r} not found".format(ag.field_name)},
            {"field": "data.fieldValue", "payload": ""},
            {"field": "data.catalogInfo", "payload": ""},
        ])
    else:
        catalog_info = catalog.index.get(field, None)
        current_refs = references.data.get(field, [])

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
            "projectMeta": ag.meta.to_json(),
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


@ag.app.callback("assign_tag_to_object")
@sly.timeit
def assign_tag_to_object(api: sly.Api, task_id, context, state, app_logger):
    tag_meta = ag.meta.get_tag_meta(ag.reference_tag_name)
    assign(context["figureId"], tag_meta)


@ag.app.callback("multi_assign_tag_to_objects")
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
    data["ownerId"] = ag.owner_id
    data["targetProject"] = {"id": ag.project.id, "name": ag.project.name}
    data["currentMeta"] = {}
    data["fieldNotFound"] = ""
    data["fieldValue"] = ""
    data["catalogInfo"] = {}
    data["referenceExamples"] = 0
    data["previewRefs"] = {
        "content": {},
        "previewOptions": ag.image_preview_options,
        "options": ag.image_grid_options,
        "zoomParams": {}
    }
    data["processedImages"] = {}
    data["fieldName"] = ag.field_name

    state = {}
    state["selectedTab"] = "product"
    state["selectedCard"] = None
    state["targetClass"] = ag.target_class_name
    state["multiselectClass"] = ag.multiselect_class_name

    sly.logger.info("Initialize catalog ...")
    catalog.init()
    data["catalog"] = json.loads(catalog.df.to_json(orient="split"))

    sly.logger.info("Initialize existing references ...")
    references.index_existing()
    data["referencesCount"] = sum([len(examples) for key, examples in references.data.items()])
    ag.app.run(data=data, state=state)


#@TODO: redme - Open properties when edit - disable
#@TODO: readme - create classes before start
#@TODO: support multiple-select object
#@TODO: readme- how to hide object properties on object select event
#@TODO: check that api saves userId that performed tagging action
if __name__ == "__main__":
    sly.main_wrapper("main", main)
