# isaac-script-dispatcher

A bot that runs scripts on the Isaac and Ada content when "asked" via GitHub issues in [isaacphysics/isaac-dispatched-scripts](https://github.com/isaacphysics/isaac-dispatched-scripts).

The idea is to make the scripts that we (the Isaac/Ada tech team) write available to the content teams, so that they can run them without having Python installed, the content repositories available locally, or any programming knowledge.

Kinds of scripts that would be useful to add to this bot:
- Ones that require running frequently
- Ones that are flexible and can do different things depending on the arguments given
- Ones that make many changes to the content repo

If a script makes changes to the content repo (and it's `type` is `write` in `script_manager.py`), then it can automatically open a PR on the content repositories. 
This is really useful if a script makes many changes to the content, as the diffs can be stepped through systematically by anyone.

## Deployment

Re-build and deploy with `docker-compose up -d --build`. For local development, the script dispatcher runs on port 5000.

## How to add new scripts

**Scripts are added to the [isaacphysics/isaac-scripts](https://github.com/isaacphysics/isaac-scripts) repository**, in the `script-dispatcher` folder. 
On startup, the script dispatcher pulls that repository - any new scripts added will require the script dispatcher to be restarted 
(we could fix this by doing the same thing as for the content repos - checking for changes on master every time a new script issue is opened and pulling if so)   

When you add a new script, you must:
- Ensure the filename is `{unique script name}_script.py`
- Make sure that the script throws/prints informative errors, for example if it is being run for Isaac when it only works for Ada 
- Write any output files to the `f"{OUT_DIR_PATH}/{args.job_id}"` directory so the worker can pick them up afterwards
- Add any new requirements (libraries used in new scripts) to the `requirements.txt` file **in this repository**
- Add a new entry to the `SCRIPTS` dictionary in `script_manager.py` **in this repository**, with the key being `"{unique script name}"` (i.e. without the `_script` suffix)
- Add `{unique script name}` to the list in `script-run.yml` file in [isaacphysics/isaac-dispatched-scripts](https://github.com/isaacphysics/isaac-dispatched-scripts)
- (Optional but preferred) Add an entry to the `README.md` file in [isaacphysics/isaac-dispatched-scripts](https://github.com/isaacphysics/isaac-dispatched-scripts) explaining what the script does so the content teams know how to use it, what to expect, etc.

If the script is taking in a CSV argument, look at the `image_attribution` script for an example of how to do this. In particular, check `script_manager.py` for an example user prompt for the CSV, and the script itself to see how to read the provided CSV.
