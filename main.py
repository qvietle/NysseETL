import zipfile
import requests
import psycopg2
from tqdm import tqdm
from pathlib import Path

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

def main():
    get_gtfs_data()

    conn = psycopg2.connect(dbname="gtfs_warehouse")
    cur = conn.cursor()
    cur.execute("SELECT 1 as connected")
    print(cur.fetchone())

if __name__ == "__main__":
    main()


