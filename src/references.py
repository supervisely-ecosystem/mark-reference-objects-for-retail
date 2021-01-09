from collections import defaultdict
import supervisely_lib as sly
import globals as ag

data = defaultdict(lambda: defaultdict(set))
count = 0

image_by_id = {}
label_by_id = {}


def index_existing():
    global data, count

    progress = sly.Progress("Collecting existing references", ag.project.items_count, ext_logger=ag.app.logger, need_info_log=True)
    for dataset_info in ag.api.dataset.get_list(ag.project.id):
        images_infos = ag.api.image.get_list(2258, sort="name", sort_order="asc")
        for batch in sly.batched(images_infos):
            ids = [info.id for info in batch]
            anns_infos = ag.api.annotation.download_batch(dataset_info.id, ids)
            anns = [sly.Annotation.from_json(info.annotation, ag.meta) for info in anns_infos]
            for ann, image_info in zip(anns, batch):
                if ag.field_name not in image_info.meta:
                    ag.app.logger.warn(f"Field \"{ag.field_name}\" not found in metadata: "
                                       f"image \"{image_info.name}\"; id={image_info.id}")
                    continue
                field_value = image_info.meta[ag.field_name]
                for label in ann.labels:
                    label: sly.Label
                    if label.obj_class.name != ag.target_class_name:
                        continue
                    if label.tags.get(ag.reference_tag_name) is not None:
                        image_by_id[image_info.id] = image_info
                        label_by_id[label.geometry.sly_id] = label
                        data[field_value][image_info.id].add(label.geometry.sly_id)
                        count += 1
            progress.iters_done_report(len(batch))
            break #@TODO: for debug
        break  # @TODO: for debug


def add(field_value, image_info, label):
    global count
    image_by_id[image_info.id] = image_info
    label_by_id[label.geometry.sly_id] = label
    data[field_value][image_info.id].add(label.geometry.sly_id)
    count += 1


def refresh_grid(field_value):
    grid_data = {}
    selectedCard = None
    card_index = 0

    current_refs = data.get(field_value, {})

    ref_count = 0
    for ref_image_id, ref_labels_ids in current_refs.items():
        ref_count += len(ref_labels_ids)
    if ref_count <= 1:
        CNT_GRID_COLUMNS = 1
    elif ref_count <= 6:
        CNT_GRID_COLUMNS = 2
    else:
        CNT_GRID_COLUMNS = 3

    grid_layout = [[] for i in range(CNT_GRID_COLUMNS)]
    for ref_image_id, ref_labels_ids in current_refs.items():
        image_info = image_by_id[ref_image_id]
        for label_id in ref_labels_ids:
            label = label_by_id[label_id]
            grid_key = str(label_id)

            grid_data[grid_key] = {
                "url": image_info.full_storage_url,
                "figures": [label.to_json()],
                "zoomToFigure": {
                    "figureId": label_id,
                    "factor": 1.2
                }
            }
            grid_layout[card_index % CNT_GRID_COLUMNS].append(grid_key)
            if selectedCard is None:
                selectedCard = grid_key
            card_index += 1

    content = {
        "projectMeta": ag.meta.to_json(),
        "annotations": grid_data,
        "layout": grid_layout
    }

    fields = [
        {"field": "data.refCount", "payload": card_index},
        {"field": "data.referencesCount", "payload": count},
        {"field": "data.previewRefs.content", "payload": content},
    ]
    ag.api.app.set_fields(ag.task_id, fields)