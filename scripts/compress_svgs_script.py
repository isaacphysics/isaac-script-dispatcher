import os
import subprocess

from arguments import base_parser
from constants import CONTENT_PATH_MAP

tot_saved = 0.0
n_saved = 0


def process_accordion_section(obj, _id, concept_title):
    print('{},"{}","{}"'.format(_id, concept_title, obj["title"]))


def compress_svg(svg_filename):
    # convert = subprocess.call(["C:/Program Files/Inkscape/inkscape", svg_filename, "--export-plain-svg", svg_filename], shell=True)
    temp_filename = "{}.temp".format(svg_filename)
    convert = subprocess.call(["scour", "--strip-xml-prolog", "--set-precision=10", "--enable-comment-stripping", "-i", svg_filename, "-o", temp_filename])
    if convert != 0:
        raise IOError(convert)
    os.remove(svg_filename)
    os.rename(temp_filename, svg_filename)


def process_svg(svg_filename):
    global tot_saved, n_saved
    size = os.stat(svg_filename).st_size
    if size > 300 * 1024:
        compress_svg(svg_filename)
        new_size = os.stat(svg_filename).st_size
        saved = size - new_size
        tot_saved += saved
        n_saved += 1
        print("Saved {0} bytes ({1:.2f}%)!".format(saved, (100.0*saved)/size))


if __name__ == '__main__':
    args = base_parser.parse_args()
    for root, directories, files in os.walk(CONTENT_PATH_MAP[args.subject]):
        for fname in files:
            if fname.lower().endswith(".svg"):
                fpath = os.path.join(root, fname)
                print(f"Found SVG: {fpath}")
                process_svg(fpath)

    print("Saved {0} bytes ({1:.2f}kb = {2:.2f}Mb)".format(tot_saved, tot_saved/1024.0, tot_saved/(1024.0*1024.0)))
    print("Saved average {0} bytes over files ({1:.2f}kb = {2:.2f}Mb)".format(
        tot_saved/n_saved if n_saved > 0 else 0,
        tot_saved/(1024.0*n_saved) if n_saved > 0 else 0,
        tot_saved/(1024.0*1024.0*n_saved) if n_saved > 0 else 0
    ))
