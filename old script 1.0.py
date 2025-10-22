import csv
import os
import ipaddress
from typing import Iterable
from tempfile import NamedTemporaryFile

in_path = "detailed_application_dependency_data.csv"
cols = ("src_group", "dest_group")
needle = "Wave4"
case_sensitive = True  # set to False for case-insensitive match

tmp = NamedTemporaryFile("w", newline="", delete=False, encoding="utf-8")

with open(in_path, newline="", encoding="utf-8") as src, tmp as dst:
    reader = csv.DictReader(src)

    # Ensure required columns exist
    missing = [c for c in cols if c not in reader.fieldnames]
    if missing:
        raise ValueError(f"Missing columns: {', '.join(missing)}")

    writer = csv.DictWriter(dst, fieldnames=reader.fieldnames)
    writer.writeheader()

    if case_sensitive:
        def match(row):
            return any(needle in (row[c] or "") for c in cols)
    else:
        low_needle = needle.lower()
        def match(row):
            return any(low_needle in (row[c] or "").lower() for c in cols)

    for row in reader:
        if match(row):
            writer.writerow(row)

os.replace(tmp.name, in_path)

# If your data is {service -> {IPs}} but your query is “given an IP, what’s the service?”, you’d have to scan all services ⇒ O(S) checks per lookup.
# Inverting to {ip -> service} makes the query O(1).

servizio_to_ips = {
 'Azure Migrate': ['10.11.12.13', '10.11.12.13', '10.11.12.13',],
 'Flexera': ['10.11.12.13', '10.11.12.13'],
 'KMS': ['10.11.12.13', '10.11.12.13'],
 'LoadBalancer': ['10.11.12.13'],
 'Monitoring': ['10.11.12.13', '10.11.12.13', '10.11.12.13', '10.11.12.13'],
 'Proxy Germania': ['10.11.12.13'],
 'Proxy Italia': ['10.11.12.13'],
}

subnets = {
 'ALBA_AUT NET': ['10.11.12.13/16', '10.11.12.13/20'],
 'ALBA_DMZ EXT': ['10.11.12.13/24', '10.11.12.13/27',],
 'ALBA_DMZ INT': ['10.11.12.13/24', '10.11.12.13/25', '10.11.12.13/28', '10.11.12.13/24', '10.11.12.13/27',],
}


PORT_COMMENTS = {
    25: "SMTP",
    8080: "Proxy",
    10065: "Zscaler",
    383: "Rule OMI",
}

def port_matches(target: int, value) -> bool:
    #Return True if `value` (string like '25', '80,8080', '10000-10100') contains `target`.
    #Matches whole numbers (no false match for 125 when target is 25).
   
    s = str(value or "")
    # whole-number match
    if re.search(rf'(?<!\d){target}(?!\d)', s):
        return True
    # range match a-b
    for a, b in re.findall(r'(\d+)\s*-\s*(\d+)', s):
        lo, hi = int(a), int(b)
        if lo <= target <= hi:
            return True
    return False


def build_ip_to_service(service_map: dict[str, set[str] | list[str]]) -> dict[str, str]:
    # Flatten {service: {ip1, ip2}} into {ip: service} for O(1) lookups.
    index: dict[str, str] = {}
    for service, ips in service_map.items():
        for ip in ips:
            index[str(ip).strip()] = service
    return index

    # Convert {'cidr': 'location'} to a list of (IPv4Network, location),
    #Parse once, use many times. Converting strings → network objects is relatively expensive. Doing it up-front means later checks are fast and simple
    # sorted by descending prefix length (so longest-prefix match wins first).

def rearrange_subnets(subnets_by_loc: dict[str, Iterable[str]]):
    #Parse once, use many times. Converting strings → network objects is relatively expensive. Doing it up-front means later checks are fast and simple
    #Input: {'LocationA': ['10.0.0.0/24', ...], 'LocationB': ['10.1.0.0/16', ...]}
    #Output: [(IPv4Network('10.0.0.0/24'), 'LocationA'), (IPv4Network('10.1.0.0/16'), 'LocationB'), ...]
    
    compiled = []
    for loc, cidrs in subnets_by_loc.items():
        for cidr in cidrs:
            try:
                net = ipaddress.ip_network(str(cidr).strip(), strict=False)
                # strict=False lets you pass things like '10.0.0.1/24'
            except ValueError:
                continue  # or raise, if you prefer not to silently skip bad CIDRs

            compiled.append((net, loc))
    # sorted by descending prefix length (so longest-prefix match wins first, /32 before /31 ... before /16.)
    compiled.sort(key=lambda nl: nl[0].prefixlen, reverse=True)
    return compiled
def find_location(ip_str: str, rearranged_nets: list[tuple[ipaddress.IPv4Network, str]]) -> str | None:
    #Return the location for the first (most specific) subnet that contains ip_str, else None.
    ip_str = (ip_str or "").strip()
    if not ip_str:
        #Ensures ip_str is a string and trims spaces. If ip_str was None, it becomes "" (empty string).
        #So this condition is True when ip_str is "" (or became empty after .strip()), meaning “we don’t actually have an IP to parse”.
        # return None, We signal “no result / don’t set anything” to the caller.
        return None
    try:
        ip = ipaddress.IPv4Address(ip_str)
    except ValueError:
        return None  # invalid/not IPv4 → no change
    for net, loc in rearranged_nets:
        if ip in net:
            return loc
    return None

ip_index = build_ip_to_service(servizio_to_ips)

nets = rearrange_subnets(subnets)

# --- Normalizzazione dei valori per le location ---
LOC_NORMALIZATION = {
    "risc-unknown-internet": "Public",
    "risc-unknown-private": "Private",
}

# ------------------------------------------
# 3) Transform CSV and write to new "target"
# ------------------------------------------

tmp = NamedTemporaryFile("w", newline="", delete=False, encoding="utf-8")

with open(in_path, newline="", encoding="utf-8") as src, tmp as dst:
    reader = csv.DictReader(src)

    # Ensure required columns exist (src_addr/dest_addr may or may not be present;
    # if missing we’ll just write "unknown")
    # list(...) ensures we have a mutable list to modify (append to)
    fieldnames = list(reader.fieldnames or [])
    for col in ("src_service", "dest_service", "src_loc", "dest_loc", "COMMENTO"):
        if col not in fieldnames:
            fieldnames.append(col)

    writer = csv.DictWriter(dst, fieldnames=fieldnames)
    writer.writeheader()

    for row in reader:
        # --- Service by exact IP ---
        src_ip = (row.get("src_addr") or "").strip()
        dest_ip = (row.get("dest_addr") or "").strip()
        # For services, we always set (unknown if no match)
        row["src_service"] = ip_index.get(src_ip, "unknown")
        row["dest_service"] = ip_index.get(dest_ip, "unknown")

        # --- Location by subnet (only set if we find a match) ---
        src_loc = find_location(src_ip, nets)
        if src_loc is not None:
            row["src_loc"] = src_loc  # set only on success

        dest_loc = find_location(dest_ip, nets)
        if dest_loc is not None:
            row["dest_loc"] = dest_loc  # set only on success

        # --- Public and Private IPs ---
        for col in ("src_loc", "dest_loc"):
            current = (row.get(col) or "").strip()
            if current:
                mapped = LOC_NORMALIZATION.get(current.lower())
                if mapped is not None:
                    row[col] = mapped

        # --- COMMENTO logic ---
        comment = ""

        # Precedence: if at least one service is known, we skip due to shared services
        if (row.get("src_service") or "").strip().lower() != "unknown" or \
        (row.get("dest_service") or "").strip().lower() != "unknown":
            comment = "skip shared services"
        else:
            dp = row.get("dest_port")
            for port, label in PORT_COMMENTS.items():
                if port_matches(port, dp):
                    comment = label
                    break

        # Write only if we have something to say
        if comment:
            row["COMMENTO"] = comment

        writer.writerow(row)


out_path = "target4.csv"
os.replace(tmp.name, out_path)