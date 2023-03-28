import json
from pathlib import Path
from typing import Dict, Iterable
from collections.abc import Callable


def rec_list_json_files(path: str, predicate=None) -> list[str]:
    """
        Lists the paths all .json files in a given directory. Accepts a predicate to filter the returned paths (a function
        that takes the path of a file, and returns either True of False depending on if it should be kept or not)
    """
    if predicate:
        return list(filter(predicate, [str(p) for p in Path(path).rglob('*.json')]))
    return [str(p) for p in Path(path).rglob('*.json')]


# ------ CSV to dictionary format functions -------


def csv_line_to_dict(headings: Iterable[str], csv_line: str, drop_columns=None) -> Dict:
    if drop_columns is None:
        drop_columns = []

    ret = dict()
    for (k, v) in zip(headings, filter_indices(csv_line.split(','), drop_columns)):
        ret[k] = v
    return ret


def filter_indices(lst: list, drop_indicies: list[int]) -> list:
    return list(map(lambda i: lst[i], set(range(0, len(lst))).difference(set(drop_indicies))))


def csv_to_dict(csv_lines: list[str], drop_columns=None) -> list[Dict]:
    """Takes a list of comma separated values (assuming the first is the data headers),
        and an optional list of column indices to ignore """

    if drop_columns is None:
        drop_columns = []

    def format_heading(h: str) -> str:
        return ''.join(list(filter(lambda s: s.isalnum() or s in ["_"], h.lower().replace(" ", "_"))))

    headings = filter_indices(list(map(format_heading, csv_lines[0].split(','))), drop_columns)
    return list(map(lambda l: csv_line_to_dict(headings, l, drop_columns), csv_lines[1:]))


# ------- Dictionary and list functions --------


def unzip(lsts):
    """Turns a list of tuples [(x, y)] into a tuple of lists ([x], [y])"""
    return tuple(map(list, zip(*lsts)))


def setify(x: Iterable) -> list:
    return list(set(x))


# Very naive - doesn't consider commas inside values
def csv_list_to_str(xs):
    return "\"" + ",".join(xs) + "\""


def flag_is_true(d: dict, p: str) -> bool:
    return d[p] if p in d else False


def exists_and_is_eq(d: dict, p: str, v) -> bool:
    return d[p] == v if p in d else False


def value_or_default(d: dict, p: str, default):
    return d[p] if p in d else default


def exists_and_is_defined(d: dict, p: str) -> bool:
    return p in d and d[p] is not None


# ------- Functions for querying and modifying the JSON content model -------

def isQuestion(content: dict):
    return content is not None and "type" in content and content["type"] in [
        "isaacMultiChoiceQuestion",
        "isaacItemQuestion",
        "isaacReorderQuestion",
        "isaacParsonsQuestion",
        "isaacNumericQuestion",
        "isaacSymbolicQuestion",
        "isaacSymbolicChemistryQuestion",
        "isaacStringMatchQuestion",
        "isaacRegexMatchQuestion",
        "isaacFreeTextQuestion",
        "isaacSymbolicLogicQuestion",
        "isaacGraphSketcherQuestion",
        "isaacClozeQuestion"
    ]


def build_dict_from_content(path_to_content: str, json_handler=None, filter_func=None, on_object_decoded=None, verbose=False):
    """
        Helper function for building a Python dictionary from data in the Isaac content repository. Functions in about
        the same way as build_csv_from_content, but the

        See `cloze_questions_encoding.py` for a simple use case.

        :param path_to_content:     absolute path to root of isaac content (either for CS or Phy)
        :param json_handler:        a function called with the following arguments in order: the decoded JSON content object,
                                    the path stub, the top-level id of the JSON object (or "undefined" if it is missing), and a callback
                                    function which takes a key and a value, and adds it to the resulting dictionary.
        :param filter_func:         a predicate that takes the path of a page, and returns whether this page should be considered or not.
                                    For example: lambda p: "\\questions\\" in p would select only files that contain "\\questions\\"
                                    in their path. THIS FUNCTION CAN'T FILTER BASED ON JSON CONTENTS, this can be done in the
                                    one of the handler functions.
        :param on_object_decoded:   a function that takes a callback function add_to_dict, which takes a key
                                    and a value, and adds it to the final dictionary.
                                    This can be used to modify individual parts of the content model as they are being decoded. THE INNER
                                    FUNCTION MUST RETURN THE JSON OBJECT!
                                    Also takes the current content object path as a second argument.
        :param verbose:             boolean flag for whether to show info messages or not
    """
    result = {}

    def add_to_dict(key: str, value: any):
        result[key] = value

    # For the path of each directory entry...
    for path in rec_list_json_files(path_to_content, filter_func):
        # Read file
        try:
            if verbose: print(f"[INFO] Attempting to open {path}...")
            with open(path, 'r', encoding='utf-8') as fp:
                decoded_json = json.load(fp, object_hook=on_object_decoded(add_to_dict, path.split(path_to_content)[1])) if on_object_decoded is not None else json.load(fp)
        except json.JSONDecodeError as e:
            print(f"[ERROR] JSON in file {path} could not be decoded, skipping... ({e})")
            continue
        except UnicodeDecodeError as e:
            print(f"[ERROR] Unicode in file {path} could not be decoded, skipping... ({e})")
            continue
        except OSError as e:
            print(f"[ERROR] Error opening file {path}, skipping... ({e})")
            continue
        if verbose: print(f"[INFO] JSON in {path} successfully decoded!")

        if json_handler is None:
            if on_object_decoded is not None:
                on_object_decoded(add_to_dict, path.split(path_to_content)[1])(decoded_json)
        else:
            json_handler(decoded_json, path.split(path_to_content)[1], decoded_json["id"] if "id" in decoded_json else "undefined", add_to_dict)

    return result


def build_csv_from_content(path_to_content: str, csv_file_path: str, csv_column_spec: [str], json_handler, filter_func=None, on_object_decoded=None, verbose=False):
    """
        Helper function for building a CSV from data in the Isaac content repository. Recommended way to use this is to
        use `on_object_decoded` to select data you need from the decoded objects, and then `json_handler` to compute the
        data required and append it to the CSV using the provided callback function.

        See `cloze_questions_encoding.py` for a simple use case.

        :param path_to_content:     absolute path to root of isaac content (either for CS or Phy)
        :param csv_file_path:       absolute path to where you want to save the CSV file
        :param csv_column_spec:     a list of headers for the CSV file
        :param json_handler:        a function called with the following arguments in order: the decoded JSON content object,
                                    the path stub, the top-level id of the JSON object (or "undefined" if it is missing), and a callback
                                    function which receives a list of string values and appends it to the output CSV
        :param filter_func:         a predicate that takes the path of a page, and returns whether this page should be considered or not.
                                    For example: lambda p: "\\questions\\" in p would select only files that contain "\\questions\\"
                                    in their path. THIS FUNCTION CAN'T FILTER BASED ON JSON CONTENTS, this can be done in the
                                    one of the handler functions.
        :param on_object_decoded:   a function that takes a decoded JSON object, and returns it (possibly modified). This can be
                                    used to modify individual parts of the content model as they are being decoded. THIS MUST RETURN THE
                                    JSON OBJECT!
        :param verbose:             boolean flag for whether to show info messages or not
    """
    def json_handler_callback(row_values: [str]):
        # Ensure row_values has same number of items as in the column spec
        if len(row_values) != len(csv_column_spec):
            raise Exception("There need to be the same number of values on a row and columns in the CSV column specification!")
        with open(csv_file_path, "a") as out_fp:
            if verbose: print(f"[INFO] Writing {row_values} to {csv_file_path}")
            out_fp.write(f"{','.join(map(str, row_values))}\n")

    with open(csv_file_path, "w") as out_fp:
        out_fp.write(f"{','.join(map(str, csv_column_spec))}\n")

    # For the path of each directory entry...
    for path in rec_list_json_files(path_to_content, filter_func):
        # Read file
        try:
            if verbose: print(f"[INFO] Attempting to open {path}...")
            with open(path, 'r', encoding='utf-8') as fp:
                decoded_json = json.load(fp, object_hook=on_object_decoded) if on_object_decoded is not None else json.load(fp)
        except json.JSONDecodeError as e:
            print(f"[ERROR] JSON in file {path} could not be decoded, skipping... ({e})")
            continue
        except UnicodeDecodeError as e:
            print(f"[ERROR] Unicode in file {path} could not be decoded, skipping... ({e})")
            continue
        except OSError as e:
            print(f"[ERROR] Error opening file {path}, skipping... ({e})")
            continue
        if verbose: print(f"[INFO] JSON in {path} successfully decoded!")
        json_handler(decoded_json, path.split(path_to_content)[1], decoded_json["id"] if "id" in decoded_json else "undefined", json_handler_callback)


def reduce_content_tree(accumulator, combination_func, json_node):
    """
    Depth first reduction of nodes in a Isaac content JSON tree

    :param accumulator:        initial value of accumulated data
    :param combination_func:   f : accumulator -> json_node -> accumulator
    :param json_node:          root node of an Isaac content JSON tree
    :return:                   final value of accumulator
    """
    if "children" in json_node:
        for child in json_node["children"]:
            accumulator = reduce_content_tree(accumulator, combination_func, child)

    return combination_func(accumulator, json_node)


def modify_content(path_to_content: str, json_handler=None, filter_func: Callable[str, bool]=None, on_object_decoded=None, verbose=False):
    """
    Helper function for modifying content in the Isaac content repositories. You can either modify the entire parsed
    JSON by specifying a `json_handler`, or modify single objects as they are decoded by specifying `on_object_decoded`.
    The former is probably better for major structural changes to the content JSON, whereas the latter is better for
    modifying the encoding, audience, value etc. (for example) of individual content objects that you know the type or
    id of.

    You should specify arguments to this function with keywords (instead of passing them in positionally), for your own
    and other users benefit.

    See `list_questions_with_double_stage_tags.py` and `list_questions_and_concepts_related_content.py` for a simple use cases.

    See `ocr_page_word_counts.py` for a more complex use case, and `close_questions_encoding.py` for how to use the
    `on_object_decoded` callback.

    :param path_to_content:     absolute path to root of isaac content (either for CS or Phy)
    :param json_handler:        a function that takes the *entire* JSON decoded from a file, the path stub, and the page id,
                                and should return the JSON that you want to be written back to the file. Return None from this
                                function if the file should remain unchanged.
    :param filter_func:         a predicate that takes the path of a page, and returns whether this page should be considered or not.
                                For example: lambda p: "\\questions\\" in p would select only files that contain "\\questions\\"
                                in their path. THIS FUNCTION CAN'T FILTER BASED ON JSON CONTENTS, this must be done in the
                                one of the handler functions (by just returning an unmodified JSON blob if you don't want to
                                change anything).
    :param on_object_decoded:   a function that takes a callback function called notify_modifed, and returns a function that takes
                                a decoded JSON object, and returns it, calling the notify_modifed function if the JSON is modified.
                                This can be used to modify individual parts of the content model as they are being decoded. THE INNER
                                FUNCTION MUST RETURN THE JSON OBJECT!
                                Also takes the current content object path as a second argument.
    :param verbose:             boolean flag for whether to show info messages or not
    """

    file_modified = False
    def notify_object_modified():
        nonlocal file_modified
        file_modified = True

    # For the path of each directory entry...
    for path in rec_list_json_files(path_to_content, filter_func):
        file_modified = False  # Reset flag
        # Read file
        try:
            if verbose: print(f"[INFO] Attempting to open {path} for reading...")
            with open(path, 'r', encoding='utf-8') as fp:
                decoded_json = json.load(fp, object_hook=on_object_decoded(notify_object_modified, path.split(path_to_content)[1])) if on_object_decoded is not None else json.load(fp)
        except json.JSONDecodeError as e:
            print(f"[ERROR] JSON in file {path} could not be decoded, skipping... ({e})")
            continue
        except UnicodeDecodeError as e:
            print(f"[ERROR] Unicode in file {path} could not be decoded, skipping... ({e})")
            continue
        except OSError as e:
            print(f"[ERROR] Error opening file {path}, skipping... ({e})")
            continue
        if verbose: print(f"[INFO] JSON in {path} successfully decoded!")

        json_to_write = decoded_json
        if json_handler:
            json_to_write = json_handler(decoded_json, path.split(path_to_content)[1], decoded_json["id"] if "id" in decoded_json else "undefined")
            # Assume that the json_handler method will either modify the file or return None
            file_modified = True

        if file_modified and json_to_write is not None:
            # Write to file
            try:
                if verbose: print(f"[INFO] Attempting to open {path} for writing...")
                with open(path, 'w', encoding='utf-8') as fp:
                    # ensure_ascii stops special characters being escaped when dumped, so we disable it
                    json.dump(json_to_write, fp, indent=2, ensure_ascii=False)
                if verbose: print(f"[INFO] File {path} was written to.")
            except OSError as e:
                print(f"[ERROR] File {path} could not be written to, skipping... ({e})")
                continue
