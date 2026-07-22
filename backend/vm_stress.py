"""
VM Stress Test Module — Execute controlled stress on OpenStack VMs via SSH.

Supports: CPU, RAM, Disk IO, Network stress.
Automatic cleanup after timeout.
Generates realistic incidents for the AI engine.
"""
import logging
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

import paramiko

from .config import settings

logger = logging.getLogger(__name__)

# Active stress tests (tracked for cleanup)
_active_tests: dict[str, dict] = {}


@dataclass
class VMStressConfig:
    """Configuration for a VM stress test."""
    vm_id: str
    vm_ip: str
    ssh_user: str = "root"
    ssh_key_path: Optional[str] = None
    ssh_password: Optional[str] = None
    mode: str = "cpu"           # cpu, ram, disk, network, mixed
    intensity: int = 75         # percentage: 30, 50, 75, 100
    duration_seconds: int = 120
    port: int = 22


def _ssh_connect(config: VMStressConfig) -> paramiko.SSHClient:
    """Establish SSH connection to the target VM."""
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    connect_kwargs = {
        "hostname": config.vm_ip,
        "port": config.port,
        "username": config.ssh_user,
        "timeout": 10,
    }

    if config.ssh_key_path:
        connect_kwargs["key_filename"] = config.ssh_key_path
    elif config.ssh_password:
        connect_kwargs["password"] = config.ssh_password

    client.connect(**connect_kwargs)
    return client


def _build_stress_command(config: VMStressConfig) -> str:
    """Build the stress-ng command based on mode and intensity."""
    duration = config.duration_seconds
    workers = max(1, config.intensity // 25)  # 1-4 workers based on intensity

    if config.mode == "cpu":
        return f"stress-ng --cpu {workers} --cpu-load {config.intensity} --timeout {duration}s --quiet &"
    elif config.mode == "ram":
        # Allocate percentage of available RAM
        ram_pct = config.intensity
        return f"stress-ng --vm {workers} --vm-bytes {ram_pct}% --timeout {duration}s --quiet &"
    elif config.mode == "disk":
        return f"stress-ng --hdd {workers} --hdd-bytes 512M --timeout {duration}s --quiet &"
    elif config.mode == "network":
        return f"stress-ng --sock {workers} --timeout {duration}s --quiet &"
    else:  # mixed
        return (
            f"stress-ng --cpu {workers} --cpu-load {config.intensity} "
            f"--vm 1 --vm-bytes {config.intensity}% "
            f"--hdd 1 --hdd-bytes 256M "
            f"--timeout {duration}s --quiet &"
        )


def _cleanup_command() -> str:
    """Command to kill all stress-ng processes."""
    return "pkill -f stress-ng 2>/dev/null; rm -f /tmp/stress-* 2>/dev/null"


def execute_stress_test(config: VMStressConfig) -> dict:
    """
    Execute a stress test on a remote VM via SSH.
    Returns immediately — stress runs in background on the VM.
    Registers cleanup timer.
    """
    logger.info("[VM-STRESS] Starting %s stress on %s (intensity=%d%%, duration=%ds)",
                config.mode, config.vm_ip, config.intensity, config.duration_seconds)

    try:
        client = _ssh_connect(config)
    except Exception as e:
        logger.error("[VM-STRESS] SSH connection failed to %s: %s", config.vm_ip, e)
        return {
            "status": "error",
            "message": f"SSH connection failed: {e}",
            "vm_id": config.vm_id,
            "vm_ip": config.vm_ip,
        }

    try:
        # Install stress-ng if not present (works on Ubuntu/RHEL/CentOS)
        install_cmd = (
            "which stress-ng >/dev/null 2>&1 || "
            "(apt-get install -y stress-ng 2>/dev/null || yum install -y stress-ng 2>/dev/null || "
            "dnf install -y stress-ng 2>/dev/null)"
        )
        stdin, stdout, stderr = client.exec_command(install_cmd, timeout=30)
        stdout.read()  # wait for completion

        # Execute stress command (backgrounded with &)
        stress_cmd = _build_stress_command(config)
        logger.info("[VM-STRESS] Executing: %s", stress_cmd)
        stdin, stdout, stderr = client.exec_command(stress_cmd, timeout=10)

        # Track this test for cleanup
        test_id = f"{config.vm_id}_{int(time.time())}"
        _active_tests[test_id] = {
            "vm_id": config.vm_id,
            "vm_ip": config.vm_ip,
            "mode": config.mode,
            "intensity": config.intensity,
            "started_at": datetime.utcnow().isoformat(),
            "expires_at": (datetime.utcnow() + timedelta(seconds=config.duration_seconds)).isoformat(),
            "config": config,
        }

        # Schedule automatic cleanup
        def _cleanup_after_timeout():
            time.sleep(config.duration_seconds + 5)
            cleanup_stress_test(config.vm_ip, config.ssh_user, config.ssh_key_path, config.ssh_password)
            _active_tests.pop(test_id, None)
            logger.info("[VM-STRESS] Auto-cleanup completed for %s", config.vm_ip)

        cleanup_thread = threading.Thread(target=_cleanup_after_timeout, daemon=True)
        cleanup_thread.start()

        client.close()

        return {
            "status": "started",
            "test_id": test_id,
            "vm_id": config.vm_id,
            "vm_ip": config.vm_ip,
            "mode": config.mode,
            "intensity": config.intensity,
            "duration_seconds": config.duration_seconds,
            "command": stress_cmd,
            "message": f"Stress test {config.mode} started on {config.vm_ip}. "
                       f"Intensity: {config.intensity}%. Duration: {config.duration_seconds}s. "
                       f"Auto-cleanup scheduled.",
        }

    except Exception as e:
        client.close()
        logger.error("[VM-STRESS] Execution failed on %s: %s", config.vm_ip, e)
        return {"status": "error", "message": f"Stress execution failed: {e}"}


def cleanup_stress_test(
    vm_ip: str,
    ssh_user: str = "root",
    ssh_key_path: Optional[str] = None,
    ssh_password: Optional[str] = None,
) -> dict:
    """Kill all stress-ng processes on a VM and clean temporary files."""
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        connect_kwargs = {"hostname": vm_ip, "username": ssh_user, "timeout": 10}
        if ssh_key_path:
            connect_kwargs["key_filename"] = ssh_key_path
        elif ssh_password:
            connect_kwargs["password"] = ssh_password
        client.connect(**connect_kwargs)

        stdin, stdout, stderr = client.exec_command(_cleanup_command(), timeout=10)
        output = stdout.read().decode()
        client.close()

        logger.info("[VM-STRESS] Cleanup executed on %s", vm_ip)
        return {"status": "cleaned", "vm_ip": vm_ip, "message": f"Stress processes killed on {vm_ip}."}
    except Exception as e:
        logger.error("[VM-STRESS] Cleanup failed on %s: %s", vm_ip, e)
        return {"status": "error", "vm_ip": vm_ip, "message": f"Cleanup failed: {e}"}


def get_active_tests() -> list[dict]:
    """Return all currently active stress tests."""
    now = datetime.utcnow()
    active = []
    expired_keys = []

    for key, test in _active_tests.items():
        expires = datetime.fromisoformat(test["expires_at"])
        if now > expires:
            expired_keys.append(key)
        else:
            active.append({
                "test_id": key,
                "vm_id": test["vm_id"],
                "vm_ip": test["vm_ip"],
                "mode": test["mode"],
                "intensity": test["intensity"],
                "started_at": test["started_at"],
                "expires_at": test["expires_at"],
                "remaining_seconds": int((expires - now).total_seconds()),
            })

    # Clean expired entries
    for key in expired_keys:
        _active_tests.pop(key, None)

    return active
