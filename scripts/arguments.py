import argparse

base_parser = argparse.ArgumentParser(
    description='Runs Playwright automated tests against the specified Isaac host.'
)
base_parser.add_argument(
    '-j',
    type=str,
    dest="job_id",
    help='The job id of this script execution. Used to tag the output file(s).',
    required=True
)
base_parser.add_argument(
    '--subject',
    type=str,
    dest="subject",
    help='Which subject\'s content to run the script against. Can be either "phy" or "ada". Defaults to "phy".',
    default="phy"
)
