# Constants required for scripts to work inside the docker container
CONTENT_BASE_DIR = r'data'
PHY_CONTENT_BASE_PATH = r'data/rutherford-content/content'
CS_CONTENT_BASE_PATH = r'data/ada-content/content'
CONTENT_PATH_MAP = {
    "phy": PHY_CONTENT_BASE_PATH,
    "ada": CS_CONTENT_BASE_PATH
}
OUT_DIR_PATH = r'./output'
