import json
from pathlib import Path
from napalm import get_network_driver
from datetime import datetime

def load_json():
    """
    Load JSON data of the routers
    """
    local_path = Path(__file__).resolve().parent / "sshinfo.json"
    cwd_path = Path("./sshinfo.json")
    path = local_path if local_path.exists() else cwd_path

    if not path.exists():
        raise FileNotFoundError("JSON file not found")

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)
    

def get_configs(ssh_data, router_name, router_index):
    """
    Connect to a router and fetch its configs
    save to a file with the timestamp.
    """
    device = {
        "hostname": ssh_data["IPS"][router_index],
        "username": ssh_data["user"],
        "password": ssh_data["pass"],
    }

    try:
        driver = get_network_driver("ios")
        conn = driver(**device)
        conn.open()

        # Fetch running configuration
        config_data = conn.get_config()
        config_output = config_data["running"]
        conn.close()

        timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        filename = f"{router_name}_{timestamp}.txt"

        # Save config to file
        with open(filename, "w") as f:
            f.write(config_output)

        return filename
    
    except Exception as e:
        return f"Error fetching config for {router_name}. {str(e)}"


def fetch_all_configs():
    try:
        data = load_json()
        routers = ["R1", "R2", "R3", "R4"]
        files = []

        for index, router_name in enumerate(routers):
            filename = get_configs(data, router_name, index)
            files.append(filename)

        return files
    
    except Exception as e:
        return [f"Error: {str(e)}"]