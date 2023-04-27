"""
    Script manager - contains information about all scripts and provides helpers to get particular info.
    Needs to be updated when new scripts are added - this could be automated in future perhaps.
"""

GOOGLE_DOC_PUBLISH_HOW_TO = """
To publish a Google Sheet CSV so the script can access it, follow these steps:

- Open the sheet in Google Sheets
- Click File -> Share -> Publish to web
- Specify a single sheet to publish (if you have multiple sheets)
- Specify output format: Comma-separated values (.csv)
- Click Publish
- Copy the link in the text box
- Paste the link in your comment

You can unpublish the sheet after the script has finished running.

"""

SCRIPTS = {
    "list_question_data": {
        "description": "Lists paths, ids and related content for question pages",
        "arguments": [],
        "type": "read"
    },
    "link_checker": {
        "description": "Checks links across the content repository",
        "arguments": [
            {
                "param": "eps",
                "type": "text",
                "title": "Extra paths",
                "description": "A semi-colon-separated list of extra paths to check against, in addition to the default paths.",
                "example": "/pages/about_us;/pages/another_new_page;/questions/a_question_id"
            }
        ],
        "type": "read"
    },
    "find_broken_image_links": {
        "description": """
Finds all figures in the content which have a src that doesn't point to a file that exists. Relies on the fact that
figure sources are relative paths, so if figure sources point to the CDN for example (do we even do that?) then this
will flag them up as "broken".
        """,
        "arguments": [],
        "type": "read"
    },
    "compress_svgs": {
        "description": "Compresses all SVGs in the content repository",
        "arguments": [],
        "type": "write"
    },
    "image_renaming": {
        "description": "Renames images in the content repository",
        "arguments": [
            {
                "param": "csv",
                "type": "file",
                "file_type": "csv",
                "title": "Image renaming specification",
                "description": "A CSV file containing the old filename and new name of images. Schema: `old_name.ext,new_name`",
                "example": "bus_connections,ada_cs_arch_bus_connections"
            }
        ],
        "type": "write"
    },
    "image_list": {
        "description": "Lists all images in the content repository",
        "arguments": [],
        "type": "read"
    },
    "image_duplicates": {
        "description": "Dedupe images in the content repository",
        "arguments": [],
        "type": "write"
    }
}


def get_script_arguments(script_name):
    if script_name in SCRIPTS:
        return SCRIPTS[script_name]["arguments"]
    return None
