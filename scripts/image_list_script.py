import os

from arguments import base_parser

from constants import CONTENT_PATH_MAP, OUT_DIR_PATH

if __name__ == '__main__':
    args = base_parser.parse_args()

    content_path = CONTENT_PATH_MAP[args.subject]

    images = []

    # Walk the content directory for images
    for path, _, files in os.walk(content_path):
        # Only consider paths where "figures" is in the path
        if "figures" not in path.split(os.sep):
            continue
        # Store the images and their full paths
        for file in files:
            images.append((file, os.path.join(path, file)))

    # Write to a file
    if not os.path.exists(f"{OUT_DIR_PATH}/{args.job_id}"):
        os.mkdir(f"{OUT_DIR_PATH}/{args.job_id}")

    with open(f"{OUT_DIR_PATH}/{args.job_id}/images.csv", "w") as f:
        f.write("Image,Full path\n")
        for (image, image_path) in images:
            f.write(f"{image},{image_path}\n")

    print(f"Found {len(images)} images.")
