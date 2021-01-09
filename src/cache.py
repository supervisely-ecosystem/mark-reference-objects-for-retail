import globals as ag
import supervisely_lib as sly
import threading

annotations = {}
anns_lock = threading.Lock()


def _download(image_id):
    ann_json = ag.api.annotation.download(image_id).annotation
    ann = sly.Annotation.from_json(ann_json, ag.meta)

    global anns_lock
    anns_lock.acquire()
    annotations[image_id] = ann
    anns_lock.release()

#@TODO: deprecated, remove later
# def _get_annotation(image_id, target_figure_id=None):
#     if image_id not in annotations:
#         _download(image_id)
#     if target_figure_id is not None:
#         ids = [label.geometry.sly_id for label in annotations[image_id].labels]
#         if target_figure_id not in ids:
#             _download(image_id)
#     return annotations[image_id]


def get_annotation(image_id):
    _download(image_id)
    return annotations[image_id]