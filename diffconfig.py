from pathlib import Path
from napalm import get_network_driver
from getconfig import load_json


def find_latest_saved(router_name):
    p = Path('.')
    pattern = f"{router_name}_*.txt"
    candidates = list(p.glob(pattern))
    if not candidates:
        return None
    candidates.sort(key=lambda f: f.stat().st_mtime, reverse=True)
    return candidates[0]





def diff_configs():
    ssh = load_json()

    routers = ["R1", "R2", "R3", "R4"]
    diffs = {}
    for idx, r in enumerate(routers):
        latest = find_latest_saved(r)

        if latest is None:
            diffs[r] = "No previous saved config file found."
            continue

        # read saved config
        try:
            with open(latest, 'r', encoding='utf-8') as f:
                saved = f.read()
        except Exception as e:
            diffs[r] = f"Error reading saved file {latest}: {e}"
            continue

        # connect to device and compare
        try:
            driver = get_network_driver("ios")
            device = {
                "hostname": ssh["IPS"][idx],
                "username": ssh["user"],
                "password": ssh["pass"],
            }
            dev = driver(**device)
            dev.open()
            dev.load_merge_candidate(config=saved)
            diff_text = dev.compare_config()
            dev.discard_config()
            dev.close()
            diffs[r] = diff_text if diff_text else 'No differences found.'
        except Exception as e:
            diffs[r] = f"Error comparing config on device: {e}"

    return diffs
