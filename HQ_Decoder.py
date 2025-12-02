"""
hq_full_decoder_with_opencellid.py

Comprehensive HQ protocol decoder + LBS->GPS using OpenCellID (user-provided key)
and Mozilla Location Service as fallback.

Usage:
    from hq_full_decoder_with_opencellid import HQFullDecoder
    decoder = HQFullDecoder(lbs_providers={"opencellid": {"key": "YOUR_KEY"},
                                           "mozilla": {"key":"test"}})
    parsed = decoder.decode(raw_packet)
    print(decoder.to_json(parsed))
"""

from __future__ import annotations
import json
import os
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
    """
    Parse hhmmss and ddmmyy into an ISO8601 UTC datetime string.
    Returns like: '2025-06-16T00:02:54+00:00' or None if malformed.
    """
    if not hhmmss or len(hhmmss) < 6 or not ddmmyy or len(ddmmyy) < 6:
        return None
    try:
        hh = int(hhmmss[0:2])
        mm = int(hhmmss[2:4])
        ss = int(hhmmss[4:6])
        dd = int(ddmmyy[0:2])
        mo = int(ddmmyy[2:4])
        yy = int(ddmmyy[4:6])
        year = 2000 + yy
        dt = datetime(year, mo, dd, hh, mm, ss, tzinfo=timezone.utc)
        return dt.isoformat()
    except Exception:
        return None


def interpret_flags_basic(hex_flags: Optional[str]) -> Dict[str, Any]:
    """Minimal flags parsing — return raw, binary string and example bits."""
    if not hex_flags:
        return {"raw": None, "bits": None}
    try:
        s = str(hex_flags).lower().replace("0x", "")
        if len(s) % 2 != 0:
            s = "0" + s
        bin_str = bin(int(s, 16))[2:].zfill(len(s) * 4)
        # LSB-first convenience
        lsb_first = bin_str[::-1]
        return {"raw": hex_flags, "bits": bin_str, "lsb_first": lsb_first}
    except Exception:
        return {"raw": hex_flags, "bits": None}


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
    def resolve(self, mcc: int, mnc: int, lac: int, cid: int) -> Optional[Dict[str, Any]]:
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
            "HB": self._handle_hb,
            "UPLOAD": self._handle_upload,
            "SOS": self._handle_sos,
            "CONFIG": self._handle_config,
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
        out["protocol"] = protocol
        imei = parts[1] if len(parts) > 1 else None
        out["imei"] = imei
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
    def _handle_v1(self, parts: list) -> dict:
        """
        V1: GPS packet. Typical fields (comma separated):
        [0]=HQ, [1]=imei, [2]=V1, [3]=hhmmss, [4]=A/V, [5]=lat (DDMM.MMMM), [6]=N/S,
        [7]=lon (DDDMM.MMMM), [8]=E/W, [9]=speed, [10]=course, [11]=ddmmyy, [12]=statusHex,
        [13]=mcc, [14]=mnc, [15]=lac, [16]=cid, ...
        """
        if len(parts) < 11:
            raise ValueError("V1 packet too short")
        # safe unpacking; if some trailing fields missing they'll be None
        protocol = parts[0] if len(parts) > 0 else None
        imei = parts[1] if len(parts) > 1 else None
        pkt = parts[2] if len(parts) > 2 else None
        time_raw = parts[3] if len(parts) > 3 else None
        status = parts[4] if len(parts) > 4 else None
        lat_raw = parts[5] if len(parts) > 5 else None
        lat_dir = parts[6] if len(parts) > 6 else None
        lon_raw = parts[7] if len(parts) > 7 else None
        lon_dir = parts[8] if len(parts) > 8 else None
        speed_raw = parts[9] if len(parts) > 9 else None
        angle_raw = parts[10] if len(parts) > 10 else None
        date_raw = parts[11] if len(parts) > 11 else None
        flags_raw = parts[12] if len(parts) > 12 else None
        mcc_raw = parts[13] if len(parts) > 13 else None
        mnc_raw = parts[14] if len(parts) > 14 else None
        lac_raw = parts[15] if len(parts) > 15 else None
        cid_raw = parts[16] if len(parts) > 16 else None

        res: Dict[str, Any] = {"type": "V1", "protocol": protocol, "imei": imei}
        res["gps_valid"] = (status == "A")
        # timestamp: ISO8601 UTC string or None
        res["timestamp"] = format_time_date(time_raw, date_raw)
        # keep raw values
        res["time_raw"] = time_raw
        res["date_raw"] = date_raw
        res["status_raw"] = status
        res["speed_raw"] = speed_raw
        res["angle_raw"] = angle_raw
        # Convert speed from knots to km/h (1 knot = 1.852 km/h)
        speed_knots = self._safe_float(speed_raw) if speed_raw is not None else None
        res["speed_kph"] = round(speed_knots * 1.852, 2) if speed_knots is not None else None
        # put a fallback alias for frontend that may expect 'speed'
        res["speed"] = res["speed_kph"]
        res["course"] = self._safe_int(angle_raw) if angle_raw is not None else None
        res["angle"] = res["course"]
        res["flags_raw"] = flags_raw
        res["flags"] = interpret_flags_basic(flags_raw)
        res["mcc"] = self._safe_int(mcc_raw)
        res["mnc"] = self._safe_int(mnc_raw)
        res["lac"] = self._safe_int(lac_raw)
        res["cid"] = self._safe_int(cid_raw)

        if res["gps_valid"]:
            res["latitude"] = dm_to_dd(lat_raw, lat_dir)
            res["longitude"] = dm_to_dd(lon_raw, lon_dir)
            res["location_source"] = "GPS"
        else:
            # Attempt LBS resolution
            res["latitude"] = None
            res["longitude"] = None
            res["location_source"] = "LBS"
            if None not in (res["mcc"], res["mnc"], res["lac"], res["cid"]):
                loc = self.lbs.resolve(res["mcc"], res["mnc"], res["lac"], res["cid"])
                if loc:
                    res["latitude"] = loc.get("lat")
                    res["longitude"] = loc.get("lon")
                    res["location_resolved_via"] = loc.get("provider")
                    res["accuracy_m"] = loc.get("accuracy")
                else:
                    res["location_resolved_via"] = "none"
            else:
                res["location_resolved_via"] = "insufficient_lbs"
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
        res["alarm_info"] = interpret_flags_basic(alarm_raw)
        return res

    def _handle_hb(self, parts: list) -> dict:
        """
        HB: Heartbeat. Many formats exist; we attempt to detect voltage & signal.
        Typical: *HQ,imei,HB,hhmmss,A,voltage_mv,signal#
        """
        if len(parts) < 3:
            raise ValueError("HB too short")
        protocol = parts[0] if len(parts) > 0 else None
        imei = parts[1] if len(parts) > 1 else None
        pkt = parts[2] if len(parts) > 2 else None
        time_raw = parts[3] if len(parts) > 3 else None
        rest = parts[4:] if len(parts) > 4 else []
        voltage_raw = None
        signal_raw = None
        status = None
        if rest:
            # detect optional status char
            if len(rest[0]) == 1 and not rest[0].isdigit():
                status = rest[0]
                if len(rest) >= 3:
                    voltage_raw = rest[1]; signal_raw = rest[2]
                elif len(rest) >= 2:
                    voltage_raw = rest[1]
            else:
                voltage_raw = rest[0]
                if len(rest) >= 2:
                    signal_raw = rest[1]
        res = {"type": "HB", "protocol": protocol, "imei": imei}
        res["timestamp"] = format_time_date(time_raw, "000000") if time_raw else None
        res["status"] = status
        res["voltage_raw"] = voltage_raw
        res["signal_raw"] = signal_raw
        res["voltage_v"] = None
        # Interpret voltage: if >=1000 -> mV else ambiguous
        try:
            if voltage_raw is not None:
                v = float(voltage_raw)
                if v >= 1000:
                    res["voltage_v"] = round(v / 1000.0, 3)
                    res["voltage_interpretation"] = "mV->V"
                elif 0 <= v <= 100:
                    res["voltage_percent"] = round(v, 2)
                    res["voltage_interpretation"] = "percent_or_unknown"
                else:
                    res["voltage_v"] = round(v, 3)
                    res["voltage_interpretation"] = "raw_guess"
        except Exception:
            pass
        try:
            if signal_raw is not None:
                res["signal_strength"] = int(float(signal_raw))
        except Exception:
            pass
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
