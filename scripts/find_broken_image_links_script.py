"""

    Finds all figures in the content which have a src that doesn't point to a file that exists. Relies on the fact that
    figure sources are relative paths, so if figure sources point to the CDN for example (do we even do that?) then this
    will flag them up as "broken".

"""
import os

from helper_functions import build_dict_from_content, value_or_default, exists_and_is_defined
from pathlib import Path

# Settings
from arguments import base_parser
from constants import CS_CONTENT_BASE_PATH, PHY_CONTENT_BASE_PATH, OUT_DIR_PATH

CONTENT_PATH = None
out_file = r'image_issues.txt'

def object_decoded_func_builder(add_to_dict, path_fragment):
    def on_object_decoded(decoded_json):
        if decoded_json is not None and value_or_default(decoded_json, "type", None) == "figure" and exists_and_is_defined(decoded_json, "src"):
            path_part_list = path_fragment.split("/")
            directory = "/".join(path_part_list[0:-1])
            file_name = path_part_list[-1]
            add_to_dict(f"{directory}/{decoded_json['src']}", f"{directory}/{file_name}")

    return on_object_decoded


if __name__ == "__main__":
    args = base_parser.parse_args()
    if args.subject == "ada":
        CONTENT_PATH = f"{CS_CONTENT_BASE_PATH}/computer_science"
    else:
        CONTENT_PATH = PHY_CONTENT_BASE_PATH
    if not os.path.exists(f"{OUT_DIR_PATH}/{args.job_id}"):
        os.mkdir(f"{OUT_DIR_PATH}/{args.job_id}")
    image_references = build_dict_from_content(CONTENT_PATH, on_object_decoded=object_decoded_func_builder)
    with open(f"{OUT_DIR_PATH}/{args.job_id}/{out_file}", "w") as f:
        for image_src, page_path in image_references.items():
            if not Path(f"{CONTENT_PATH}{image_src}").exists():
                f.write(f"Broken figure src \"{image_src}\" in content page {CONTENT_PATH}{page_path}\n")
