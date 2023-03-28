"""

    Lists paths, ids and related content for question pages

"""

# These import paths need to be prepended by "scripts." for the script_manager to work
from scripts.arguments import base_parser
from scripts.helper_functions import build_csv_from_content, value_or_default
from scripts.constants import CONTENT_BASE_PATH, OUT_DIR_PATH

CONTENT_PATH = f"{CONTENT_BASE_PATH}/questions"

# This should really be in a constants file
content_type_name_map = {
    "isaacQuestionPage": "Question page",
    "isaacConceptPage": "Concept page",
    "isaacTopicSummaryPage": "Topic summary page"
}


def json_handler(decoded_json, path_fragment, page_id, write_to_csv):
    if value_or_default(decoded_json, "type", None) not in content_type_name_map:
        # only process relevant json types
        return

    print(f"Processing {path_fragment}...")
    write_to_csv([
        path_fragment,
        page_id,
        value_or_default(decoded_json, "title", "[unknown title]"),
        content_type_name_map[decoded_json["type"]],
        value_or_default(decoded_json, "published", "-"),
        ';'.join(value_or_default(decoded_json, "tags", [])),
        ';'.join(value_or_default(decoded_json, "relatedContent", []))
    ])


if __name__ == "__main__":
    args = base_parser.parse_args()
    build_csv_from_content(CONTENT_PATH, f"{OUT_DIR_PATH}/{args.job_id}.csv", ["Path", "ID", "Title", "Page type", "Published", "Tags", "Related content"], json_handler)


def get_info():
    return {
        "name": "list_question_data",
        "description": "Lists paths, ids and related content for question pages",
        "arguments": []
    }
