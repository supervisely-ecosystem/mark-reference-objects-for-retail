import json
import supervisely_lib as sly

import globals as ag  # application globals
import catalog
import references
import cache
from tagging import assign


@ag.app.callback("manual_selected_image_changed")
def event_next_image(api: sly.Api, task_id, context, state, app_logger):
    user_id = context["userId"]
    cur_image_id = context["imageId"]
    cur_image_info = api.image.get_info_by_id(cur_image_id)
    field = cur_image_info.meta.get(ag.field_name, None)

    if field is None:
        fields = {
            "fieldNotFound": "Field {!r} not found".format(ag.field_name),
            "fieldValue": "",
            "catalogInfo": {}
        }
    else:
        catalog_info = catalog.index.get(field, None)
        fields = {
            "fieldNotFound": "" if catalog_info is not None else "Key {!r} not found in catalog".format(field),
            "fieldValue": field,
            "catalogInfo": catalog_info,
        }

    api.app.set_field(task_id, "data.user", {user_id: fields}, append=True)
    references.refresh_grid(user_id, field)


@ag.app.callback("assign_tag_to_object")
@sly.timeit
def assign_tag_to_object(api: sly.Api, task_id, context, state, app_logger):
    tag_meta = ag.meta.get_tag_meta(ag.reference_tag_name)
    figure_id = context["figureId"]
    image_id = context["imageId"]
    assign(figure_id, tag_meta)

    image_info = api.image.get_info_by_id(image_id)
    field_value = image_info.meta[ag.field_name]
    ann = cache.get_annotation(image_id)
    label = ann.get_label_by_id(figure_id)
    if label is None:
        raise KeyError(f"Figure with id {figureId} is not found in annotation")
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
    ann = cache.get_annotation(image_id)

    selected_label = ann.get_label_by_id(figure_id)
    if selected_label is None:
        raise KeyError(f"Figure with id {figureId} is not found in annotation")
    assign(figure_id, tag_meta)

    for idx, label in enumerate(ann.labels):
        if label.geometry.sly_id == figure_id or label.obj_class.name != ag.target_class_name:
            continue
        if label.geometry.to_bbox().intersects_with(selected_label.geometry.to_bbox()):
            assign(label.geometry.sly_id, tag_meta)
            references.add(field_value, image_info, label)
    references.refresh_grid(field_value)


def main():
    ag.init()

    data = {}
    data["user"] = {}

    data["catalog"] = {"columns": [], "data": []}
    data["ownerId"] = ag.owner_id
    data["targetProject"] = {"id": ag.project.id, "name": ag.project.name}
    data["currentMeta"] = {}
    data["fieldName"] = ag.field_name

    state = {}
    state["selectedTab"] = "product"
    state["targetClass"] = ag.target_class_name
    state["multiselectClass"] = ag.multiselect_class_name

    sly.logger.info("Initialize catalog ...")
    catalog.init()
    data["catalog"] = json.loads(catalog.df.to_json(orient="split"))

    sly.logger.info("Initialize existing references ...")
    references.index_existing()

    ag.app.run(data=data, state=state)


#@TODO: redme - Open properties when edit - disable
#@TODO: readme - create classes before start
#@TODO: support multiple-select object
#@TODO: readme- how to hide object properties on object select event
#@TODO: check that api saves userId that performed tagging action
if __name__ == "__main__":
    sly.main_wrapper("main", main)
