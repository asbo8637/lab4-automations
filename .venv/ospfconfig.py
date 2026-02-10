import sqlite3
from pathlib import Path
import subprocess
from napalm import get_network_driver
from validateIPv4 import validate_ipv4_list

DB = Path("data.db")


def init_db():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS routers (
            name TEXT PRIMARY KEY,
            host TEXT,
            username TEXT,
            password TEXT,
            process_id INTEGER,
            area INTEGER,
            loopback TEXT
        )
        """
    )
    conn.commit()
    conn.close()



def get_routers_info():
    init_db()
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute("SELECT name, host, username, password, process_id, area, loopback FROM routers ORDER BY name")
    rows = cur.fetchall()
    conn.close()
    routers = []
    for r in rows:
        routers.append(
            {
                "name": r[0],
                "host": r[1],
                "username": r[2],
                "password": r[3],
                "process_id": r[4],
                "area": r[5],
                "loopback": r[6],
            }
        )
    return routers


def save_router(router):
    init_db()
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute(
        "REPLACE INTO routers (name, host, username, password, process_id, area, loopback) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            router["name"],
            router.get("host", ""),
            router.get("username", ""),
            router.get("password", ""),
            int(router.get("process_id") or 0),
            router.get("area", 0),
            router.get("loopback", ""),
        ),
    )
    conn.commit()
    conn.close()

def fetch_interfaces(router):
    """Fetch interface IPs for a router using napalm get_interfaces_ip()."""
    driver = get_network_driver("ios")
    device = {
        "hostname": router["host"],
        "username": router["username"],
        "password": router["password"],
    }
    try:
        dev = driver(**device)
        dev.open()
        ips = dev.get_interfaces_ip()
        dev.close()
        return ips
    except Exception as e:
        return {"error": str(e)}


def configure_ospf():
    """
    Read routers from DB and apply OSPF configuration using napalm.
    R2 and R4 get 'maximum-paths 2' for load balancing.
    """
    results = {}
    routers = get_routers_info()
    for r in routers:
        driver = get_network_driver("ios")
        device = {
            "hostname": r["host"],
            "username": r["username"],
            "password": r["password"],
        }
        try:
            dev = driver(**device)
            dev.open()

            cfg_lines = []
            if r.get("loopback"):
                cfg_lines.append(f"interface Loopback0")
                cfg_lines.append(f" ip address {r['loopback']} 255.255.255.255")
                cfg_lines.append(" exit")
            pid = int(r.get("process_id") or 1)
            cfg_lines.append(f"router ospf {pid}")
            if r["name"] in ("R2Boneh", "R4Boneh"):
                cfg_lines.append(" maximum-paths 2")

            config = "\n".join(cfg_lines)

            dev.load_merge_candidate(config=config)
            dev.commit_config()
            dev.close()
            results[r["name"]] = {"status": "ok", "config": config}
        except Exception as e:
            results[r["name"]] = {"status": "error", "error": str(e)}

    return results


def ping_loopbacks():
    routers = get_routers_info()
    r1 = next((r for r in routers if r["name"] == "R1Boneh"), None)
    if not r1:
        return {"error": "R1 not found in DB"}

    # collect loopbacks of routers

    driver = get_network_driver("ios")
    device = {"hostname": r1["host"], "username": r1["username"], "password": r1["password"]}
    try:
        dev = driver(**device)
        dev.open()
        outputs = {}
        for r in routers:
            t = r.get("loopback")
            if not t:
                continue
            if not validate_ipv4_list(t):
                outputs[t] = "Loopback IP is invalid."
                continue
            cmd = f"ping {t} repeat 2"
            try:
                ping_result = dev.cli([cmd])
                outputs[t] = ping_result.get(cmd, "")
            except Exception as e:
                outputs[t] = f"Error running ping: {str(e)}"
        dev.close()
        return outputs
    except Exception as e:
        return {"error": str(e)}
