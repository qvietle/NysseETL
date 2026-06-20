import zipfile
import requests
import psycopg2
import os
from tqdm import tqdm
from pathlib import Path

TYPE_MAP = {
    "agency_id" : "TEXT",
    "agency_name" : "TEXT",
    "agency_url" : "TEXT",
    "agency_timezone" : "TEXT",
    "agency_lang" : "VARCHAR(2)",
    "agency_phone" : "TEXT",
    "agency_fare_url" : "TEXT",
    "service_id" : "TEXT",
    "monday" : "INTEGER",
    "tuesday" : "INTEGER",
    "wednesday" : "INTEGER",
    "thursday" : "INTEGER",
    "friday" : "INTEGER",
    "saturday" : "INTEGER",
    "sunday" : "INTEGER",
    "start_date" : "DATE",
    "end_date" : "DATE",
    "exception_type" : "INTEGER",
    "id" : "INTEGER",
    "name" : "TEXT",
    "route_id" : "TEXT",
    "route_short_time" : "INTEGER",
    "route_long_name" : "TEXT",
    "route_type" : "INTEGER",
    "route_url" : "TEXT",
    "route_color" : "TEXT",
    "route_text_color" : "TEXT",
    "shape_id" : "TEXT",
    "shape_pt_lat" : "FLOAT",
    "shape_pt_lon" : "FLOAT",
    "shape_pt_sequence" : "INTEGER",
    "stop_id" : "TEXT",
    "stop_code" : "TEXT",
    "stop_name" : "TEXT",
    "stop_lat" : "FLOAT",
    "stop_lon" : "FLOAT",
    "zone_id" : "CHAR(1)",
    "wheelchair_boarding" : "TEXT",
    "wheelchair_accessible" : "TEXT",
    "municipality_id" : "INTEGER",
    "from_stop_id" : "TEXT",
    "to_stop_id" : "TEXT",
    "transfer_type" : "INTEGER",
    "min_transfer_time" : "TEXT",
    "from_route_id" : "TEXT",
    "from_trip_id" : "TEXT",
    "to_route_id" : "TEXT",
    "to_trip_id" : "TEXT",
    "trip_id" : "TEXT",
    "trip_headsign" : "TEXT",
    "direction_id" : "TEXT",
    "block_id" : "TEXT",
    "shape_id" : "TEXT",
    "bikes_allowed" : "INTEGER",
    "date" : "DATE",
    "route_short_name" : "TEXT"
}

PRIMARY_KEYS = {
    "agency" : "agency_id",
    "calendar" : "service_id",
    "calendar_dates" : "service_id, date",
    "municipalities" : "name",
    "routes" : "route_id",
    "shapes" : "shape_id, shape_pt_sequence",
    "stops" : "stop_id",
    "transfers" : "from_trip_id, to_trip_id",
    "trips" : "trip_id"

}

def get_gtfs_data():
    download_url = "https://data.itsfactory.fi/journeys/files/gtfs/latest/extended_gtfs_tampere.zip"
    zip_output_path = Path("data") / "extended_gtfs_tampere.zip"

    if zip_output_path.exists():
        print(f"File already exists at {zip_output_path}")
    else:
        print("Downloading GTFS data...")
        headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        response = requests.get(download_url, headers=headers, stream=True)
        if response.status_code == 200:
            zip_output_path.parent.mkdir(parents=True, exist_ok=True)
            total_size = int(response.headers.get('content-length', 0))
            total_len = len(response.content)
            with tqdm(total=total_size, unit='B', unit_scale=True, desc="Downloadingl", colour="green") as pbar:
                with open(zip_output_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                        pbar.update(len(chunk))

            print(f"Downloaded successfully to {zip_output_path} ({total_len} bytes)")
        else:
            print(f"Failed download: HTTP {response.status_code}")

    dir_output_path = Path("data/extended_gtfs_tampere")
    
    if not dir_output_path.exists():
        print(f"Creating a dir to {dir_output_path}")
        dir_output_path.mkdir(parents=True)
        with zipfile.ZipFile(zip_output_path, "r")  as zf:
            zf.extractall(dir_output_path)
    else:
        print(f"Dir already exists at {dir_output_path}")

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
        print("THIS SHIT IS NOT EMPTY")
        return


    cols = get_cols(file_path)
    with open(file_path, 'r') as f:
        cur.copy_expert(f"COPY {table_name} FROM STDIN CSV HEADER", f)

def get_files():
    dir = "data/extended_gtfs_tampere"
    txt_files = os.listdir(dir)
    abs_paths = [os.path.abspath(os.path.join(dir, f)) for f in txt_files]
    return abs_paths
        

def initialize_db(cur):

    abs_paths = get_files()
    for file in abs_paths:
        if (Path(file).stem not in ["stop_times", "fare_attributes", "fare_rules"]):
            print(f"creating table for {file}")
            table_name = file.split('/')[-1].split('.')[0]
            create_table(cur, table_name, file)
            copy_table(cur, table_name, file)

def main():
    get_gtfs_data()


    conn = psycopg2.connect(dbname="gtfs_warehouse")
    cur = conn.cursor()

    initialize_db(cur)
    conn.commit()



if __name__ == "__main__":
    main()


