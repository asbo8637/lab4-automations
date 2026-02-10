from flask import Flask, request
from getconfig import fetch_all_configs, load_json
import diffconfig as dc
import ospfconfig as osp
from validateIPv4 import validate_ipv4_list
from prettytable import PrettyTable

app = Flask(__name__)


@app.route("/")
def hello_world():
    return """
        <a href="/get-config">Get Config</a> <br>
        <a href="/ospf-config">OSPF config</a> <br>
        <a href="/diff-config">Diff config</a>
    """


@app.route("/get-config")
def get_config():
    saved_files = fetch_all_configs()

    files_html = "<ul>"
    for filename in saved_files:
        files_html += f"<li>{filename}</li>"
    files_html += "</ul>"

    return f"<h2>Get Config</h2><p>Saved files:</p>{files_html}"



def prettify(routers):
    table = PrettyTable()
    table.field_names = ["Router", "Interface", "IP Addresses"]
    for r in routers:
        ips = osp.fetch_interfaces(r)
        if isinstance(ips, dict) and "error" in ips:
            table.add_row([r["name"], "ERROR", ips["error"]])
            continue
        for interface, data in ips.items():
            addrs = ", ".join(data.get("ipv4", {}).keys()) if data.get("ipv4") else ""
            table.add_row([r["name"], interface, addrs])

    return table.get_string()


@app.route("/ospf-config", methods=["GET", "POST"])
def ospf_config():
    if request.method == "GET":
        return """
        <h2>OSPF Configuration Input</h2>
        
        <form method="post">
        <h3>Router R1</h3>
        Username: <input name="R1_user"><br>
        Password: <input name="R1_pass" type="password"><br>
        OSPF Process ID: <input name="R1_process" value="1"><br>
        Area: <input name="R1_area" value="0"><br>
        Loopback IP: <input name="R1_loopback"><br>
        <input type="submit" name="submit_R1" value="Save R1">
        </form>

        <form method="post">
        <h3>Router R2</h3>
        Username: <input name="R2_user"><br>
        Password: <input name="R2_pass" type="password"><br>
        OSPF Process ID: <input name="R2_process" value="1"><br>
        Area: <input name="R2_area" value="0"><br>
        Loopback IP: <input name="R2_loopback"><br>
        <input type="submit" name="submit_R2" value="Save R2">
        </form>

        <form method="post">
        <h3>Router R3</h3>
        Username: <input name="R3_user"><br>
        Password: <input name="R3_pass" type="password"><br>
        OSPF Process ID: <input name="R3_process" value="1"><br>
        Area: <input name="R3_area" value="0"><br>
        Loopback IP: <input name="R3_loopback"><br>
        <input type="submit" name="submit_R3" value="Save R3">
        </form>

        <form method="post">
        <h3>Router R4</h3>
        Username: <input name="R4_user"><br>
        Password: <input name="R4_pass" type="password"><br>
        OSPF Process ID: <input name="R4_process" value="1"><br>
        Area: <input name="R4_area" value="0"><br>
        Loopback IP: <input name="R4_loopback"><br>
        <input type="submit" name="submit_R4" value="Save R4">
        </form>
        """
    
    ssh = {}
    try:
        ssh = load_json()
    except Exception:
        ssh = {}

    # Determine which router was submitted
    submitted_router = None
    for name in ["R1", "R2", "R3", "R4"]:
        if f"submit_{name}" in request.form:
            submitted_router = name
            break

    if not submitted_router:
        return "<h2>Error</h2><p>No router selected.</p>"

    try:
        idx = ["R1", "R2", "R3", "R4"].index(submitted_router)
        host = ssh.get("IPS", [])[idx]
    except Exception:
        host = ""

    username = request.form.get(f"{submitted_router}_user", "").strip()
    password = request.form.get(f"{submitted_router}_pass", "").strip()

    # Skip if username or password is empty
    if not username or not password:
        return f"<h2>Error</h2><p>{submitted_router} needs both username and password.</p><p><a href='/ospf-config'>Go back</a></p>"

    router_name = f"{submitted_router}Boneh"
    r = {
        "name": router_name,
        "host": host,
        "username": username,
        "password": password,
        "process_id": int(request.form.get(f"{submitted_router}_process", "1") or 1),
        "area": int(request.form.get(f"{submitted_router}_area", "0") or 0),
        "loopback": request.form.get(f"{submitted_router}_loopback", "").strip(),
    }
    
    osp.save_router(r)

    # Validate and show results for this router
    vhtml = f"<h2>Saved {router_name}</h2>"
    vhtml += "<h3>Validation</h3><ul>"
    host_ok = validate_ipv4_list(r["host"]) if r["host"] else False
    loop_ok = validate_ipv4_list(r["loopback"]) if r.get("loopback") else False

    loop_format_ok = False
    if r.get("loopback"):
        loop_format_ok = validate_ipv4_list(r.get("loopback"))

    vhtml += f"<li>{r['name']} host {r['host']} reachable: {host_ok}; loopback {r.get('loopback','')} reachable: {loop_ok}; loopback format valid: {loop_format_ok}</li>"
    vhtml += "</ul>"

    # Show interfaces for this router
    table_str = prettify([r])

    return f"{vhtml}<h3>Interfaces</h3><pre>{table_str}</pre><p><a href='/ospf-config'>Configure another router</a> | <a href='/apply-ospf'>Apply OSPF to all routers</a></p>"


@app.route("/apply-ospf")
def apply_ospf():
    osp.init_db()
    cfg_results = osp.configure_ospf()
    ping_results = osp.ping_loopbacks()

    out = "<h2>OSPF Apply Results</h2>"
    out += "<h3>Configuration Results</h3><ul>"
    for r, res in cfg_results.items():
        if res.get("status") == "ok":
            out += f"<li>{r}: OK</li>"
        else:
            out += f"<li>{r}: ERROR - {res.get('error')}</li>"
    out += "</ul>"

    out += "<h3>Ping Loopbacks from R1</h3>"
    if isinstance(ping_results, dict):
        out += "<pre>"
        for t, val in ping_results.items():
            out += f"{t}:\n{val}\n\n"
        out += "</pre>"
    else:
        out += f"<p>{ping_results}</p>"

    return out


@app.route("/diff-config")
def diff_config():
    diffs = dc.diff_configs()
    out = "<h2>Config Differences</h2>"
    for r, diff in diffs.items():
        out += f"<h3>{r}</h3><pre>{diff}</pre>"
    return out