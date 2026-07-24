import os
import sys

from dotenv import load_dotenv
from pymongo import MongoClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.db_setup import initialize_exam_centric_collections  # noqa: E402


def main():
    load_dotenv()
    mongo_uri = os.getenv("MONGO_URI")
    if not mongo_uri:
        password = os.getenv("MONGO_PASSWORD")
        mongo_uri = "mongodb+srv://stevenkashaigili340:{}@cluster0.fsedap8.mongodb.net/?appName=Cluster0".format(password)
    db_name = os.getenv("MONGO_DB_NAME", "Studetails")
    client = MongoClient(mongo_uri)
    seeded = initialize_exam_centric_collections(client[db_name])
    print("Duration rules seeded: {}".format(seeded))


if __name__ == "__main__":
    main()
