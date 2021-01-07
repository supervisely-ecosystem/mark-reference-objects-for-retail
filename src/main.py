import json
import pprint
import supervisely_lib as sly

import globals as ag  # application globals
import catalog
import references
import cache
from tagging import assign




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
    cur_image_id = context["imageId"]
    cur_image_info = api.image.get_info_by_id(cur_image_id)
    field = cur_image_info.meta.get(ag.field_name, None)

    fields = []
    if field is None:
        fields.extend([
            {"field": "data.fieldNotFound", "payload": "Field {!r} not found".format(ag.field_name)},
            {"field": "data.fieldValue", "payload": ""},
            {"field": "data.catalogInfo", "payload": ""},
        ])
    else:
        catalog_info = catalog.index.get(field, None)
        fieldNotFound = ""
        if catalog_info is None:
            fieldNotFound = "Key {!r} not found in catalog".format(field)

        references.refresh_grid(field)

        fields.extend([
            {"field": "data.fieldNotFound", "payload": fieldNotFound},
            {"field": "data.fieldValue", "payload": field},
            {"field": "data.catalogInfo", "payload": catalog_info},
        ])
    api.app.set_fields(task_id, fields)



@ag.app.callback("assign_tag_to_object")
@sly.timeit
def assign_tag_to_object(api: sly.Api, task_id, context, state, app_logger):
    tag_meta = ag.meta.get_tag_meta(ag.reference_tag_name)
    figure_id = context["figureId"]
    image_id = context["imageId"]
    assign(figure_id, tag_meta)

    image_info = api.image.get_info_by_id(image_id)
    field_value = image_info.meta[ag.field_name]
    ann = cache.get_annotation(image_id, target_figure_id=figure_id)
    label = ann.get_label_by_id(figure_id)
    references.add(field_value, image_info, label)
    references.refresh_grid(field_value)


@ag.app.callback("multi_assign_tag_to_objects")
@sly.timeit
def multi_assign_tag_to_objects(api: sly.Api, task_id, context, state, app_logger):
    image_id = context["imageId"]
    image_info = api.image.get_info_by_id(image_id)
    field_value = image_info.meta[ag.field_name]

    figure_id = context["figureId"]
    tag_meta = ag.meta.get_tag_meta(ag.reference_tag_name)
    ann = cache.get_annotation(image_id, target_figure_id=figure_id)

    selected_label = ann.get_label_by_id(figure_id)
    assign(figure_id, tag_meta)
    for idx, label in enumerate(ann.labels):
        if label.geometry.sly_id == figure_id or label.obj_class.name != ag.target_class_name:
            continue
        if label.geometry.to_bbox().intersects_with(selected_label.geometry.to_bbox()):
            assign(label.geometry.sly_id, tag_meta)
            references.add(field_value, image_info, label)


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
    data["referencesCount"] = references.count

    ag.app.run(data=data, state=state)


#@TODO: references for images - found/total неправильно работают
#@TODO: redme - Open properties when edit - disable
#@TODO: readme - create classes before start
#@TODO: support multiple-select object
#@TODO: readme- how to hide object properties on object select event
#@TODO: check that api saves userId that performed tagging action
if __name__ == "__main__":
    sly.main_wrapper("main", main)
