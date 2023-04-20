# Copyright 2015 James Sharkey
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
import sys
from constants import CS_CONTENT_BASE_PATH, OUT_DIR_PATH

###############################################################################
# Useful settings:

print_to_file = True
live_only = True

# subdir = "/questions"
# subdir = "/concepts"
subdir = ""

link_regex = re.compile(r'\\link{(.*?)}{(.*?)}')  # Need to extract group 2
href_regex = re.compile(r'<a href=(\"|\')(.*?)(\"|\')')  # Need to extract group 2 (other groups for " versus ')
markdown_regex = re.compile(r'\[(.*?)\]\((.*?)\)')  # Need to extract group 2
fake_url_regex = re.compile(r'(url:)(.*)')  # Need to extract group 2, group 1 is fake

###############################################################################
# Global variables:
error_string = ""
link_errors = 0
link_count = 0


symbolic_links = {
    "/pages/about_us": "/about",
    "/pages/privacy_policy": "/privacy",
    "/pages/cookies": "/cookies",
    "/pages/cyberessentials": "/cyberessentials",
    "/pages/accessibility_statement": "/accessibility",
    "/pages/teaching_order": "/teaching_order",
    "/pages/terms_of_use": "/terms",
    "/pages/student_rewards_programme": "/student_rewards",
    "{{pageFragment}}/support_student_homework": "/support/student/homework",
    "{{pageFragment}}/support_student_general": "/support/student/general",
    "{{pageFragment}}/support_teacher_general": "/support/teacher/general"
}

existing_pages = {
    "/", "/login", "/register", "/account", "/account#emailpreferences", "/account#teacherconnections",
    "/coming_soon", "/progress", "/assignments", "/boards", "/concepts", "/gameboards", "/gameboards/new",
    "/game_builder", "/gameboard_builder", "/assignment_progress", "/my_markbook", "/set_assignments",
    "/groups", "/quizzes", "/tests", "/set_quizzes", "/topics", "/topics/gcse", "/topics/gcse#all",
    "/topics/a_level", "/teacher_account_request", "/contact", "/events", "/robots.txt"
}
existing_pages.update(list(symbolic_links.values()))

existing_links = set()
external_links = set()
gameboard_ids = set()
link_src_dict = {}


###############################################################################
# Check a link for obvious errors; containing a backslash or an (internal) link not starting with a forward slash:
def link_contains_errors(link, src_path, link_type):
    global link_errors, error_string
    editor_link = src_path.replace(CS_CONTENT_BASE_PATH, "https://editor.isaaccomputerscience.org/#!/edit/master/content")
    if "\\" in link:
        link_errors += 1
        error_string += 'Invalid Link in %s\n     %s link "%s" should not contain a "\\" character.\n\n' % (editor_link, link_type, link)
        return True
    if not link.startswith("/"):
        link_errors += 1
        error_string += 'Invalid Link in %s\n     %s link "%s" should start with a "/" character.\n\n' % (editor_link, link_type, link)
        return True
    if link.endswith("/"):
        link_errors += 1
        error_string += 'Invalid Link in %s\n     %s link "%s" should not end with a "/" character.\n\n' % (editor_link, link_type, link)
        return True
    return False


def parse_link_address(link_address, src_path, link_type):
    global error_string, external_links, gameboard_ids
    link_address = link_address.replace("https://isaaccomputerscience.org", "").replace("{{siteBaseURL}}", "")  # Make any Isaac links local by removing the first part
    if link_address == "":
        return
    if (("/add_gameboard/" in link_address) or ("/assignment/" in link_address) or ("/board/" in link_address) or ("http" in link_address) or ("www" in link_address) or ("mailto:" in link_address)):
        if ("/add_gameboard/" not in link_address) and ("/assignment/" not in link_address) and ("/board/" not in link_address):  # We don't want to do anything with gameboard links, otherwise
            external_links.add(link_address)  # if it's an external link add it to the list so it can be checked if necessary.
        else:
            gameboard_id = link_address.replace("/board/", "").replace("/add_gameboard/", "").replace("/assignment/", "")
            gameboard_ids.add(gameboard_id)
        return

    if "/s/" in link_address:  # If it contains a "/s/" then it's a share URL:
        external_links.add("https://isaaccomputerscience.org%s" % link_address)  # Treat it as an external link.
        return

    if (("/#" in link_address) or ("/gameboards#" in link_address)):  # If it contains a "/#" then it's a gameboard hash, not an accordion/question ID
        link_address, gameboard_id = link_address.split("#")  # so drop the bit after the hash
        gameboard_ids.add(gameboard_id)

    if (link_address.startswith("{{") and link_address.endswith("}}")):  # If link_address is enclosed in {{...}}
        external_links.add(link_address)  # then it's probably an email field to be autofilled.
        return

    link_address = link_address.split("?")[0]

    if not link_contains_errors(link_address, src_path, link_type):
        return link_address


def process_possible_link(match, src_path, link_type):
    global link_count, link_src_dict
    link_count += 1
    link_address = str(match.group(2))  # Extract group 2
    link_address = parse_link_address(link_address, src_path, link_type)
    if link_address is not None:  # If no errors in parse_link_address()
        existing_links.add(link_address)  # add to the link set.
        try:
            link_src_dict[link_address].append(src_path)
        except KeyError:
            link_src_dict[link_address] = [src_path]
    return


###############################################################################
# How to process each JSON object:
def process_thing(json_path, published, page_link, obj):
    global link_count, link_src_dict, existing_links, existing_pages
    assert "type" in obj, "JSON Parse Error: Object has no type property!" + json_path + "\t" + str(obj)
    # Implement checking if live or not:
    if "published" in obj:            # If live_only is true, published by default false so if the page contains a published tag and that
        if obj["published"] is True:  # tag is "true", change published. Otherwise, if live_only is false then published is by default true,
            published = True          # and so anything with published==false will still be processed. Any other way of changing published would not ensure this.

    if not published:  # If it's not published, don't check it. Setting live-only to false overrides this.
        return

    # First, see if accordion/tab section and deal with appropriately:
    if (("title" in obj) and ("id" in obj) and ("children" in obj)):  # If has a title, id and children; must be an accordion part or tab
        acc_id = str(obj["id"])  # Which can be referenced by its ID
        if acc_id != "":  # Provided the ID isn't blank, add the "page_link#acc_id" to existing_pages
            if page_link in symbolic_links:  # If there's a human-friendly symbolic link too:
                existing_pages.add("%s#%s" % (page_link, acc_id))
                existing_pages.add("%s#%s" % (symbolic_links[page_link], acc_id))  # Deal with fact can link to accordion via it too
            else:
                existing_pages.add("%s#%s" % (page_link, acc_id))

    # What to do with any content blocks we reach in the search:
    if "value" in obj:
        value = obj["value"]

        # If the content might contain a [...](...) link:
        if "[" in value:
            matches = markdown_regex.finditer(value)
            for m in matches:
                process_possible_link(m, json_path, "[]()")
        # Or a \\link link:
        if "\\link" in value:
            matches = link_regex.finditer(value)
            for m in matches:
                process_possible_link(m, json_path, "\\link{}{}")
        # Or a <a href> link
        if "a href" in value:
            matches = href_regex.finditer(value)
            for m in matches:
                process_possible_link(m, json_path, "<a href>")

    # Pods and wildcards have "url" links, images have "clickUrl" links. Check them:
    if ("url" in obj) or ("clickUrl" in obj):
        obj_url = obj.get("url") if "url" in obj else obj.get("clickUrl")
        fake_link_text = "url:%s" % (obj_url)
        matches = fake_url_regex.finditer(fake_link_text)
        for m in matches:
            process_possible_link(m, json_path, obj["type"])

    # If it's a question; we can link to it, so add its link to existing pages:
    question_types = ["isaac{}Question".format(qt) for qt in ["", "MultiChoice", "Numeric", "Symbolic", "SymbolicChemistry", "FreeText", "StringMatch"]]
    if obj["type"] in question_types:
        q_id = str(obj["id"])
        if q_id != "":
            existing_pages.add("%s#%s" % (page_link, q_id))

    page_id = ""
    # If it's a question page; add its link to existing pages:
    if ((obj["type"] == "isaacQuestionPage") or (obj["type"] == "isaacFastTrackQuestionPage")):
        page_id = str(obj["id"])
        page_link = "/questions/%s" % page_id
        existing_pages.add(page_link)
    # If it's a concept page; add its link to existing pages:
    if obj["type"] == "isaacConceptPage":
        page_id = str(obj["id"])
        page_link = "/concepts/%s" % page_id
        existing_pages.add(page_link)
    # If it's a just a page; add its link to existing pages:
    if obj["type"] == "page":
        page_id = str(obj["id"])
        page_link = "/pages/%s" % page_id
        existing_pages.add(page_link)
    # If it's an event; add its link to existing pages:
    if obj["type"] == "isaacEventPage":
        page_id = str(obj["id"])
        page_link = "/events/%s" % page_id
        existing_pages.add(page_link)
    # If it's a topic summary; add its link to existing pages:
    if obj["type"] == "isaacTopicSummaryPage":
        page_id = str(obj["id"])
        page_link = "/topics/%s" % page_id.replace("topic_summary_", "")
        existing_pages.add(page_link)
    # If it's a page fragment; hack to add its link to existing pages:
    if obj["type"] == "isaacPageFragment":
        page_id = str(obj["id"])
        page_link = "{{pageFragment}}/%s" % page_id
        existing_pages.add(page_link)

    # Finished processing.
    # Keep searching deeper in the tree if possible:
    if "answer" in obj:
        process_thing(json_path, published, page_link, obj["answer"])
    if "explanation" in obj:
        process_thing(json_path, published, page_link, obj["explanation"])
    if "choices" in obj:
        for c in obj["choices"]:
            process_thing(json_path, published, page_link, c)
    if "hints" in obj:
        for h in obj["hints"]:
            process_thing(json_path, published, page_link, h)
    if "children" in obj:
        for c in obj["children"]:
            process_thing(json_path, published, page_link, c)


###############################################################################
# The main function:
def main(args):
    global error_string, correct_links, link_count, link_src_dict, existing_links, \
        existing_pages, gameboard_ids, external_links

    # Create output directory if it doesn't exist:
    if print_to_file:
        if not os.path.exists(f"{OUT_DIR_PATH}/{args.job_id}"):
            os.mkdir(f"{OUT_DIR_PATH}/{args.job_id}")

    """The main function, search for JSON files and run process_thing() on each."""
    if live_only:
        print("\nONLY ERRORS IN PUBLISHED FILES WILL BE FOUND AND OUTPUTTED!")

    all_files = []
    for root, directories, files in os.walk(CS_CONTENT_BASE_PATH + subdir):
        for fname in files:
            all_files.append(f"{root}/{fname}")

    ###########################################################################
    # Find all manually entered links in JSON files:
    for fpath in all_files:
        if fpath.lower().endswith(".json") and not fpath.lower().endswith("keep.json"):
            file_handle = open(fpath, encoding='utf-8')
            try:
                obj = json.load(file_handle)
            except (UnicodeDecodeError, ValueError) as e:
                print(fpath)
                raise Exception(e)
            process_thing(fpath, not live_only, "", obj)

    print("")
    # If any serious errors, i.e. poorly formatted links then output the list:
    if error_string != "":
        error_string = "SERIOUS ERRORS FOUND:\n%s" % error_string
        if print_to_file:
            with open(f"{OUT_DIR_PATH}/{args.job_id}/link_errors.txt", 'w') as f:
                f.write(error_string)
        else:
            sys.stdout.write(error_string)
            sys.stdout.write("==================================================\n\n")

    # Work out what are non-existent links, and compile non-exhaustive list
    # (The set means duplicates are gone; code will need multiple runs to give all occurrences . . .)
    correct_links = existing_links.intersection(existing_pages)
    nonexistent = existing_links.difference(existing_pages)
    nonexistent_string = "Links to non-existent pages found. This list contains all dead links:\n"
    nonexistent_string += "==================================================\n\n"
    nonexistent = sorted(nonexistent, key=lambda s: s.lower())
    nonexistent_count = 0
    for n in nonexistent:
        for page in link_src_dict[n]:
            nonexistent_count += 1
            nonexistent_string += "Dead link found in %s\n" % str(page.replace(CS_CONTENT_BASE_PATH, "https://editor.isaaccomputerscience.org/#!/edit/master/content"))
            nonexistent_string += '     Link address "%s" does not exist.\n\n' % n

    # If any broken links, output the list:
    if len(nonexistent) > 0:
        if print_to_file:
            with open(f"{OUT_DIR_PATH}/{args.job_id}/dead_links.txt", 'w') as f:
                f.write(nonexistent_string)
        else:
            sys.stdout.write(nonexistent_string)
            sys.stdout.write("==================================================\n\n")

    # Even if no errors, if print_to_file then output allowed links:
    if print_to_file:
        with open(f"{OUT_DIR_PATH}/{args.job_id}/external_links.txt", 'w') as f:
            f.write("\n".join(sorted(external_links, key=lambda s: s.lower())))
        with open(f"{OUT_DIR_PATH}/{args.job_id}/allowed_links.txt", 'w') as f:
            f.write("\n".join(sorted(existing_pages, key=lambda s: s.lower())))
        with open(f"{OUT_DIR_PATH}/{args.job_id}/gameboard_ids.txt", 'w') as f:
            f.write("\n".join(sorted(gameboard_ids, key=lambda s: s.lower())))

    # Output a useful summary:
    print("Total links processed: %s" % link_count)
    print("Linkable content locations: %s" % len(existing_pages))
    print("Ill-formatted links found: %s" % link_errors)
    print("Links to non-existent pages: %s" % nonexistent_count)
