#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import socket
import struct
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path


CMD_READ = 0x01
CMD_WRITE = 0x03
HEADER_FORMAT = "<5I"
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)

MODULE_ID = 0x80000024
DP_FPGA_FW_BUILD = 0x80000010
CALIB_BUILD = 0x80000014
DP_CLOCK_STATUS = 0x80000020
CAL_COUNT = 0x80000448
PDTS_CMD_CONTROL_1 = 0x80000464
PDTS_CMD_CONTROL_2 = 0x80000468
PDTS_CONTROL = 0x800004C0
PDTS_STATUS = 0x800004C4
DP_CLOCK_CONTROL = 0x80000520
PDTS_CMD_DELAY_0 = 0x80000940
BIAS_CONTROL = 0x40000300
MASTER_LOGIC_CONTROL = 0x80000500
MASTER_LOGIC_STATUS = 0x80000504

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 55001
DEFAULT_TIMEOUT = 5.0
DEFAULT_SSH_TUNNEL_REMOTE_HOST = "127.0.0.1"
DEFAULT_PDTS_RESET_HOLD_SECONDS = 1.0
DEFAULT_PDTS_RUN_SETTLE_SECONDS = 2.0

NON_LATCHED_REGISTERS = {BIAS_CONTROL}

PDTS_REPORT_REGISTERS = (
    (DP_CLOCK_CONTROL, "dp_clock_control"),
    (PDTS_CONTROL, "pdts_control"),
    (PDTS_STATUS, "pdts_status"),
    (PDTS_CMD_CONTROL_1, "pdts_cmd_control_1"),
    (PDTS_CMD_CONTROL_2, "pdts_cmd_control_2"),
    (CAL_COUNT, "cal_count"),
    *tuple((PDTS_CMD_DELAY_0 + index * 4, f"pdts_cmd_delay_{index}") for index in range(16)),
)

INSPECT_REGISTERS = (
    (DP_FPGA_FW_BUILD, "dp_fpga_fw_build"),
    (CALIB_BUILD, "calib_build"),
    (DP_CLOCK_STATUS, "dp_clock_status"),
    (MASTER_LOGIC_CONTROL, "master_logic_control"),
    (MASTER_LOGIC_STATUS, "master_logic_status"),
    (DP_CLOCK_CONTROL, "dp_clock_control"),
    (PDTS_CONTROL, "pdts_control"),
    (PDTS_STATUS, "pdts_status"),
    (PDTS_CMD_CONTROL_1, "pdts_cmd_control_1"),
    (PDTS_CMD_CONTROL_2, "pdts_cmd_control_2"),
    (CAL_COUNT, "cal_count"),
)


@dataclass
class LEDRunConfig:
    number_channels: int = 12
    channel_mask: int = 1
    pulse_mode: str = "single"
    burst_count: int = 1
    double_pulse_delay_ticks: int = 0
    pulse1_width_ticks: int = 5
    pulse2_width_ticks: int = 0
    pulse_bias_percent_270nm: int = 4000
    pulse_bias_percent_367nm: int = 0
    module_id: int | None = None
    partition_number: int | None = None
    timing_address: int | None = None
    pdts_sync: bool = False


def parse_int(value: str | int | None) -> int | None:
    if value is None or isinstance(value, int):
        return value
    return int(str(value), 0)


def load_json_config(path: Path) -> LEDRunConfig:
    raw = json.loads(path.read_text())
    ssp_conf = raw.get("ssp_conf", {})
    cfg = LEDRunConfig()

    for field_name in (
        "number_channels",
        "channel_mask",
        "pulse_mode",
        "burst_count",
        "double_pulse_delay_ticks",
        "pulse1_width_ticks",
        "pulse2_width_ticks",
        "pulse_bias_percent_270nm",
        "pulse_bias_percent_367nm",
    ):
        if field_name not in ssp_conf:
            continue
        value = ssp_conf[field_name]
        if field_name == "pulse_mode":
            setattr(cfg, field_name, str(value))
        else:
            setattr(cfg, field_name, parse_int(value))

    return cfg


def validate_config(cfg: LEDRunConfig) -> None:
    if cfg.number_channels not in (5, 12):
        raise ValueError(f"number_channels must be 5 or 12, got {cfg.number_channels}")
    if cfg.channel_mask < 0 or cfg.channel_mask > 4095:
        raise ValueError(f"channel_mask must be in 0..4095, got {cfg.channel_mask}")
    if cfg.pulse_mode not in ("single", "burst"):
        raise ValueError(f"pulse_mode must be 'single' or 'burst', got {cfg.pulse_mode}")
    if cfg.burst_count < 0 or cfg.burst_count > 10000:
        raise ValueError(f"burst_count must be in 0..10000, got {cfg.burst_count}")
    if cfg.double_pulse_delay_ticks < 0 or cfg.double_pulse_delay_ticks > 4095:
        raise ValueError(
            f"double_pulse_delay_ticks must be in 0..4095, got {cfg.double_pulse_delay_ticks}"
        )
    if cfg.pulse1_width_ticks < 0 or cfg.pulse1_width_ticks > 255:
        raise ValueError(f"pulse1_width_ticks must be in 0..255, got {cfg.pulse1_width_ticks}")
    if cfg.pulse2_width_ticks < 0 or cfg.pulse2_width_ticks > 255:
        raise ValueError(f"pulse2_width_ticks must be in 0..255, got {cfg.pulse2_width_ticks}")
    if cfg.pulse_bias_percent_270nm < 0 or cfg.pulse_bias_percent_270nm > 4095:
        raise ValueError(
            "pulse_bias_percent_270nm must be in 0..4095, "
            f"got {cfg.pulse_bias_percent_270nm}"
        )
    if cfg.pulse_bias_percent_367nm < 0 or cfg.pulse_bias_percent_367nm > 4095:
        raise ValueError(
            "pulse_bias_percent_367nm must be in 0..4095, "
            f"got {cfg.pulse_bias_percent_367nm}"
        )
    if cfg.pdts_sync:
        if cfg.partition_number is None:
            raise ValueError("--partition-number is required with --pdts-sync")
        if cfg.timing_address is None:
            raise ValueError("--timing-address is required with --pdts-sync")
        if cfg.partition_number < 0 or cfg.partition_number > 3:
            raise ValueError(f"partition_number must be in 0..3, got {cfg.partition_number}")
        if cfg.timing_address < 0 or cfg.timing_address > 0xFF:
            raise ValueError(f"timing_address must be in 0..255, got {cfg.timing_address}")


class SSPClient:
    def __init__(self, host: str, port: int, timeout: float):
        self._sock = socket.create_connection((host, port), timeout=timeout)
        self._sock.settimeout(timeout)

    def close(self) -> None:
        self._sock.close()

    def _recv_exact(self, size: int) -> bytes:
        chunks: list[bytes] = []
        remaining = size
        while remaining > 0:
            chunk = self._sock.recv(remaining)
            if not chunk:
                raise ConnectionError("socket closed while receiving response")
            chunks.append(chunk)
            remaining -= len(chunk)
        return b"".join(chunks)

    def _transaction(self, address: int, command: int, data_words: list[int]) -> tuple[int, int, int, int, int, list[int]]:
        payload = struct.pack(f"<{len(data_words)}I", *data_words) if data_words else b""
        packet = struct.pack(
            HEADER_FORMAT,
            HEADER_SIZE + len(payload),
            address,
            command,
            1,
            0,
        ) + payload
        self._sock.sendall(packet)

        header = self._recv_exact(HEADER_SIZE)
        total_len, rx_addr, rx_cmd, rx_size, rx_status = struct.unpack(HEADER_FORMAT, header)
        if total_len < HEADER_SIZE:
            raise RuntimeError(f"invalid response length {total_len} for address 0x{address:08X}")
        payload_len = total_len - HEADER_SIZE
        payload_bytes = self._recv_exact(payload_len) if payload_len else b""
        if payload_len % 4 != 0:
            raise RuntimeError(f"misaligned payload length {payload_len} for address 0x{address:08X}")
        payload_words = list(struct.unpack(f"<{payload_len // 4}I", payload_bytes)) if payload_len else []
        return total_len, rx_addr, rx_cmd, rx_size, rx_status, payload_words

    def read(self, address: int) -> int:
        _, rx_addr, _, _, rx_status, payload = self._transaction(address, CMD_READ, [])
        if rx_addr != address:
            raise RuntimeError(
                f"read response address mismatch: expected 0x{address:08X}, got 0x{rx_addr:08X}"
            )
        if rx_status != 0:
            raise RuntimeError(f"read failed at 0x{address:08X}, status=0x{rx_status:08X}")
        if not payload:
            raise RuntimeError(f"read response missing payload for 0x{address:08X}")
        return payload[0]

    def write(self, address: int, value: int, *, verify: bool = True) -> int | None:
        _, rx_addr, _, _, rx_status, _ = self._transaction(address, CMD_WRITE, [value])
        if rx_addr != address:
            raise RuntimeError(
                f"write response address mismatch: expected 0x{address:08X}, got 0x{rx_addr:08X}"
            )
        if rx_status != 0:
            raise RuntimeError(f"write failed at 0x{address:08X}, status=0x{rx_status:08X}")
        if not verify or address in NON_LATCHED_REGISTERS:
            return None
        readback = self.read(address)
        if readback != value:
            raise RuntimeError(
                f"readback mismatch at 0x{address:08X}: wrote 0x{value:08X}, got 0x{readback:08X}"
            )
        return readback


class SSHTunnel:
    def __init__(self, jump_host: str, local_port: int, remote_host: str, remote_port: int):
        self._jump_host = jump_host
        self._local_port = local_port
        self._remote_host = remote_host
        self._remote_port = remote_port
        self._proc: subprocess.Popen[str] | None = None

    def __enter__(self) -> "SSHTunnel":
        cmd = [
            "ssh",
            "-N",
            "-o",
            "ExitOnForwardFailure=yes",
            "-L",
            f"{self._local_port}:{self._remote_host}:{self._remote_port}",
            self._jump_host,
        ]
        self._proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )

        deadline = time.time() + 5.0
        while time.time() < deadline:
            if self._proc.poll() is not None:
                stderr = self._proc.stderr.read().strip() if self._proc.stderr else ""
                raise RuntimeError("failed to start SSH tunnel" + (f": {stderr}" if stderr else ""))
            time.sleep(0.1)

        print(
            "SSH tunnel ready:"
            f" localhost:{self._local_port} -> {self._remote_host}:{self._remote_port} via {self._jump_host}"
        )
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._proc is None:
            return
        self._proc.terminate()
        try:
            self._proc.wait(timeout=2.0)
        except subprocess.TimeoutExpired:
            self._proc.kill()
            self._proc.wait(timeout=2.0)


def write_and_log(client: SSPClient, address: int, value: int, *, verify: bool = True, label: str = "") -> None:
    readback = client.write(address, value, verify=verify)
    if verify and address not in NON_LATCHED_REGISTERS:
        print(f"0x{address:08X} <- 0x{value:08X} OK {label}".rstrip())
    else:
        suffix = f" {label}" if label else ""
        print(f"0x{address:08X} <- 0x{value:08X} SENT{suffix}")
    if readback is not None and readback != value:
        raise RuntimeError(
            f"unexpected readback at 0x{address:08X}: wrote 0x{value:08X}, got 0x{readback:08X}"
        )


def sync_pdts(client: SSPClient, partition_number: int, timing_address: int) -> None:
    pdts_status = client.read(PDTS_STATUS)
    pdts_control = client.read(PDTS_CONTROL)
    dp_clock_control = client.read(DP_CLOCK_CONTROL)

    present_timing_address = (pdts_control >> 16) & 0xFF
    present_timing_partition = pdts_control & 0x3
    status_nibble = pdts_status & 0xF

    print(
        "PDTS status before sync:"
        f" status=0x{pdts_status:08X} control=0x{pdts_control:08X} dp_clock=0x{dp_clock_control:08X}"
    )

    if (
        0x6 <= status_nibble <= 0x8
        and present_timing_address == timing_address
        and present_timing_partition == partition_number
        and (dp_clock_control & 0xF) == 0x1
    ):
        print("PDTS already looks synced; skipping reset")
    else:
        print(f"Syncing PDTS: partition={partition_number} timing_address=0x{timing_address:02X}")
        for attempt in range(5):
            reset_value = 0x80000000 + partition_number + timing_address * 0x10000
            run_value = partition_number + timing_address * 0x10000

            write_and_log(client, DP_CLOCK_CONTROL, 0x30, label="pdts internal clock")
            write_and_log(
                client,
                PDTS_CONTROL,
                reset_value,
                label="pdts reset",
            )
            time.sleep(DEFAULT_PDTS_RESET_HOLD_SECONDS)
            pdts_status = client.read(PDTS_STATUS)
            pdts_control = client.read(PDTS_CONTROL)
            dp_clock_control = client.read(DP_CLOCK_CONTROL)
            print(
                "PDTS after reset:"
                f" status=0x{pdts_status:08X} control=0x{pdts_control:08X} dp_clock=0x{dp_clock_control:08X}"
            )
            write_and_log(
                client,
                PDTS_CONTROL,
                run_value,
                label="pdts run",
            )
            time.sleep(DEFAULT_PDTS_RUN_SETTLE_SECONDS)
            pdts_status = client.read(PDTS_STATUS)
            pdts_control = client.read(PDTS_CONTROL)
            print(f"PDTS after run release: status=0x{pdts_status:08X} control=0x{pdts_control:08X}")
            write_and_log(client, DP_CLOCK_CONTROL, 0x31, label="pdts external clock")
            time.sleep(DEFAULT_PDTS_RUN_SETTLE_SECONDS)
            pdts_status = client.read(PDTS_STATUS)
            print(f"PDTS attempt {attempt + 1}: status=0x{pdts_status:08X}")
            if 0x6 <= (pdts_status & 0xF) <= 0x8:
                break
        else:
            raise RuntimeError(f"PDTS sync failed after 5 tries; status=0x{pdts_status:08X}")

    for _ in range(3):
        pdts_status = client.read(PDTS_STATUS)
        if (pdts_status & 0xF) == 0x8:
            print(f"PDTS running: status=0x{pdts_status:08X}")
            return
        print(f"Waiting for PDTS running state, current status=0x{pdts_status:08X}")
        time.sleep(2.0)
    raise RuntimeError(f"PDTS did not reach running state 0x8; last status=0x{pdts_status:08X}")


def dump_registers(client: SSPClient, registers: tuple[tuple[int, str], ...], *, heading: str) -> None:
    print(heading)
    for address, label in registers:
        value = client.read(address)
        print(f"  0x{address:08X}  0x{value:08X}  {label}")


def configure_pdts_register_block(client: SSPClient) -> None:
    write_and_log(client, PDTS_CMD_CONTROL_1, 0x000002E7, label="pdts_cmd_control_1")
    for index in range(16):
        write_and_log(
            client,
            PDTS_CMD_DELAY_0 + index * 4,
            0x00030036,
            label=f"pdts_cmd_delay_{index}",
        )
    write_and_log(client, PDTS_CMD_CONTROL_2, 0x80000000, label="pdts_cmd_control_2")
    write_and_log(client, DP_CLOCK_CONTROL, 0x00000011, label="pulser/dp clock control")


def pulse_master_logic_reset(client: SSPClient) -> None:
    current = client.read(MASTER_LOGIC_CONTROL)
    cleared = current & ~0x00000101
    print(f"Master logic before pulse: control=0x{current:08X}")
    write_and_log(client, MASTER_LOGIC_CONTROL, cleared, label="master_logic clear reset bits")
    time.sleep(0.1)
    write_and_log(client, MASTER_LOGIC_CONTROL, 0x00000041, label="master_logic start")
    status = client.read(MASTER_LOGIC_STATUS)
    pdts_status = client.read(PDTS_STATUS)
    print(
        "Master logic after pulse:"
        f" control=0x{client.read(MASTER_LOGIC_CONTROL):08X}"
        f" status=0x{status:08X}"
        f" pdts_status=0x{pdts_status:08X}"
    )


def configure_run(client: SSPClient, cfg: LEDRunConfig) -> None:
    if cfg.pdts_sync:
        sync_pdts(client, cfg.partition_number, cfg.timing_address)

    if cfg.module_id is not None:
        write_and_log(client, MODULE_ID, cfg.module_id, label="module_id")

    configure_pdts_register_block(client)

    cal_count = 1 if cfg.pulse_mode == "single" else cfg.burst_count
    write_and_log(client, CAL_COUNT, cal_count, label="cal_count")

    base_bias_addr = 0x40000340
    base_timing_addr = 0x800003C0
    if cfg.number_channels == 5:
        base_bias_addr = 0x4000035C
        base_timing_addr = 0x800003DC

    pulse_bias_setting_270nm = cfg.pulse_bias_percent_270nm
    pulse_bias_setting_367nm = cfg.pulse_bias_percent_367nm // 2

    for counter in range(cfg.number_channels):
        bias_reg_addr = base_bias_addr + 0x4 * counter
        timing_reg_addr = base_timing_addr + 0x4 * counter

        timing_reg_val = 0xF0000000 if cfg.pulse_mode == "single" else 0x90000000

        if cfg.channel_mask & (1 << counter):
            bias_reg_val = 0x00040000
            if counter < 6:
                bias_reg_val += pulse_bias_setting_270nm
            else:
                bias_reg_val += pulse_bias_setting_367nm
            timing_reg_val += cfg.pulse1_width_ticks
            timing_reg_val += cfg.pulse2_width_ticks << 8
            timing_reg_val += cfg.double_pulse_delay_ticks << 16
            write_and_log(client, bias_reg_addr, bias_reg_val, label=f"bias_config_{counter}")
            if counter == 7 and not (cfg.channel_mask & (1 << (counter - 1))):
                write_and_log(client, bias_reg_addr - 0x4, bias_reg_val, label="channel_7_bias_workaround")
            write_and_log(client, timing_reg_addr, timing_reg_val, label=f"cal_config_{counter}")
        else:
            write_and_log(client, bias_reg_addr, 0x00000000, label=f"bias_config_{counter}")
            write_and_log(client, timing_reg_addr, 0x00000000, label=f"cal_config_{counter}")

    write_and_log(client, BIAS_CONTROL, 0x00000001, verify=False, label="apply_bias")


def stop_run(client: SSPClient) -> None:
    for counter in range(12):
        write_and_log(client, 0x40000340 + 0x4 * counter, 0x00000000, label=f"bias_config_{counter}")
        write_and_log(client, 0x800003C0 + 0x4 * counter, 0x00000000, label=f"cal_config_{counter}")
    write_and_log(client, BIAS_CONTROL, 0x00000001, verify=False, label="apply_bias")


def add_common_connection_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--host", default=DEFAULT_HOST, help=f"Target host (default: {DEFAULT_HOST})")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"Target TCP port (default: {DEFAULT_PORT})")
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        help=f"Socket timeout in seconds (default: {DEFAULT_TIMEOUT})",
    )
    parser.add_argument(
        "--ssh-tunnel",
        help="Start an SSH local forward through this jump host before connecting",
    )
    parser.add_argument(
        "--ssh-tunnel-remote-host",
        default=DEFAULT_SSH_TUNNEL_REMOTE_HOST,
        help=f"Remote host for the SSH local forward (default: {DEFAULT_SSH_TUNNEL_REMOTE_HOST})",
    )
    parser.add_argument(
        "--ssh-tunnel-remote-port",
        type=int,
        help="Remote port for the SSH local forward (default: same as --port)",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Local SSP LED control without DAQ")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Configure and start the SSP LED pulser")
    add_common_connection_args(run_parser)
    run_parser.add_argument("--config", type=Path, help="Optional JSON config containing an ssp_conf block")
    run_parser.add_argument("--number-channels", type=lambda x: int(x, 0))
    run_parser.add_argument("--channel-mask", type=lambda x: int(x, 0))
    run_parser.add_argument("--pulse-mode", choices=("single", "burst"))
    run_parser.add_argument("--burst-count", type=lambda x: int(x, 0))
    run_parser.add_argument("--double-pulse-delay-ticks", type=lambda x: int(x, 0))
    run_parser.add_argument(
        "--pulse-width-ticks",
        type=lambda x: int(x, 0),
        help="Convenience alias for --pulse1-width-ticks",
    )
    run_parser.add_argument("--pulse1-width-ticks", type=lambda x: int(x, 0))
    run_parser.add_argument("--pulse2-width-ticks", type=lambda x: int(x, 0))
    run_parser.add_argument("--pulse-bias-percent-270nm", type=lambda x: int(x, 0))
    run_parser.add_argument("--pulse-bias-percent-367nm", type=lambda x: int(x, 0))
    run_parser.add_argument("--module-id", type=lambda x: int(x, 0))
    run_parser.add_argument("--pdts-sync", action="store_true", help="Perform the PDTS sync/reset sequence before configuring")
    run_parser.add_argument("--partition-number", type=lambda x: int(x, 0))
    run_parser.add_argument("--timing-address", type=lambda x: int(x, 0))

    stop_parser = subparsers.add_parser("stop", help="Stop the SSP LED pulser")
    add_common_connection_args(stop_parser)

    pdts_parser = subparsers.add_parser(
        "pdts-sync-report",
        help="Dump PDTS registers, resync the endpoint, reapply the PDTS register block, and dump again",
    )
    add_common_connection_args(pdts_parser)
    pdts_parser.add_argument("--partition-number", type=lambda x: int(x, 0), required=True)
    pdts_parser.add_argument("--timing-address", type=lambda x: int(x, 0), required=True)

    inspect_parser = subparsers.add_parser(
        "inspect",
        help="Read firmware/version registers and key PDTS registers without modifying state",
    )
    add_common_connection_args(inspect_parser)

    mlr_parser = subparsers.add_parser(
        "master-logic-reset-report",
        help="Dump key registers, pulse master_logic_control reset/start sequence, and dump again",
    )
    add_common_connection_args(mlr_parser)

    return parser


def merge_config(args: argparse.Namespace) -> LEDRunConfig:
    cfg = load_json_config(args.config) if args.config else LEDRunConfig()

    if args.pulse_width_ticks is not None and args.pulse1_width_ticks is not None:
        raise ValueError("use only one of --pulse-width-ticks or --pulse1-width-ticks")

    pulse1_width_ticks = args.pulse1_width_ticks
    if pulse1_width_ticks is None:
        pulse1_width_ticks = args.pulse_width_ticks

    for field_name in (
        "number_channels",
        "channel_mask",
        "pulse_mode",
        "burst_count",
        "double_pulse_delay_ticks",
        "pulse2_width_ticks",
        "pulse_bias_percent_270nm",
        "pulse_bias_percent_367nm",
        "module_id",
        "partition_number",
        "timing_address",
    ):
        value = getattr(args, field_name)
        if value is not None:
            setattr(cfg, field_name, value)
    if pulse1_width_ticks is not None:
        cfg.pulse1_width_ticks = pulse1_width_ticks
    cfg.pdts_sync = args.pdts_sync
    return cfg


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        tunnel_remote_port = args.ssh_tunnel_remote_port or args.port
        tunnel = (
            SSHTunnel(args.ssh_tunnel, args.port, args.ssh_tunnel_remote_host, tunnel_remote_port)
            if args.ssh_tunnel
            else None
        )

        if args.command == "run":
            cfg = merge_config(args)
            validate_config(cfg)
            if tunnel:
                with tunnel:
                    print(f"Connecting to {args.host}:{args.port}")
                    client = SSPClient(args.host, args.port, args.timeout)
                    try:
                        configure_run(client, cfg)
                    finally:
                        client.close()
            else:
                print(f"Connecting to {args.host}:{args.port}")
                client = SSPClient(args.host, args.port, args.timeout)
                try:
                    configure_run(client, cfg)
                finally:
                    client.close()
            print("SSP LED run configured and started")
            return 0

        if args.command == "stop":
            if tunnel:
                with tunnel:
                    print(f"Connecting to {args.host}:{args.port}")
                    client = SSPClient(args.host, args.port, args.timeout)
                    try:
                        stop_run(client)
                    finally:
                        client.close()
            else:
                print(f"Connecting to {args.host}:{args.port}")
                client = SSPClient(args.host, args.port, args.timeout)
                try:
                    stop_run(client)
                finally:
                    client.close()
            print("SSP LED run stopped")
            return 0

        if args.command == "pdts-sync-report":
            if tunnel:
                with tunnel:
                    print(f"Connecting to {args.host}:{args.port}")
                    client = SSPClient(args.host, args.port, args.timeout)
                    try:
                        dump_registers(client, PDTS_REPORT_REGISTERS, heading="PDTS register dump before sync:")
                        sync_pdts(client, args.partition_number, args.timing_address)
                        configure_pdts_register_block(client)
                        dump_registers(client, PDTS_REPORT_REGISTERS, heading="PDTS register dump after sync:")
                    finally:
                        client.close()
            else:
                print(f"Connecting to {args.host}:{args.port}")
                client = SSPClient(args.host, args.port, args.timeout)
                try:
                    dump_registers(client, PDTS_REPORT_REGISTERS, heading="PDTS register dump before sync:")
                    sync_pdts(client, args.partition_number, args.timing_address)
                    configure_pdts_register_block(client)
                    dump_registers(client, PDTS_REPORT_REGISTERS, heading="PDTS register dump after sync:")
                finally:
                    client.close()
            print("PDTS sync/report completed")
            return 0

        if args.command == "inspect":
            if tunnel:
                with tunnel:
                    print(f"Connecting to {args.host}:{args.port}")
                    client = SSPClient(args.host, args.port, args.timeout)
                    try:
                        dump_registers(client, INSPECT_REGISTERS, heading="SSP inspect dump:")
                    finally:
                        client.close()
            else:
                print(f"Connecting to {args.host}:{args.port}")
                client = SSPClient(args.host, args.port, args.timeout)
                try:
                    dump_registers(client, INSPECT_REGISTERS, heading="SSP inspect dump:")
                finally:
                    client.close()
            print("SSP inspect completed")
            return 0

        if args.command == "master-logic-reset-report":
            if tunnel:
                with tunnel:
                    print(f"Connecting to {args.host}:{args.port}")
                    client = SSPClient(args.host, args.port, args.timeout)
                    try:
                        dump_registers(client, INSPECT_REGISTERS, heading="Before master logic reset:")
                        pulse_master_logic_reset(client)
                        dump_registers(client, INSPECT_REGISTERS, heading="After master logic reset:")
                    finally:
                        client.close()
            else:
                print(f"Connecting to {args.host}:{args.port}")
                client = SSPClient(args.host, args.port, args.timeout)
                try:
                    dump_registers(client, INSPECT_REGISTERS, heading="Before master logic reset:")
                    pulse_master_logic_reset(client)
                    dump_registers(client, INSPECT_REGISTERS, heading="After master logic reset:")
                finally:
                    client.close()
            print("Master logic reset/report completed")
            return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    parser.error(f"unknown command {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())

