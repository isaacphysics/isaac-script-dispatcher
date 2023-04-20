from arguments import base_parser
from cs_link_checker import main as cs_link_checker_main
from phy_link_checker import main as phy_link_checker_main

base_parser.add_argument(
    '--eps',
    type=str,
    dest="extra_paths",
    help='A comma-separated list of extra paths to check against, in addition to the default paths.',
    default=""
)

if __name__ == '__main__':
    args = base_parser.parse_args()
    print("Extra paths given as argument:", args.extra_paths)
    if args.subject == "ada":
        cs_link_checker_main(args)
    else:
        phy_link_checker_main(args)
