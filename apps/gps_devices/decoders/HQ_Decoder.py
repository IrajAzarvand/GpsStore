"""
hq_full_decoder_with_opencellid.py

Comprehensive HQ protocol decoder + LBS->GPS using OpenCellID (user-provided key)
and Mozilla Location Service as fallback.

Usage:
    from HQ_Decoder import HQDecoder
    decoder = HQFullDecoder(lbs_providers={"opencellid": {"key": "YOUR_KEY"},
    "mozilla": {"key":"test"}})
    parsed = decoder.decode(raw_packet)
    print(decoder.to_json(parsed))
"""

from __future__ import annotations
import json
import os
import re
from typing import Optional, Dict, Any, Callable
from functools import lru_cache
from datetime import datetime, timezone

# network requests
try:
    import requests
except Exception:
    requests = None

# -----------------------
# OpenCellID API key loaded from environment variables
OPENCELLID_API_KEY = os.environ.get('OPENCELLID_API_KEY', 'pk.4dbbc49e1464ebf250731662ff85eb00')
# -----------------------


def dm_to_dd(value: Optional[str], direction: Optional[str]) -> Optional[float]:
    """Convert DDMM.MMMM (or DDDMM.MMMM) to decimal degrees. Return None if invalid."""
    if not value:
        return None
    try:
        v = float(value)
    except Exception:
        return None
    
    # Auto-detect format: if value >= 10000, it's DDDMM.MMMM, else DDMM.MMMM
    if v >= 10000:
        # DDDMM.MMMM format (longitude with 3-digit degrees)
        degrees = int(v // 100)
        minutes = v - degrees * 100
    else:
        # DDMM.MMMM format (latitude with 2-digit degrees)
        degrees = int(v // 100)
        minutes = v - degrees * 100
    
    decimal = degrees + (minutes / 60.0)
    if direction and isinstance(direction, str) and direction.upper() in ("S", "W"):
        decimal = -decimal
    # round to 7 decimals for better precision (~1cm accuracy)
    return round(decimal, 7)


def format_time_date(hhmmss: Optional[str], ddmmyy: Optional[str]) -> Optional[str]:
    if not hhmmss or len(hhmmss) < 6 or not ddmmyy or len(ddmmyy) < 6:
        return None
    try:
        hh = int(hhmmss[0:2])
        mm = int(hhmmss[2:4])
        ss = int(hhmmss[4:6])
        dd = int(ddmmyy[0:2])
        mo = int(ddmmyy[2:4])
        yy = int(ddmmyy[4:6])
        # Year logic: 80–99 → 1980–1999, 00–79 → 2000–2079
        if yy >= 80:
            year = 1900 + yy
        else:
            year = 2000 + yy
        dt = datetime(year, mo, dd, hh, mm, ss, tzinfo=timezone.utc)
        return dt.isoformat()
    except Exception:
        return None



def parse_flags_from_hex(hex_str, byteorder='little'):
    """
    Parse a hex string like 'fbfffbff' into 32 boolean bits.
    byteorder: 'little' or 'big' — default 'little' (common in many text trackers).
    Returns integer value and dict bits.
    """
    try:
        # Clean: remove non-hex
        cleaned = re.sub(r'[^0-9a-fA-F]', '', str(hex_str))
        # ensure even-length
        if len(cleaned) % 2 == 1:
            cleaned = '0' + cleaned
        b = bytes.fromhex(cleaned)
        # pad or trim to 4 bytes
        if len(b) < 4:
            b = b.ljust(4, b'\x00')
        elif len(b) > 4:
            b = b[:4]
        if byteorder == 'little':
            value = int.from_bytes(b, 'little')
        else:
            value = int.from_bytes(b, 'big')
        bits = {}
        for bit in range(32):
            bit_val = (value >> bit) & 1
            meta = FLAGS_MAP.get(bit, {"name": f"bit_{bit}", "desc":"Unknown/reserved", "notes":""})
            bits[bit] = {
                "bit": bit,
                "value": bool(bit_val),
                "name": meta.get("name"),
                "desc": meta.get("desc"),
                "notes": meta.get("notes", "")
            }
        return value, bits
    except Exception:
        # fallback: all zero
        bits = {bit: {"bit": bit, "value": False, "name": FLAGS_MAP.get(bit, {}).get("name", f"bit_{bit}"),
                      "desc": FLAGS_MAP.get(bit, {}).get("desc",""), "notes":""} for bit in range(32)}
        return 0, bits


# ---------- Flags map (bits 0..31) ----------
# This is a comprehensive, editable mapping of bit index -> metadata.
# If you get an official spec, replace names/descriptions accordingly.
FLAGS_MAP = {
    0:  {"name":"acc_on", "desc":"ACC (ignition) ON", "notes":"1=ignition on (engine running/ignition)"},
    1:  {"name":"gps_fixed", "desc":"GPS position valid/fix", "notes":"1=GPS fix (valid lat/lon)"},
    2:  {"name":"charging", "desc":"External power / charging", "notes":"1=charging/connected to external power"},
    3:  {"name":"sos", "desc":"SOS / emergency alarm", "notes":"panic button triggered"},
    4:  {"name":"overspeed", "desc":"Overspeed alarm", "notes":"1=overspeed condition"},
    5:  {"name":"gps_tamper", "desc":"GPS antenna tamper/cut", "notes":"antenna fault / cut"},
    6:  {"name":"low_battery", "desc":"Low internal battery", "notes":"device battery low"},
    7:  {"name":"power_cut", "desc":"External power cut / ignition off", "notes":"external power removed"},
    8:  {"name":"tamper", "desc":"Device tamper", "notes":"case opened / tamper sensor"},
    9:  {"name":"geofence", "desc":"Geofence breach", "notes":"in/out geofence event"},
    10: {"name":"input1", "desc":"Digital input 1", "notes":"usage-defined (e.g. door, sensor)"},
    11: {"name":"input2", "desc":"Digital input 2", "notes":"usage-defined"},
    12: {"name":"relay_on", "desc":"Relay/immobilizer active", "notes":"cut-off / relay engaged"},
    13: {"name":"gps_disabled", "desc":"GPS disabled/standby", "notes":"GPS module disabled or sleep"},
    14: {"name":"acc_alarm", "desc":"ACC tamper/rapid on-off", "notes":"fluctuating ignition event"},
    15: {"name":"pir_alarm", "desc":"Motion/PIR alarm", "notes":"internal motion sensor triggered"},
    16: {"name":"seatbelt", "desc":"Seatbelt status", "notes":"1=unfastened (vendor-specific)"},
    17: {"name":"backup_batt_low", "desc":"Backup battery low", "notes":""},
    18: {"name":"oil_cut", "desc":"Oil/electronic fuel cut", "notes":"immobilizer action or fuel cut detected"},
    19: {"name":"door_open", "desc":"Door open", "notes":"one of doors is open"},
    20: {"name":"tilt_alarm", "desc":"Tilt/rollover alarm", "notes":"possible tilt/rollover"},
    21: {"name":"shock_alarm", "desc":"Vibration/shock alarm", "notes":"impact detected"},
    22: {"name":"temperature_alarm", "desc":"Temperature sensor alarm", "notes":""},
    23: {"name":"reserved_23", "desc":"Reserved / vendor specific", "notes":""},
    24: {"name":"reserved_24", "desc":"Reserved / vendor specific", "notes":""},
    25: {"name":"reserved_25", "desc":"Reserved / vendor specific", "notes":""},
    26: {"name":"reserved_26", "desc":"Reserved / vendor specific", "notes":""},
    27: {"name":"reserved_27", "desc":"Reserved / vendor specific", "notes":""},
    28: {"name":"reserved_28", "desc":"Reserved / vendor specific", "notes":""},
    29: {"name":"reserved_29", "desc":"Reserved / vendor specific", "notes":""},
    30: {"name":"reserved_30", "desc":"Reserved / vendor specific", "notes":""},
    31: {"name":"reserved_31", "desc":"Reserved / vendor specific", "notes":""},
}

# -----------------------
# LBS resolver class: tries opencellid then mozilla then fallback
# -----------------------
class LBSResolver:
    def __init__(self, providers: Optional[Dict[str, Dict[str, Any]]] = None):
        """
        providers example:
          {"opencellid": {"key": "YOUR_KEY"},
           "mozilla": {"key": "test"}}
        If providers is None, OpenCellID is used with OPENCELLID_API_KEY variable.
        """
        if providers is None:
            providers = {}
        # ensure opencellid key present if not provided
        if "opencellid" not in providers and OPENCELLID_API_KEY:
            providers["opencellid"] = {"key": OPENCELLID_API_KEY}
        if "mozilla" not in providers:
            providers["mozilla"] = {"key": "test"}  # test key; limited
        self.providers = providers

    @lru_cache(maxsize=4096)
    def resolve(self, lac: int, cid: int, mcc: int = 432, mnc: int = 1) -> Optional[Dict[str, Any]]:
        """
        Attempt providers in order: opencellid -> mozilla -> fallback.
        Uses Iran's default MCC=432, MNC=1 if not provided.
        Returns dict {lat, lon, accuracy, provider} or None.
        """
        # try OpenCellID if configured
        if "opencellid" in self.providers and requests is not None:
            cfg = self.providers["opencellid"]
            key = cfg.get("key")
            if key:
                try:
                    loc = self._resolve_opencellid(key, mcc, mnc, lac, cid)
                    if loc:
                        loc["provider"] = "opencellid"
                        return loc
                except Exception:
                    pass

        # try Mozilla Location Service
        if "mozilla" in self.providers and requests is not None:
            cfg = self.providers["mozilla"]
            key = cfg.get("key", "test")
            try:
                loc = self._resolve_mozilla(key, mcc, mnc, lac, cid)
                if loc:
                    loc["provider"] = "mozilla"
                    return loc
            except Exception:
                pass

        # fallback
        loc = self._fallback_pseudo(mcc, mnc, lac, cid)
        loc["provider"] = "pseudo"
        return loc
    
    
        """
        Attempt providers in order: opencellid -> mozilla -> fallback.
        Returns dict {lat, lon, accuracy, provider} or None.
        """
        # try OpenCellID if configured
        if "opencellid" in self.providers and requests is not None:
            cfg = self.providers["opencellid"]
            key = cfg.get("key")
            if key:
                try:
                    loc = self._resolve_opencellid(key, mcc, mnc, lac, cid)
                    if loc:
                        loc["provider"] = "opencellid"
                        return loc
                except Exception:
                    pass

        # try Mozilla Location Service
        if "mozilla" in self.providers and requests is not None:
            cfg = self.providers["mozilla"]
            key = cfg.get("key", "test")
            try:
                loc = self._resolve_mozilla(key, mcc, mnc, lac, cid)
                if loc:
                    loc["provider"] = "mozilla"
                    return loc
            except Exception:
                pass

        # fallback deterministic pseudo-resolver (not accurate - for dev/testing)
        loc = self._fallback_pseudo(mcc, mnc, lac, cid)
        loc["provider"] = "pseudo"
        return loc

    def _resolve_opencellid(self, api_key: str, mcc: int, mnc: int, lac: int, cid: int) -> Optional[Dict[str, Any]]:
        """
        Query OpenCellID cell endpoint.
        We'll try several common URL patterns conservatively.
        """
        if requests is None:
            return None
        urls = [
            f"https://opencellid.org/cell/get?mcc={mcc}&mnc={mnc}&lac={lac}&cellid={cid}&fmt=json&key={api_key}",
            f"https://www.opencellid.org/cell/get?mcc={mcc}&mnc={mnc}&lac={lac}&cellid={cid}&fmt=json&key={api_key}",
            f"https://opencellid.org/cell/get?mcc={mcc}&mnc={mnc}&cellid={cid}&lac={lac}&fmt=json&key={api_key}"
        ]
        for url in urls:
            try:
                r = requests.get(url, timeout=6)
                if r.status_code != 200:
                    continue
                j = r.json()
                if isinstance(j, dict):
                    lat = j.get("lat") or j.get("latitude") or (j.get("data") and j["data"].get("lat"))
                    lon = j.get("lon") or j.get("longitude") or (j.get("data") and j["data"].get("lon"))
                    acc = j.get("range") or j.get("accuracy") or None
                    if lat is not None and lon is not None:
                        return {"lat": float(lat), "lon": float(lon), "accuracy": acc}
            except Exception:
                continue
        return None

    def _resolve_mozilla(self, api_key: str, mcc: int, mnc: int, lac: int, cid: int) -> Optional[Dict[str, Any]]:
        """
        Query Mozilla Location Service:
          POST https://location.services.mozilla.com/v1/geolocate?key=API_KEY
        """
        if requests is None:
            return None
        url = f"https://location.services.mozilla.com/v1/geolocate?key={api_key}"
        payload = {"cellTowers": [{"mobileCountryCode": mcc, "mobileNetworkCode": mnc,
                                   "locationAreaCode": lac, "cellId": cid}]}
        try:
            r = requests.post(url, json=payload, timeout=6)
            if r.status_code != 200:
                return None
            j = r.json()
            if "location" in j and "lat" in j["location"] and "lng" in j["location"]:
                return {"lat": float(j["location"]["lat"]), "lon": float(j["location"]["lng"]), "accuracy": j.get("accuracy")}
        except Exception:
            return None
        return None

    @staticmethod
    def _fallback_pseudo(mcc: int, mnc: int, lac: int, cid: int) -> Dict[str, float]:
        """
        Deterministic pseudo resolver for offline testing (not accurate).
        """
        seed = (abs(int(mcc)) * 100000000) + (abs(int(mnc)) * 1000000) + (abs(int(lac)) * 1000) + abs(int(cid))
        lat = 20.0 + ((seed % 1000000) / 1000000.0) * 20.0
        lon = 40.0 + ((seed % 1000000) / 1000000.0) * 20.0
        return {"lat": round(lat, 6), "lon": round(lon, 6), "accuracy": None}


# -----------------------
# HQFullDecoder (comprehensive)
# -----------------------
class HQFullDecoder:
    def __init__(self, lbs_providers: Optional[Dict[str, Dict[str, Any]]] = None):
        """
        Create decoder. Pass lbs_providers to configure which LBS services to use.
        Example:
            decoder = HQFullDecoder(lbs_providers={
                "opencellid":{"key":"pk.4db..."},
                "mozilla":{"key":"test"}
            })
        """
        self.lbs = LBSResolver(lbs_providers)
        # handlers map
        self.packet_handlers: Dict[str, Callable[[list], dict]] = {
            "V1": self._handle_v1,
            "V0": self._handle_v0,
            "V2": self._handle_v2,
            "V3": self._handle_v3,
            "UPLOAD": self._handle_upload,
            "CONFIG": self._handle_config,
            # Special cases handled in decode()
        }

    def decode(self, raw_packet: str) -> Dict[str, Any]:
        """Top-level decode: returns detailed dict; never interprets MCC/MNC as voltage/temp."""
        out = {"raw": raw_packet}
        if not raw_packet or not raw_packet.strip():
            out.update({"error": "empty_packet"})
            return out
        working = raw_packet.strip()
        # remove leading * and trailing # if present
        if working.startswith("*"):
            working = working[1:]
        if working.endswith("#"):
            working = working[:-1]
        parts = working.split(",")
        if len(parts) < 2:
            out.update({"error": "malformed_packet", "parts": parts})
            return out

        protocol = parts[0]
        imei = parts[1] if len(parts) > 1 else None
        out["protocol"] = protocol
        out["imei"] = imei

        # 🔹 Special case: Heartbeat formats
        if working == "HTBT" or (len(parts) >= 3 and parts[2] == "XT"):
            return self._handle_heartbeat(parts)

        # Normal packet type (V1, V0, etc.)
        pkt_type = parts[2] if len(parts) > 2 else None
        out["type_raw"] = pkt_type
        handler = self.packet_handlers.get(pkt_type)
        if handler:
            try:
                body = handler(parts)
                body.setdefault("raw", raw_packet)
                body.setdefault("protocol", protocol)
                body.setdefault("imei", imei)
                return body
            except Exception as e:
                return {"error": "handler_exception", "exception": str(e), "raw": raw_packet, "type_tried": pkt_type}
        else:
            return {"type": "unknown", "raw": raw_packet, "parts": parts}
    
    
    # ---------- Handlers ----------
    def _handle_heartbeat(self, parts: list) -> dict:
        """Handle heartbeat packets: HTBT or XT."""
        protocol = parts[0] if len(parts) > 0 else None
        imei = parts[1] if len(parts) > 1 else None
        return {
            "type": "HEARTBEAT",
            "protocol": protocol,
            "imei": imei,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "note": "Device is online"
        }

    def _handle_v1(self, parts: list) -> dict:
        if len(parts) < 12:
            raise ValueError("V1 packet too short")
        protocol = parts[0]
        imei = parts[1]
        time_raw = parts[3]
        status = parts[4]
        lat_raw = parts[5]
        lat_dir = parts[6]
        lon_raw = parts[7]
        lon_dir = parts[8]
        speed_raw = parts[9]
        angle_raw = parts[10]
        date_raw = parts[11]
        flags_raw = parts[12] if len(parts) > 12 else None

        res = {
            "type": "V1",
            "protocol": protocol,
            "imei": imei,
            "gps_valid": (status == "A"),
            "timestamp": format_time_date(time_raw, date_raw),
            "time_raw": time_raw,
            "date_raw": date_raw,
            "status_raw": status,
            "speed_raw": speed_raw,
            "angle_raw": angle_raw,
        }

        # Speed: convert knots to km/h
        speed_knots = self._safe_float(speed_raw)
        res["speed_kph"] = round(speed_knots * 1.852, 2) if speed_knots is not None else None
        res["speed"] = res["speed_kph"]
        res["course"] = self._safe_int(angle_raw)
        res["angle"] = res["course"]

        # Flags
        if flags_raw:
            flags_value, flags_bits = parse_flags_from_hex(flags_raw, byteorder='little')
            res["flags_value"] = flags_value
            res["flags"] = flags_bits
            # Extract ACC and SOS from flags
            res["acc_on"] = flags_bits.get(1, {}).get("value", False)  # Bit 1 = ACC
            res["sos_active"] = flags_bits.get(3, {}).get("value", False)  # Bit 3 = SOS
            if res["sos_active"]:
                res["alarm_type"] = "sos"
        else:
            res["flags_value"] = 0
            res["flags"] = {bit: {"bit": bit, "value": False, **FLAGS_MAP.get(bit, {"name": f"bit_{bit}", "desc": "", "notes": ""})}
                            for bit in range(32)}
            res["acc_on"] = None
            res["sos_active"] = False

        # Coordinates
        if res["gps_valid"]:
            res["latitude"] = dm_to_dd(lat_raw, lat_dir)
            res["longitude"] = dm_to_dd(lon_raw, lon_dir)
            res["location_source"] = "GPS"
        else:
            res["latitude"] = None
            res["longitude"] = None
            res["location_source"] = "LBS"

        # Parse extra fields: voltage, signal, LAC, CID (if present)
        res["lac"] = None
        res["cid"] = None
        res["voltage_mv"] = None
        res["voltage_v"] = None
        res["gsm_signal"] = None

        if len(parts) >= 17:
            # Check if parts[13] to [16] are numeric and plausible
            v_mv = self._safe_int(parts[13])
            sig = self._safe_int(parts[14])
            lac = self._safe_int(parts[15])
            cid = self._safe_int(parts[16])
            if v_mv is not None and sig is not None and lac is not None and cid is not None:
                res["voltage_mv"] = v_mv
                res["voltage_v"] = round(v_mv / 1000.0, 3)
                res["gsm_signal"] = sig
                res["lac"] = lac
                res["cid"] = cid

        # LBS fallback if no GPS
        if not res["gps_valid"] and res["lac"] is not None and res["cid"] is not None:
            loc = self.lbs.resolve(res["lac"], res["cid"])  # Note: MCC/MNC are now optional in LBSResolver
            if loc:
                res["latitude"] = loc.get("lat")
                res["longitude"] = loc.get("lon")
                res["location_resolved_via"] = loc.get("provider")
                res["accuracy_m"] = loc.get("accuracy")
            else:
                res["location_resolved_via"] = "none"

        return res



    def _handle_v0(self, parts: list) -> dict:
        """V0: LBS-only packet. Resolve to coords if possible."""
        if len(parts) < 9:
            raise ValueError("V0 too short")
        protocol = parts[0] if len(parts) > 0 else None
        imei = parts[1] if len(parts) > 1 else None
        pkt = parts[2] if len(parts) > 2 else None
        time_raw = parts[3] if len(parts) > 3 else None
        date_raw = parts[4] if len(parts) > 4 else None
        mcc_raw = parts[5] if len(parts) > 5 else None
        mnc_raw = parts[6] if len(parts) > 6 else None
        lac_raw = parts[7] if len(parts) > 7 else None
        cid_raw = parts[8] if len(parts) > 8 else None

        res = {"type": "V0", "protocol": protocol, "imei": imei}
        res["gps_valid"] = False
        res["timestamp"] = format_time_date(time_raw, date_raw)
        res["mcc"] = self._safe_int(mcc_raw)
        res["mnc"] = self._safe_int(mnc_raw)
        res["lac"] = self._safe_int(lac_raw)
        res["cid"] = self._safe_int(cid_raw)
        # resolve
        if None not in (res["mcc"], res["mnc"], res["lac"], res["cid"]):
            loc = self.lbs.resolve(res["mcc"], res["mnc"], res["lac"], res["cid"])
            if loc:
                res["latitude"] = loc.get("lat")
                res["longitude"] = loc.get("lon")
                res["location_resolved_via"] = loc.get("provider")
                res["accuracy_m"] = loc.get("accuracy")
            else:
                res["latitude"] = None
                res["longitude"] = None
                res["location_resolved_via"] = "none"
        else:
            res["latitude"] = None
            res["longitude"] = None
            res["location_resolved_via"] = "insufficient_lbs"
        return res

    def _handle_v2(self, parts: list) -> dict:
        """V2: alarm/status. Return alarm_info from flags if possible."""
        if len(parts) < 7:
            raise ValueError("V2 too short")
        protocol = parts[0] if len(parts) > 0 else None
        imei = parts[1] if len(parts) > 1 else None
        pkt = parts[2] if len(parts) > 2 else None
        time_raw = parts[3] if len(parts) > 3 else None
        status = parts[4] if len(parts) > 4 else None
        alarm_raw = parts[5] if len(parts) > 5 else None
        date_raw = parts[6] if len(parts) > 6 else None
        res = {"type": "V2", "protocol": protocol, "imei": imei}
        res["timestamp"] = format_time_date(time_raw, date_raw)
        res["status"] = status
        res["alarm_raw"] = alarm_raw
        if alarm_raw:
            alarm_value, alarm_bits = parse_flags_from_hex(alarm_raw, byteorder='little')
            res["alarm_value"] = alarm_value
            res["alarm_info"] = alarm_bits
        else:
            res["alarm_value"] = 0
            res["alarm_info"] = {bit: {"bit": bit, "value": False, "name": FLAGS_MAP.get(bit, {}).get("name", f"bit_{bit}"),
                                       "desc": FLAGS_MAP.get(bit, {}).get("desc",""), "notes": ""} for bit in range(32)}
        return res
    
    def _handle_v3(self, parts: list) -> dict:
        """V3: LBS-only packet (rare, but documented)."""
        if len(parts) < 7:
            raise ValueError("V3 too short")
        protocol = parts[0]
        imei = parts[1]
        time_raw = parts[3]
        date_raw = parts[6]
        flags_raw = parts[7] if len(parts) > 7 else None

        res = {
            "type": "V3",
            "protocol": protocol,
            "imei": imei,
            "gps_valid": False,
            "timestamp": format_time_date(time_raw, date_raw),
            "location_source": "LBS",
            "latitude": None,
            "longitude": None,
        }

        # Try to parse LAC/CID from later fields if structure matches
        # (V3 format varies; safe fallback is to rely on server-side buffering)
        res["location_resolved_via"] = "unsupported_in_v3"
        return res
   
    

    def _handle_upload(self, parts: list) -> dict:
        """UPLOAD: multi-record. We'll try to parse embedded V1/V0/V2 entries."""
        protocol = parts[0] if len(parts) > 0 else None
        imei = parts[1] if len(parts) > 1 else None
        subs = parts[3:] if len(parts) > 3 else []
        parsed = []
        for sub in subs:
            # If sub contains ':' that means "V1:..." style - convert to commas then decode
            if ":" in sub:
                tail = sub.replace(":", ",")
                pseudo = ",".join([protocol, imei, tail])
                try:
                    parsed.append(self.decode(pseudo + "#"))
                except Exception:
                    parsed.append({"raw_sub": sub})
            else:
                # try to detect starting token
                if isinstance(sub, str) and (sub.startswith("V1") or sub.startswith("V0") or sub.startswith("V2") or sub.startswith("HB")):
                    try:
                        parsed.append(self.decode(",".join([protocol, imei, sub]) + "#"))
                    except Exception:
                        parsed.append({"raw_sub": sub})
                else:
                    parsed.append({"raw_sub": sub})
        return {"type": "UPLOAD", "protocol": protocol, "imei": imei, "records": parsed}

    def _handle_sos(self, parts: list) -> dict:
        """Try V1 parsing and mark as SOS alarm if structure similar; else raw."""
        try:
            v1 = self._handle_v1(parts)
            v1["type"] = "SOS"
            v1["alarm"] = "SOS"
            return v1
        except Exception:
            return {"type": "SOS", "raw_parts": parts}

    def _handle_config(self, parts: list) -> dict:
        """CONFIG reply handling - look for OK/ERR tokens."""
        protocol = parts[0] if len(parts) > 0 else None
        imei = parts[1] if len(parts) > 1 else None
        pkt = parts[2] if len(parts) > 2 else None
        payload = parts[3:] if len(parts) > 3 else []
        res = {"type": "CONFIG", "protocol": protocol, "imei": imei, "payload": payload}
        if any(p.lower() in ("ok", "ack", "success") for p in payload if isinstance(p, str)):
            res["status"] = "ack"
        elif any(p.lower() in ("err", "error", "nok") for p in payload if isinstance(p, str)):
            res["status"] = "error"
        return res

    # ---------- Utilities ----------
    @staticmethod
    def _safe_int(v) -> Optional[int]:
        try:
            if v is None:
                return None
            return int(float(str(v)))
        except Exception:
            return None

    @staticmethod
    def _safe_float(v) -> Optional[float]:
        try:
            if v is None:
                return None
            return float(str(v))
        except Exception:
            return None

    def to_json(self, obj: Dict[str, Any], ensure_ascii: bool = False) -> str:
        # Custom serializer for datetime objects if any slipped in
        def default(o):
            if isinstance(o, datetime):
                return o.astimezone(timezone.utc).isoformat()
            return str(o)
        return json.dumps(obj, indent=2, ensure_ascii=ensure_ascii, default=default)

# End of module
