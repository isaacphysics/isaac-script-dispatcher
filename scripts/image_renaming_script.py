import csv
import os
import re

from arguments import base_parser
from helper_functions import value_or_default, modify_content
from constants import CONTENT_PATH_MAP

RENAME_MAP = dict()


def on_object_decoded_builder(notify_modified, path_fragment):
    def on_object_decoded(json):
        if value_or_default(json, "type", None) not in ["figure", "image"]:
            return json

        # Split the src into the path and the filename
        path, filename = json["src"].rsplit("/", 1) if "/" in json["src"] else (None, json["src"])

        if filename in RENAME_MAP:
            # Rename the image
            json["src"] = f"{path + '/' if path else ''}{RENAME_MAP[filename]}"
            notify_modified()

        return json

    return on_object_decoded


base_parser.add_argument(
    '--csv',
    type=str,
    dest="csv",
    help='Path to the csv file containing old and new image names.',
    default=""
)

if __name__ == '__main__':
    args = base_parser.parse_args()

    content_path = CONTENT_PATH_MAP[args.subject]

    # Read the csv file
    with open(args.csv, "r") as f:
        print(f"Reading {args.csv}...")
        # Read the csv file
        csv_reader = csv.reader(f, delimiter=',')
        for row in csv_reader:
            name = row[0]
            new_name = row[1]
            # Check that name ends with a file extension
            if not re.match(r".*\.[a-zA-Z0-9]+$", name):
                print(f"WARNING: Image {name} has no extension, skipping.")
                continue
            extension = name.rsplit(".", 1)[1]
            # Add to the rename map
            RENAME_MAP[name] = new_name + "." + extension

    print(f"Renaming {len(RENAME_MAP)} images...")

    modify_content(
        content_path,
        on_object_decoded=on_object_decoded_builder,
    )

    # Walk the content directory and rename the images given in the rename map
    for path, _, files in os.walk(content_path):
        # Only consider paths where "figures" is in the path
        if "figures" not in path.split(os.sep):
            continue
        for file in files:
            if file in RENAME_MAP:
                # Rename the image
                os.rename(os.path.join(path, file), os.path.join(path, RENAME_MAP[file]))
