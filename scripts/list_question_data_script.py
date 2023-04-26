"""

    Lists paths, ids and related content for question pages

"""

import os

from arguments import base_parser
from helper_functions import build_csv_from_content, value_or_default
from constants import OUT_DIR_PATH, PHY_CONTENT_BASE_PATH, CS_CONTENT_BASE_PATH

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
    content_path = None
    if args.subject == "ada":
        content_path = f"{CS_CONTENT_BASE_PATH}/computer_science"
    else:
        content_path = f"{PHY_CONTENT_BASE_PATH}/questions"
    if not os.path.exists(f"{OUT_DIR_PATH}/{args.job_id}"):
        os.mkdir(f"{OUT_DIR_PATH}/{args.job_id}")
    build_csv_from_content(content_path, f"{OUT_DIR_PATH}/{args.job_id}/output.csv", ["Path", "ID", "Title", "Page type", "Published", "Tags", "Related content"], json_handler)
