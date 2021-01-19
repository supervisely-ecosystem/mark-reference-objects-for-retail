from collections import defaultdict
import threading
import supervisely_lib as sly
import globals as ag

data = defaultdict(lambda: defaultdict(set))
count = 0

image_by_id = {}
label_by_id = {}
label_to_image = {}
modify_lock = threading.Lock()

empty_gallery = {
    "content": {
        "projectMeta": {},
        "annotations": {},
        "layout": []
    },
    "previewOptions": ag.image_preview_options,
    "options": ag.image_grid_options,
}


def index_existing():
    global data, count

    progress = sly.Progress("Collecting existing references", ag.project.items_count, ext_logger=ag.app.logger,
                            need_info_log=True)
    for dataset_info in ag.api.dataset.get_list(ag.project.id):
        images_infos = ag.api.image.get_list(dataset_info.id, sort="name", sort_order="asc")
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
                        add(field_value, image_info, label)
            progress.iters_done_report(len(batch))
            #break  # @TODO: for debug
        #break  # @TODO: for debug

    sly.Progress("App is ready", 1, ext_logger=ag.app.logger).iter_done_report()


def add(field_value, image_info, label):
    global count, modify_lock
    modify_lock.acquire()
    image_by_id[image_info.id] = image_info
    label_by_id[label.geometry.sly_id] = label
    label_to_image[label.geometry.sly_id] = image_info.id
    data[field_value][image_info.id].add(label.geometry.sly_id)
    count += 1
    modify_lock.release()


def delete(field_value, image_info, label):
    global count, modify_lock
    modify_lock.acquire()
    image_by_id[image_info.id] = image_info
    label_by_id[label.geometry.sly_id] = label
    if label.geometry.sly_id in data[field_value][image_info.id]:
        data[field_value][image_info.id].remove(label.geometry.sly_id)
        count -= 1
    modify_lock.release()


def refresh_grid(user_id, field_value):
    grid_data = {}
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

    cards_checkboxes = {}
    grid_layout = [[] for i in range(CNT_GRID_COLUMNS)]
    for ref_image_id, ref_labels_ids in current_refs.items():
        image_info = image_by_id[ref_image_id]
        for label_id in ref_labels_ids:
            label = label_by_id[label_id]
            grid_key = str(label_id)

            cards_checkboxes[grid_key] = False
            grid_data[grid_key] = {
                "labelId": grid_key,  # duplicate for simplicity
                "url": image_info.full_storage_url,
                "figures": [label.to_json()],
                "zoomToFigure": {
                    "figureId": label_id,
                    "factor": 1.2
                }
            }
            grid_layout[card_index % CNT_GRID_COLUMNS].append(grid_key)
            card_index += 1

    fields = {
        "refCount": ref_count,
        "totalRefCount": count,
        "previewRefs": {
            "content": {
                "projectMeta": ag.meta.to_json(),
                "annotations": grid_data,
                "layout": grid_layout
            },
            "previewOptions": ag.image_preview_options,
            "options": ag.image_grid_options,
        }
    }
    ag.api.app.set_field(ag.task_id, f"data.user.{user_id}", fields, append=True)
    ag.api.app.set_field(ag.task_id, f"state.user.{user_id}.cardsCheckboxes", cards_checkboxes)

