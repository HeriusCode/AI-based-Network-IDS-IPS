"""OpenFlow 1.3 learning switch with a bounded Mininet IPS REST API.

The REST endpoint is intentionally bound to VM loopback.  The desktop UI reaches
it through the authenticated Mininet agent/SSH tunnel.  Enforcement is limited
to the Mininet 10.0.0.0/8 lab and every rule has a hard timeout.
"""

from __future__ import annotations

import ipaddress
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from http import HTTPStatus
from typing import Any

from os_ken.base import app_manager
from os_ken.controller import ofp_event
from os_ken.controller.handler import CONFIG_DISPATCHER, DEAD_DISPATCHER, MAIN_DISPATCHER, set_ev_cls
from os_ken.lib import hub
from os_ken.lib.packet import ethernet, ether_types, packet
from os_ken.ofproto import ofproto_v1_3


API_ADDRESS = ("127.0.0.1", 8080)
LAB_NETWORK = ipaddress.ip_network("10.0.0.0/8")
COOKIE_PREFIX = 0xA17A000000000000
COOKIE_MASK = 0xFFFFFFFFFFFFFFFF


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class IpsApi:
    """Small dependency-free WSGI application used by OS-Ken's server."""

    def __init__(self, controller: "IdsController") -> None:
        self.controller = controller

    def __call__(self, environ: dict[str, Any], start_response):
        method = str(environ.get("REQUEST_METHOD", "GET")).upper()
        path = str(environ.get("PATH_INFO", "/"))
        try:
            length = int(environ.get("CONTENT_LENGTH") or 0)
            raw = environ["wsgi.input"].read(length) if length else b""
            payload = json.loads(raw.decode("utf-8")) if raw else {}
            if not isinstance(payload, dict):
                raise ValueError("JSON body phải là object")
            status, result = self.controller.handle_api(method, path, payload)
        except (ValueError, json.JSONDecodeError) as error:
            status, result = 400, {"detail": str(error)}
        except Exception as error:  # Keep controller alive on malformed requests.
            self.controller.logger.exception("IPS API error")
            status, result = 500, {"detail": str(error)}
        body = json.dumps(result, ensure_ascii=False).encode("utf-8")
        reason = HTTPStatus(status).phrase if status in HTTPStatus._value2member_map_ else "Error"
        start_response(
            f"{status} {reason}",
            [("Content-Type", "application/json; charset=utf-8"), ("Content-Length", str(len(body)))],
        )
        return [body]


class IdsController(app_manager.OSKenApp):
    """Learning switch plus reversible IPS enforcement for the Mininet lab."""

    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.mac_to_port: dict[int, dict[str, int]] = {}
        self.datapaths: dict[int, Any] = {}
        self.rules: dict[str, dict[str, Any]] = {}
        self.audit: list[dict[str, Any]] = []
        self.enabled = False
        self._meter_sequence = 100
        self._api_server = None
        self._api_thread = hub.spawn(self._serve_api)
        self.logger.setLevel(logging.INFO)

    def _serve_api(self) -> None:
        self._api_server = hub.WSGIServer(API_ADDRESS, IpsApi(self))
        self.logger.info("IPS API listening on http://%s:%s", *API_ADDRESS)
        self._api_server.serve_forever()

    def _audit(self, event: str, **details: Any) -> None:
        self.audit.insert(0, {"timestamp": _utc_now(), "event": event, **details})
        del self.audit[200:]

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev) -> None:
        datapath = ev.msg.datapath
        self.datapaths[datapath.id] = datapath
        parser = datapath.ofproto_parser
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(datapath.ofproto.OFPP_CONTROLLER, datapath.ofproto.OFPCML_NO_BUFFER)]
        self._add_flow(datapath, 0, match, actions)
        self.logger.info("OVS connected: datapath=%s", datapath.id)

    @set_ev_cls(ofp_event.EventOFPStateChange, [MAIN_DISPATCHER, DEAD_DISPATCHER])
    def datapath_state_handler(self, ev) -> None:
        if ev.state == MAIN_DISPATCHER:
            self.datapaths[ev.datapath.id] = ev.datapath
        elif ev.state == DEAD_DISPATCHER:
            self.datapaths.pop(ev.datapath.id, None)
            self.logger.warning("OVS disconnected: datapath=%s", ev.datapath.id)

    def _add_flow(self, datapath, priority: int, match, actions, *, cookie: int = 0,
                  hard_timeout: int = 0, meter_id: int | None = None) -> None:
        parser = datapath.ofproto_parser
        instructions = []
        if meter_id is not None:
            instructions.append(parser.OFPInstructionMeter(meter_id))
        if actions:
            instructions.append(parser.OFPInstructionActions(datapath.ofproto.OFPIT_APPLY_ACTIONS, actions))
        mod = parser.OFPFlowMod(
            datapath=datapath, cookie=cookie, priority=priority, match=match,
            instructions=instructions, hard_timeout=hard_timeout,
            flags=datapath.ofproto.OFPFF_SEND_FLOW_REM if cookie else 0,
        )
        datapath.send_msg(mod)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev) -> None:
        msg = ev.msg
        datapath = msg.datapath
        self.datapaths[datapath.id] = datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match["in_port"]
        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)
        if eth is None or eth.ethertype == ether_types.ETH_TYPE_LLDP:
            return
        self.mac_to_port.setdefault(datapath.id, {})[eth.src] = in_port
        out_port = self.mac_to_port[datapath.id].get(eth.dst, ofproto.OFPP_FLOOD)
        actions = [parser.OFPActionOutput(out_port)]
        if out_port != ofproto.OFPP_FLOOD:
            match = parser.OFPMatch(in_port=in_port, eth_src=eth.src, eth_dst=eth.dst)
            self._add_flow(datapath, 1, match, actions)
        data = None if msg.buffer_id != ofproto.OFP_NO_BUFFER else msg.data
        datapath.send_msg(parser.OFPPacketOut(
            datapath=datapath, buffer_id=msg.buffer_id, in_port=in_port,
            actions=actions, data=data,
        ))

    @set_ev_cls(ofp_event.EventOFPFlowRemoved, MAIN_DISPATCHER)
    def flow_removed_handler(self, ev) -> None:
        cookie = int(ev.msg.cookie)
        for rule_id, rule in list(self.rules.items()):
            if int(rule["cookie"]) == cookie and rule.get("status") == "active":
                rule["status"] = "expired"
                rule["expired_at"] = _utc_now()
                self._delete_meter(rule)
                self._audit("rule_expired", rule_id=rule_id, action=rule["action"], source_ip=rule["source_ip"])

    @staticmethod
    def _lab_ip(value: Any, *, optional: bool = False) -> str | None:
        text = str(value or "").strip()
        if optional and text.lower() in {"", "any", "*"}:
            return None
        try:
            address = ipaddress.ip_address(text)
        except ValueError as error:
            raise ValueError(f"IP không hợp lệ: {text}") from error
        if address.version != 4 or address not in LAB_NETWORK:
            raise ValueError("IPS chỉ được phép áp dụng cho IP Mininet 10.0.0.0/8")
        return str(address)

    @staticmethod
    def _protocol(value: Any) -> str:
        protocol = str(value or "any").lower()
        if protocol not in {"any", "tcp", "udp", "icmp"}:
            raise ValueError("Giao thức phải là any/tcp/udp/icmp")
        return protocol

    def _build_match(self, datapath, rule: dict[str, Any]):
        fields: dict[str, Any] = {
            "eth_type": ether_types.ETH_TYPE_IP,
            "ipv4_src": rule["source_ip"],
        }
        if rule.get("destination_ip"):
            fields["ipv4_dst"] = rule["destination_ip"]
        protocol = rule["protocol"]
        if protocol == "tcp":
            fields["ip_proto"] = 6
            if rule.get("destination_port"):
                fields["tcp_dst"] = rule["destination_port"]
        elif protocol == "udp":
            fields["ip_proto"] = 17
            if rule.get("destination_port"):
                fields["udp_dst"] = rule["destination_port"]
        elif protocol == "icmp":
            fields["ip_proto"] = 1
        return datapath.ofproto_parser.OFPMatch(**fields)

    def _install_meter(self, datapath, meter_id: int, rate_kbps: int) -> None:
        ofproto, parser = datapath.ofproto, datapath.ofproto_parser
        band = parser.OFPMeterBandDrop(rate=rate_kbps, burst_size=max(1, rate_kbps // 10))
        datapath.send_msg(parser.OFPMeterMod(
            datapath=datapath, command=ofproto.OFPMC_ADD,
            flags=ofproto.OFPMF_KBPS | ofproto.OFPMF_BURST,
            meter_id=meter_id, bands=[band],
        ))

    def _delete_meter(self, rule: dict[str, Any]) -> None:
        meter_id = rule.get("meter_id")
        if not meter_id:
            return
        for datapath in self.datapaths.values():
            datapath.send_msg(datapath.ofproto_parser.OFPMeterMod(
                datapath=datapath, command=datapath.ofproto.OFPMC_DELETE,
                flags=0, meter_id=int(meter_id), bands=[],
            ))

    def _create_rule(self, payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        action = str(payload.get("action", "alert")).lower()
        if action not in {"alert", "block_ip", "block_flow", "rate_limit"}:
            raise ValueError("Hành động phải là alert/block_ip/block_flow/rate_limit")
        source_ip = self._lab_ip(payload.get("source_ip"))
        destination_ip = self._lab_ip(payload.get("destination_ip"), optional=True)
        protocol = self._protocol(payload.get("protocol"))
        port_value = payload.get("destination_port")
        destination_port = None if port_value in (None, "", "any", "*") else int(port_value)
        if destination_port is not None and not 1 <= destination_port <= 65535:
            raise ValueError("Cổng đích phải nằm trong 1..65535")
        if destination_port and protocol not in {"tcp", "udp"}:
            raise ValueError("Cổng đích chỉ dùng với TCP/UDP")
        if action == "block_ip":
            destination_ip = None
            protocol = "any"
            destination_port = None
        duration = int(payload.get("duration", 60))
        if not 5 <= duration <= 3600:
            raise ValueError("Thời hạn rule phải nằm trong 5..3600 giây")
        rate_kbps = int(payload.get("rate_kbps", 256))
        if action == "rate_limit" and not 64 <= rate_kbps <= 100000:
            raise ValueError("Rate limit phải nằm trong 64..100000 Kbps")
        if action != "alert" and not self.enabled:
            return 409, {"detail": "IPS đang tạm dừng; hãy kích hoạt trước khi áp dụng rule"}
        if action != "alert" and not self.datapaths:
            return 503, {"detail": "Chưa có Open vSwitch kết nối OS-Ken"}

        rule_id = uuid.uuid4().hex[:10].upper()
        cookie = COOKIE_PREFIX | (int(uuid.uuid4().hex[:8], 16) & 0xFFFFFFFF)
        now = time.time()
        rule: dict[str, Any] = {
            "id": rule_id, "action": action, "source_ip": source_ip,
            "destination_ip": destination_ip, "protocol": protocol,
            "destination_port": destination_port, "duration": duration,
            "rate_kbps": rate_kbps if action == "rate_limit" else None,
            "reason": str(payload.get("reason") or "Manual IPS policy")[:240],
            "origin": str(payload.get("origin") or "manual")[:32],
            "cookie": cookie, "status": "active" if action != "alert" else "alerted",
            "created_at": _utc_now(), "expires_at_epoch": now + duration,
            "priority": 31000 if action == "block_flow" else 30000,
            "meter_id": None,
        }
        if action != "alert":
            if action == "rate_limit":
                self._meter_sequence += 1
                rule["meter_id"] = self._meter_sequence
            for datapath in self.datapaths.values():
                match = self._build_match(datapath, rule)
                if action == "rate_limit":
                    self._install_meter(datapath, int(rule["meter_id"]), rate_kbps)
                    actions = [datapath.ofproto_parser.OFPActionOutput(datapath.ofproto.OFPP_NORMAL)]
                    self._add_flow(datapath, 30500, match, actions, cookie=cookie,
                                   hard_timeout=duration, meter_id=int(rule["meter_id"]))
                else:
                    self._add_flow(datapath, int(rule["priority"]), match, [],
                                   cookie=cookie, hard_timeout=duration)
            self.rules[rule_id] = rule
        self._audit("alert" if action == "alert" else "rule_created", rule_id=rule_id,
                    action=action, source_ip=source_ip, reason=rule["reason"], origin=rule["origin"])
        return 201, {"rule": self._public_rule(rule)}

    @staticmethod
    def _public_rule(rule: dict[str, Any]) -> dict[str, Any]:
        result = {key: value for key, value in rule.items() if key != "cookie"}
        result["remaining_seconds"] = max(0, int(float(rule.get("expires_at_epoch", 0)) - time.time()))
        return result

    def _delete_rule(self, rule_id: str) -> tuple[int, dict[str, Any]]:
        rule = self.rules.get(rule_id)
        if rule is None:
            return 404, {"detail": "Không tìm thấy IPS rule"}
        cookie = int(rule["cookie"])
        for datapath in self.datapaths.values():
            parser, ofproto = datapath.ofproto_parser, datapath.ofproto
            datapath.send_msg(parser.OFPFlowMod(
                datapath=datapath, cookie=cookie, cookie_mask=COOKIE_MASK,
                table_id=ofproto.OFPTT_ALL, command=ofproto.OFPFC_DELETE,
                out_port=ofproto.OFPP_ANY, out_group=ofproto.OFPG_ANY,
            ))
        self._delete_meter(rule)
        rule["status"] = "removed"
        rule["removed_at"] = _utc_now()
        self._audit("rule_removed", rule_id=rule_id, action=rule["action"], source_ip=rule["source_ip"])
        return 200, {"rule": self._public_rule(rule)}

    def handle_api(self, method: str, path: str, payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        if method == "GET" and path == "/ips/health":
            return 200, {
                "status": "ok", "enabled": self.enabled,
                "openflow_version": "1.3", "ovs_connected": bool(self.datapaths),
                "datapaths": sorted(self.datapaths),
                "active_rules": sum(rule.get("status") == "active" for rule in self.rules.values()),
            }
        if method == "POST" and path == "/ips/mode":
            self.enabled = bool(payload.get("enabled"))
            self._audit("ips_enabled" if self.enabled else "ips_paused")
            return 200, {"enabled": self.enabled}
        if method == "GET" and path == "/ips/rules":
            rules = [self._public_rule(rule) for rule in self.rules.values()]
            rules.sort(key=lambda item: str(item.get("created_at", "")), reverse=True)
            return 200, {"rules": rules}
        if method == "POST" and path == "/ips/rules":
            return self._create_rule(payload)
        if method == "GET" and path == "/ips/audit":
            return 200, {"events": self.audit[:100]}
        if method == "DELETE" and path.startswith("/ips/rules/"):
            return self._delete_rule(path.rsplit("/", 1)[-1])
        return 404, {"detail": "IPS endpoint không tồn tại"}

