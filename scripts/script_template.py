import os

from arguments import base_parser
from constants import OUT_DIR_PATH, CONTENT_PATH_MAP
from helper_functions import build_csv_from_content, modify_content, value_or_default

"""
! IMPORTANT !

When you add a new script, you must:
- Ensure the filename is {unique script name}_script.py
- Make sure that the script throws informative errors, if for example it is being run for the wrong subject
- Write any output files to the f"{OUT_DIR_PATH}/{args.job_id}" directory so the worker can pick them up afterwards
- Add a new entry to the SCRIPTS dictionary in script_manager.py, with the key being "{unique script name}" 
    (i.e. without the "_script" suffix)
- Add {unique script name} to the list in script-run.yml file in isaacphysics/isaac-dispatched-scripts
- (Optional but preferred) Add an entry to the README.md file in isaacphysics/isaac-dispatched-scripts explaining
    what the script does 
"""

# Example of a function that reads from content and produces a CSV file
def read_from_content_example(content_path, args):
    # This is the function that will be called for each json file in the content directory. It is passed the decoded
    # json object, the path fragment (the path relative to the content directory), the page id (the last part of the
    # path) and a function (`write_to_csv`) that can be called to write a row to the output CSV file.
    def build_csv_json_handler(decoded_json, path_fragment, page_id, write_to_csv):
        if value_or_default(decoded_json, "type", None) is not "isaacQuestionPage":
            # only process relevant json types
            return

        # `write_to_csv` is a function that writes a single row in the output CSV file. The values should be in the same
        # order as the headers specified in build_csv_from_content.
        write_to_csv([
            path_fragment,
            page_id,
            value_or_default(decoded_json, "title", "[unknown title]"),
            "Question page",
            value_or_default(decoded_json, "published", "-"),
            ';'.join(value_or_default(decoded_json, "tags", [])),
            ';'.join(value_or_default(decoded_json, "relatedContent", []))
        ])

    # If you want to write a csv file, you can use the build_csv_from_content helper function.
    build_csv_from_content(
        content_path,
        f"{OUT_DIR_PATH}/{args.job_id}/output.csv",
        ["Path", "ID", "Title", "Page type", "Published", "Tags", "Related content"],
        build_csv_json_handler
    )


# Example of a function that modifies content
def modify_content_example(content_path, args):

    def modify_content_json_handler(decoded_json, path_fragment, page_id):
        if value_or_default(decoded_json, "type", None) is not "isaacQuestionPage":
            # only process relevant json types
            return None
        decoded_json["type"] = "isaacFastTrackQuestionPage"  # Here you can modify the json object
        return decoded_json

    def on_object_decoded_builder(notify_modified):
        def on_object_decoded(json, path_fragment, page_id):
            if value_or_default(json, "type", None) is not "figure":
                # only process relevant json types
                return json  # Return the json object (you have to do this if you don't want to modify it)

            # Here you can modify the json object
            json["value"] = f"A new description for the image {value_or_default(json, 'src', '[unknown image]')}"

            # You NEED to call this if you have modified the json object, otherwise your changes will not be saved
            # (unless you are using modify_content_json_handler as well, and the page gets modified there)
            notify_modified()

            return json  # Return the (now modified) json object

        return on_object_decoded

    # If you want to modify the content, you can use the modify_content helper function. You can filter based on the
    # file path - filtering based on anything else will need to be done in the json_handler or on_object_decoded function.
    modify_content(
        content_path,
        json_handler=modify_content_json_handler,
        filter_func=lambda p: "question" in p,
        on_object_decoded=on_object_decoded_builder,
        verbose=False  # Set this to True for debugging purposes (it defaults to False)
    )


# Add new arguments to base_parser like so - these should be recorded in `script_manager.py` so the user can be
# prompted for them when they run the script.
base_parser.add_argument(
    '--new_argument',
    type=str,
    dest="new_argument",
    help='Description of new argument',
    default=""
)

if __name__ == '__main__':
    args = base_parser.parse_args()

    # Get the content path from the subject argument (which is added to base_parser by default). There is also
    # PHY_CONTENT_BASE_PATH and CS_CONTENT_BASE_PATH exported from constants.py, which you could use if you want to
    # pick different subdirectories of the content directory based on the subject.
    content_path = CONTENT_PATH_MAP[args.subject]

    # Create the output directory. The output directory is named after the job_id argument (added to base_parser by
    # default), and should be a directory, **not a file**. It can be used to store any output files generated by the
    # script.
    if not os.path.exists(f"{OUT_DIR_PATH}/{args.job_id}"):
        os.mkdir(f"{OUT_DIR_PATH}/{args.job_id}")

    read_from_content_example(content_path, args)

    modify_content_example(content_path, args)
