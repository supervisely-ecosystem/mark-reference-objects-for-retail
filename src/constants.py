import os
import supervisely_lib as sly

_my_app = sly.AppService()


def APP():
    return _my_app


def API():
    return _my_app.public_api


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


def _empty_string_error(var, name):
    if var == '':
        raise ValueError(f"{name} is undefined")


_CATALOG_PATH = os.environ["modal.state.catalogPath"]
_empty_string_error(_CATALOG_PATH, "CSV catalog path")
def CATALOG_PATH():
    return _CATALOG_PATH


_FIELD_NAME = os.environ["modal.state.fieldName"]
_empty_string_error(_FIELD_NAME, "Image metadata field")
def FIELD_NAME():
    return _FIELD_NAME


_COLUMN_NAME = os.environ['modal.state.columnName']
_empty_string_error(_COLUMN_NAME, "Catalog column name")
def COLUMN_NAME():
    return _COLUMN_NAME

_TARGET_CLASS_NAME = os.environ['modal.state.targetClassName']
_empty_string_error(_TARGET_CLASS_NAME, "Target class name")
def TARGET_CLASS_NAME():
    return _TARGET_CLASS_NAME

_REFERENCE_TAG_NAME = os.environ['modal.state.referenceTagName']
_empty_string_error(_REFERENCE_TAG_NAME, "Reference tag name")
def REFERENCE_TAG_NAME():
    return _REFERENCE_TAG_NAME


_MULTISELECT_CLASS_NAME = os.environ['modal.state.multiselectClassName']
_empty_string_error(_MULTISELECT_CLASS_NAME, "Multiselect class name")
def MULTISELECT_CLASS_NAME():
    return _MULTISELECT_CLASS_NAME
