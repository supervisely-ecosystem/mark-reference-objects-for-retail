import supervisely_lib as sly
import threading


anns_lock = threading.Lock()


def get_annotation(meta, annotations, api: sly.Api, image_id, force=False, target_figure_id=None):
    def _download():
        ann_json = api.annotation.download(image_id).annotation
        ann = sly.Annotation.from_json(ann_json, meta)

        global anns_lock
        anns_lock.acquire()
        annotations[image_id] = ann
        anns_lock.release()

    if image_id not in annotations:
        _download()
    if target_figure_id is not None:
        ids = [label.geometry.sly_id for label in annotations[image_id].labels]
        if target_figure_id not in ids:
            _download()

    return annotations[image_id]