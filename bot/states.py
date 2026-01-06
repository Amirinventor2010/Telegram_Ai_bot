from enum import IntEnum


class States(IntEnum):
    HOME = 0

    # Admin: Add Template Wizard
    ADM_TPL_TITLE = 10
    ADM_TPL_DESC = 11
    ADM_TPL_PROMPT = 12
    ADM_TPL_SAMPLE = 13

    # Edit flow
    EDIT_WAIT_IMAGES = 20
    EDIT_WAIT_PROMPT = 21
    EDIT_CONFIRM = 22
