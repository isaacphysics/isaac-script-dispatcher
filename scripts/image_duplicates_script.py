# Copyright 2019 James Sharkey
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
import os
import re
import hashlib

from arguments import base_parser
from constants import CONTENT_PATH_MAP

BLOCKSIZE = 65536
API_IMAGE_URL = "/api/any/api/images/content"
html_img_regex = re.compile(r'<img(.*?)>')

###############################################################################
# How to process each image source string:
def process_image_reference(content_path, dir_path, json_path, src):
    # Check if empty string, return "" to denote no image if so:
    if src == "" or src == "/path/to/figure.svg" or src.startswith("/assets/"):
        return None
    # Get the directory in a nice format:
    # Deal with relative references to parent folders of dir_path if present.
    path = dir_path
    while "../" in src:
        src = src.replace("../", "", 1)
        path = "/".join(path.split("/")[:-1])
    # Join the image source path to the directory:
    src_path = ""
    if (("http" in src) and ("isaaccomputerscience" not in src or "cdn.isaac" in src)):
        # Ignore external links, return "" to denote no image.
        return None
    elif (API_IMAGE_URL in src):
        # If links go via API, rather than simply to content, deal with this:
        src_path = content_path + src.split(API_IMAGE_URL)[-1]
    else:
        # Otherwise just as image source to directory location,
        # removing any leading forward slash:
        if src.startswith("/"):
            src = src.replace("/", "", 1)
        src_path = path + "/" + src
    return src_path

def process_thing(content_path, dir_path, json_path, obj):
    global duplicate_image_map

    modified = False
    if "type" not in obj:
        print("Invalid object found!", json_path)
        return modified

    # Check if any images added using HTML <img> tags:
    if "value" in obj:
        matches = html_img_regex.finditer(obj["value"])
        for m in matches:
            src = m.group(1)
            src_path = process_image_reference(content_path, dir_path, json_path, src)
            if (src_path != "") and (src_path in duplicate_image_map):
                print("WARN: Duplicate image referenced in TEXT!")

    # If the current object is a figure or image, add it and return (Figures shouldn't have figures inside them!)
    if ((obj["type"] == "figure") or (obj["type"] == "image")):
        src = obj["src"]
        src_path = process_image_reference(content_path, dir_path, json_path, src)
        if (src_path != "") and (src_path in duplicate_image_map):
            canonical_image = duplicate_image_map[src_path]
            rel_path = str(os.path.relpath(canonical_image, dir_path)).replace("\\", "/")
            obj["src"] = rel_path
            modified = True

    # Otherwise, keep searching down the tree recursively adding any other images:
    if "answer" in obj:
        modified = process_thing(content_path, dir_path, json_path, obj["answer"]) or modified
    if "explanation" in obj:
        modified = process_thing(content_path, dir_path, json_path, obj["explanation"]) or modified
    if "eventThumbnail" in obj:
        modified = process_thing(content_path, dir_path, json_path, obj["eventThumbnail"]) or modified
    if obj["type"] == "isaacFeaturedProfile":
        modified = process_thing(content_path, dir_path, json_path, obj["image"]) or modified
    if obj["type"] == "isaacPod":
        modified = process_thing(content_path, dir_path, json_path, obj["image"]) or modified
    if "hints" in obj:
        for h in obj["hints"]:
            modified = process_thing(content_path, dir_path, json_path, h) or modified
    if "children" in obj:
        for c in obj["children"]:
            modified = process_thing(content_path, dir_path, json_path, c) or modified
    if "choices" in obj:
        for c in obj["choices"]:
            modified = process_thing(content_path, dir_path, json_path, c) or modified
    return modified


###############################################################################

sha_filename_map = dict()
duplicate_image_map = dict()
all_files = []

if __name__ == "__main__":
    args = base_parser.parse_args()

    content_path = CONTENT_PATH_MAP[args.subject]

    for root, directories, files in os.walk(content_path):
        for fname in files:
            all_files.append("{0}/{1}".format(root, fname).replace("\\", "/"))

    ###########################################################################
    # Find all image type files, work out their hashes:
    for fpath in all_files:
        if (fpath.lower().endswith(".svg") or fpath.lower().endswith(".png") or fpath.lower().endswith(".jpg") or fpath.lower().endswith(".gif")):
            sha1hasher = hashlib.sha1()
            with open(fpath, 'rb') as image_file:
                buf = image_file.read(BLOCKSIZE)
                while len(buf) > 0:
                    sha1hasher.update(buf)
                    buf = image_file.read(BLOCKSIZE)
            sha1hash = sha1hasher.hexdigest()
            # Record the results:
            if sha1hash not in sha_filename_map:
                sha_filename_map[sha1hash] = []
            sha_filename_map[sha1hash].append(fpath)

    ###########################################################################
    # Find duplicates, record the replacement value:
    for sha1hash, images in sha_filename_map.items():
        if len(images) > 1:
            canonical_file = sorted(sorted(images), key=lambda x: len(x))[0]
            for image_file in images:
                if image_file != canonical_file:
                    duplicate_image_map[image_file] = canonical_file

    ###########################################################################
    # Find duplicates, record the replacement value:
    for fpath in all_files:
        if fpath.lower().endswith(".json") and not fpath.lower().endswith("keep.json"):
            file_handle = open(fpath, encoding='utf-8')
            try:
                obj = json.load(file_handle)
            except UnicodeDecodeError:
                print(fpath)
                raise
            except json.JSONDecodeError:
                print(fpath)
                raise
            json_path = "/".join(fpath.split("\\"))
            dir_path = "/".join(json_path.split("/")[:-1])
            modified = process_thing(content_path, dir_path, json_path, obj)
            file_handle.close()
            if modified:
                file_handle = open(fpath, 'w', encoding="utf-8")

                data = json.dumps(obj, indent=2, separators=(',', ': '), ensure_ascii=False)
                file_handle.write(data)
