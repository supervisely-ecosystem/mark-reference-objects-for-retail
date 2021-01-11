import supervisely_lib as sly
import globals as ag


def assign(api, figure_id, tag_meta, remove_duplicates=True):
    if remove_duplicates is True:
        delete(api, figure_id, tag_meta)
    api.advanced.add_tag_to_object(tag_meta.sly_id, figure_id)


def delete(api, figure_id, tag_meta):
    tags_json = api.advanced.get_object_tags(figure_id)
    tags = sly.TagCollection.from_json(tags_json, ag.meta.tag_metas)
    for tag in tags:
        if tag.meta.sly_id == tag_meta.sly_id:
            api.advanced.remove_tag_from_object(tag_meta.sly_id, figure_id, tag.sly_id)