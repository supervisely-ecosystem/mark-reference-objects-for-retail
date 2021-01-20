import json
import supervisely_lib as sly

import globals as ag  # application globals
import catalog
import references
import cache
from tagging import assign, delete


@ag.app.callback("manual_selected_image_changed")
def event_next_image(api: sly.Api, task_id, context, state, app_logger):
    user_id = context["userId"]
    cur_image_id = context["imageId"]
    if cur_image_id is None or type(cur_image_id) is not int:
        app_logger.warn("Image Changed event with wrong context", extra={"ui_context": context})
        return

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


def change_tag(api: sly.Api, task_id, context, state, app_logger, action_figure, action_reference):
    tag_meta = ag.meta.get_tag_meta(ag.reference_tag_name)
    userId = context["userId"]
    figure_id = context["figureId"]
    image_id = context["imageId"]

    image_info = api.image.get_info_by_id(image_id)
    field_value = image_info.meta[ag.field_name]
    ann = cache.get_annotation(image_id)
    selected_label = ann.get_label_by_id(figure_id)

    if selected_label is None:
        raise KeyError(f"Figure with id {figureId} is not found in annotation")
    if selected_label.obj_class.name == ag.target_class_name:
        action_figure(api, figure_id, tag_meta)
        action_reference(field_value, image_info, selected_label)
    elif selected_label.obj_class.name == ag.multiselect_class_name:
        for idx, label in enumerate(ann.labels):
            if label.geometry.sly_id == figure_id:
                continue
            if label.geometry.to_bbox().intersects_with(selected_label.geometry.to_bbox()):
                action_figure(api, label.geometry.sly_id, tag_meta)
                action_reference(field_value, image_info, label)
    references.refresh_grid(userId, field_value)


@ag.app.callback("assign_tag")
@sly.timeit
def assign_tag(api: sly.Api, task_id, context, state, app_logger):
    change_tag(api, task_id, context, state, app_logger, assign, references.add)


@ag.app.callback("delete_tag")
@sly.timeit
def delete_tag(api: sly.Api, task_id, context, state, app_logger):
    change_tag(api, task_id, context, state, app_logger, delete, references.delete)


@ag.app.callback("delete_reference")
@sly.timeit
def delete_reference(api: sly.Api, task_id, context, state, app_logger):
    tag_meta = ag.meta.get_tag_meta(ag.reference_tag_name)
    userId = context["userId"]
    checkboxes = state["user"][str(userId)]["cardsCheckboxes"]
    print(json.dumps(checkboxes, indent=4))
    for str_label_id, need_delete in checkboxes.items():
        if need_delete is False:
            continue
        label_id = int(str_label_id)
        image_id = references.label_to_image[label_id]
        image_info = api.image.get_info_by_id(image_id)
        field_value = image_info.meta[ag.field_name]

        delete(api, label_id, tag_meta)
        references.delete(field_value, image_info, references.label_by_id[label_id])
    references.refresh_grid(userId, field_value)


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
    state["user"] = {}

    sly.logger.info("Initialize catalog ...")
    catalog.init()
    data["catalog"] = json.loads(catalog.df.to_json(orient="split"))
    data["emptyGallery"] = references.empty_gallery

    sly.logger.info("Initialize existing references ...")
    references.index_existing()

    ag.app.run(data=data, state=state)

#@TODO: save references to file at the end
#@TODO: redme - how to hide object properties on object select event
#@TODO: readme - create classes before start
if __name__ == "__main__":
    sly.main_wrapper("main", main)
