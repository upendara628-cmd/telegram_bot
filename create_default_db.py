import os
import json
import logging
from scraper import login_mudu_api, save_user_data

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("DBCreator")

def create():
    roll_no = os.getenv("MUDU_ROLL_NO", "2511CS020116")
    password = os.getenv("MUDU_PASSWORD", "2511CS020116")
    try:
        user_info = login_mudu_api(roll_no, password)
        save_user_data("default", user_info)
        logger.info("Successfully created database.json with default MUDU user session.")
    except Exception as e:
        logger.error(f"Failed to create default session: {e}")

if __name__ == "__main__":
    create()
