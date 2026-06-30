import zipfile
import requests
import psycopg2
import os
import logging
import csv
from tqdm import tqdm
from pathlib import Path
from dotenv import load_dotenv
from schema_config import TYPE_MAP, PRIMARY_KEYS, TABLES_TO_SKIP


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
)

logger = logging.getLogger(__name__)


def get_gtfs_data():
    download_url = os.getenv('GTFS_FEED_URL', 'https://data.itsfactory.fi/journeys/files/gtfs/latest/extended_gtfs_tampere.zip')

    file_name = os.path.basename(download_url)
    zip_output_path = Path("data") / file_name

    if zip_output_path.exists():
        logger.info(f"File already exists at {zip_output_path}")
    else:
        logger.info("Downloading GTFS data...")
        headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        response = requests.get(download_url, headers=headers, stream=True)
        if response.status_code == 200:
            zip_output_path.parent.mkdir(parents=True, exist_ok=True)
            total_size = int(response.headers.get('content-length', 0))
            with tqdm(total=total_size, unit='B', unit_scale=True, desc="Downloading", colour="green") as pbar:
                with open(zip_output_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                        pbar.update(len(chunk))

            logger.info(f"Downloaded successfully to {zip_output_path} ({total_size/1000000} megabytes Mb)")
        else:
            logger.info(f"Failed download: HTTP {response.status_code}")

    file_dir = file_name.split('.')[0]

    dir_output_path = Path("data") / file_dir
    if not dir_output_path.exists():
        logger.info(f"Creating a dir to {dir_output_path}")
        dir_output_path.mkdir(parents=True)
        with zipfile.ZipFile(zip_output_path, "r")  as zf:
            zf.extractall(dir_output_path)
    else:
        logger.info(f"Dir already exists at {dir_output_path}")
    
    return file_dir
def get_cols(file_path):


    with open(file_path) as f:
        header = f.readline().strip().split(',')
        cols = ", ".join([f"{c} {TYPE_MAP.get(c, 'TEXT')}" for c in header])
        return cols
        
def create_table(cur, table_name, file_path):

        cols = get_cols(file_path)

        cur.execute(f"DROP TABLE IF EXISTS {table_name}")
        cur.execute(
            f"""
                CREATE TABLE {table_name}  (
                {cols}
                )
            """
        )

        pk = PRIMARY_KEYS.get(table_name)
        if pk:
            cur.execute(f"ALTER TABLE {table_name} ADD PRIMARY KEY ({pk})")

def copy_table(cur, table_name, file_path):

    cur.execute(f"SELECT EXISTS (SELECT 1 FROM {table_name})")
    not_empty = cur.fetchone()[0]

    if (not_empty):

        return

    row_count = 0

    cols = get_cols(file_path)

    # Count rows
    with open(file_path, 'r') as f:
        reader = csv.reader(f)
        row_count = sum(1 for row in reader)

    # Load data
    with open(file_path, 'r') as f:
        cur.copy_expert(f"COPY {table_name} FROM STDIN CSV HEADER", f)

    return row_count

def get_files(file_name):
    dir = f"data/{file_name}"
    txt_files = os.listdir(dir)
    abs_paths = [os.path.abspath(os.path.join(dir, f)) for f in txt_files]
    return abs_paths
        

def initialize_db(cur, file_name):

    abs_paths = get_files(file_name)
    row_counts = {}
    tablerow_counts = {}
    for file in abs_paths:
        name = Path(file).stem
        if (name not in TABLES_TO_SKIP):
            logger.info(f"creating table for {file}")
            table_name = file.split('/')[-1].split('.')[0]

            create_table(cur, table_name, file)
            row_count = copy_table(cur, table_name, file)
            cur.execute(f"SELECT COUNT(*) FROM {table_name}")
            tablerow_count = cur.fetchone()[0]
            row_counts[table_name] = row_count-1
            tablerow_counts[table_name] = tablerow_count

            logger.info(f"[{table_name}] Source: {row_counts[table_name]} Target: {tablerow_counts[table_name]} ")
        
    return row_counts == tablerow_counts

def main():

    load_dotenv()
    file_name = get_gtfs_data()

    db_user = os.getenv('DB_USER')
    db_host = os.getenv('DB_HOST')
    db_port = os.getenv('DB_PORT')
    db_name = os.getenv('DB_NAME')
    db_password = os.getenv('DB_PASSWORD')

    
    conn = psycopg2.connect(dbname=db_name, user=db_user, password=db_password, host=db_host, port=db_port)
    cur = conn.cursor()

    init_ok = initialize_db(cur, file_name)
    if init_ok:
        conn.commit()
        logger.info("Database initialized successfully")
    else:
        conn.rollback()
        logger.error("Database initialization failed")



if __name__ == "__main__":
    main()


