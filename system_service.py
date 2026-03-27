import time
from collections import deque
from dataclasses import dataclass, field

import psutil


# ── Ring Buffer ────────────────────────────────────────────

class RingBuffer:
    """Fixed-size circular buffer for sparkline history."""

    def __init__(self, capacity: int = 120):
        self._data: deque[float] = deque(maxlen=capacity)

    def push(self, value: float):
        self._data.append(value)

    def values(self) -> list[float]:
        return list(self._data)

    @property
    def last(self) -> float | None:
        return self._data[-1] if self._data else None

    def __len__(self) -> int:
        return len(self._data)


# ── Data classes ───────────────────────────────────────────

@dataclass
class ProcessInfo:
    pid: int
    name: str
    cpu_percent: float
    memory_mb: float


@dataclass
class AppGroup:
    name: str            # display name (e.g. "chrome", "Terminal")
    process_count: int   # number of processes in group
    cpu_percent: float   # aggregated CPU across all processes
    memory_mb: float     # aggregated memory across all processes


@dataclass
class TerminalProcess:
    name: str
    cpu_percent: float
    memory_mb: float
    process_count: int = 1
    child_count: int = 0


@dataclass
class DriveInfo:
    mountpoint: str
    label: str
    total_gb: float
    used_gb: float
    free_gb: float
    usage_percent: float


@dataclass
class MemoryInfo:
    total_gb: float
    available_gb: float
    used_gb: float
    usage_percent: float


@dataclass
class SystemSnapshot:
    cpu_percent: float = 0.0
    gpu_percent: float | None = None
    gpu_name: str | None = None
    gpu_mem_percent: float | None = None

    net_rate_up: float = 0.0       # bytes/sec
    net_rate_down: float = 0.0     # bytes/sec

    disk_read_rate: float = 0.0    # bytes/sec
    disk_write_rate: float = 0.0   # bytes/sec

    drives: list[DriveInfo] = field(default_factory=list)
    memory: MemoryInfo | None = None

    terminals: list[TerminalProcess] = field(default_factory=list)
    top_cpu: list[ProcessInfo] = field(default_factory=list)
    top_mem: list[ProcessInfo] = field(default_factory=list)
    top_cpu_groups: list[AppGroup] = field(default_factory=list)
    top_mem_groups: list[AppGroup] = field(default_factory=list)

    error: str | None = None


# ── Terminal process names ─────────────────────────────────

TERMINAL_NAMES = {
    "cmd.exe", "powershell.exe", "pwsh.exe",
    "bash.exe", "wsl.exe", "wslhost.exe",
    "windowsterminal.exe", "conhost.exe",
    "mintty.exe", "alacritty.exe", "wezterm-gui.exe",
}

IDLE_PROCESS_NAMES = {"system idle process", "idle"}


# ── GPU helpers ────────────────────────────────────────────

def _init_gpu():
    """Try to initialize NVIDIA GPU monitoring. Returns True if available."""
    try:
        import pynvml
        pynvml.nvmlInit()
        return True
    except Exception:
        return False


def _read_gpu() -> tuple[float | None, str | None, float | None]:
    """Read GPU utilization. Returns (gpu_percent, gpu_name, gpu_mem_percent)."""
    try:
        import pynvml
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        util = pynvml.nvmlDeviceGetUtilizationRates(handle)
        name = pynvml.nvmlDeviceGetName(handle)
        if isinstance(name, bytes):
            name = name.decode("utf-8")
        mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
        mem_pct = (mem_info.used / mem_info.total * 100) if mem_info.total > 0 else 0.0
        return float(util.gpu), name, mem_pct
    except Exception:
        return None, None, None


# ── Format helpers ─────────────────────────────────────────

def format_bytes_rate(bps: float) -> str:
    """Format bytes/sec into human-readable string."""
    if bps < 1024:
        return f"{bps:.0f} B/s"
    elif bps < 1024 * 1024:
        return f"{bps / 1024:.1f} KB/s"
    elif bps < 1024 * 1024 * 1024:
        return f"{bps / (1024 * 1024):.1f} MB/s"
    else:
        return f"{bps / (1024 * 1024 * 1024):.1f} GB/s"


def format_memory(mb: float) -> str:
    """Format memory in MB to human-readable string."""
    if mb < 1024:
        return f"{mb:.0f}M"
    else:
        return f"{mb / 1024:.1f}G"


# ── System Monitor ─────────────────────────────────────────

class SystemMonitor:
    """Collects system metrics. Call collect() from a background thread."""

    def __init__(self):
        # Ring buffers for sparkline history
        self.cpu_history = RingBuffer(120)
        self.gpu_history = RingBuffer(120)
        self.net_up_history = RingBuffer(120)
        self.net_down_history = RingBuffer(120)
        self.disk_read_history = RingBuffer(120)
        self.disk_write_history = RingBuffer(120)

        # Previous counters for rate calculation
        self._prev_net = None
        self._prev_disk = None
        self._prev_time: float | None = None

        # GPU
        self._gpu_available = _init_gpu()

        # Prime cpu_percent
        psutil.cpu_percent(interval=None)
        self._last_cpu = 0.0

        # Process cache (updated at slower rate)
        self._last_proc_update: float = 0.0
        self._cached_terminals: list[TerminalProcess] = []
        self._cached_top_cpu: list[ProcessInfo] = []
        self._cached_top_mem: list[ProcessInfo] = []
        self._cached_top_cpu_groups: list[AppGroup] = []
        self._cached_top_mem_groups: list[AppGroup] = []

    def collect(self) -> SystemSnapshot:
        """Collect a snapshot of system metrics. Thread-safe."""
        now = time.monotonic()
        dt = now - self._prev_time if self._prev_time is not None else 1.0
        if dt <= 0:
            dt = 1.0

        # CPU — use a short blocking interval for accurate reading on bg thread
        cpu = psutil.cpu_percent(interval=0.1)
        self.cpu_history.push(cpu)

        # GPU
        gpu_pct, gpu_name, gpu_mem = None, None, None
        if self._gpu_available:
            gpu_pct, gpu_name, gpu_mem = _read_gpu()
            if gpu_pct is not None:
                self.gpu_history.push(gpu_pct)

        # Network
        net = psutil.net_io_counters()
        net_up, net_down = 0.0, 0.0
        if self._prev_net is not None:
            net_down = (net.bytes_recv - self._prev_net.bytes_recv) / dt
            net_up = (net.bytes_sent - self._prev_net.bytes_sent) / dt
        self._prev_net = net
        self.net_up_history.push(net_up)
        self.net_down_history.push(net_down)

        # Disk I/O
        disk_io = psutil.disk_io_counters()
        disk_read, disk_write = 0.0, 0.0
        if self._prev_disk is not None and disk_io is not None:
            disk_read = (disk_io.read_bytes - self._prev_disk.read_bytes) / dt
            disk_write = (disk_io.write_bytes - self._prev_disk.write_bytes) / dt
        self._prev_disk = disk_io
        self.disk_read_history.push(disk_read)
        self.disk_write_history.push(disk_write)

        # Disk space (all drives)
        drives = []
        for part in psutil.disk_partitions(all=False):
            try:
                usage = psutil.disk_usage(part.mountpoint)
                drives.append(DriveInfo(
                    mountpoint=part.mountpoint,
                    label=part.mountpoint.rstrip("\\").rstrip("/") or part.device,
                    total_gb=usage.total / (1024 ** 3),
                    used_gb=usage.used / (1024 ** 3),
                    free_gb=usage.free / (1024 ** 3),
                    usage_percent=usage.percent,
                ))
            except (PermissionError, OSError):
                continue

        # RAM
        vm = psutil.virtual_memory()
        mem_info = MemoryInfo(
            total_gb=vm.total / (1024 ** 3),
            available_gb=vm.available / (1024 ** 3),
            used_gb=(vm.total - vm.available) / (1024 ** 3),
            usage_percent=vm.percent,
        )

        # Processes (update every 2 seconds)
        if now - self._last_proc_update >= 2.0:
            self._update_processes()
            self._last_proc_update = now

        self._prev_time = now

        return SystemSnapshot(
            cpu_percent=cpu,
            gpu_percent=gpu_pct,
            gpu_name=gpu_name,
            gpu_mem_percent=gpu_mem,
            net_rate_up=net_up,
            net_rate_down=net_down,
            disk_read_rate=disk_read,
            disk_write_rate=disk_write,
            drives=drives,
            memory=mem_info,
            terminals=self._cached_terminals,
            top_cpu=self._cached_top_cpu,
            top_mem=self._cached_top_mem,
            top_cpu_groups=self._cached_top_cpu_groups,
            top_mem_groups=self._cached_top_mem_groups,
        )

    def _update_processes(self):
        """Update process lists. Called every ~2 seconds."""
        procs = []
        for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_info"]):
            try:
                info = p.info
                name = info["name"] or "unknown"
                if name.lower() in IDLE_PROCESS_NAMES:
                    continue
                mem_mb = (info["memory_info"].rss / (1024 * 1024)) if info["memory_info"] else 0.0
                procs.append({
                    "pid": info["pid"],
                    "name": name,
                    "cpu": info["cpu_percent"] or 0.0,
                    "mem_mb": mem_mb,
                    "proc": p,
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        # Top 5 CPU
        by_cpu = sorted(procs, key=lambda x: x["cpu"], reverse=True)
        self._cached_top_cpu = [
            ProcessInfo(pid=p["pid"], name=p["name"], cpu_percent=p["cpu"], memory_mb=p["mem_mb"])
            for p in by_cpu[:5]
        ]

        # Top 5 Memory
        by_mem = sorted(procs, key=lambda x: x["mem_mb"], reverse=True)
        self._cached_top_mem = [
            ProcessInfo(pid=p["pid"], name=p["name"], cpu_percent=p["cpu"], memory_mb=p["mem_mb"])
            for p in by_mem[:5]
        ]

        # Terminal processes — grouped by name
        term_groups: dict[str, dict] = {}
        for p in procs:
            if p["name"].lower() in TERMINAL_NAMES:
                key = p["name"].lower()
                if key not in term_groups:
                    term_groups[key] = {"name": p["name"], "cpu": 0.0, "mem": 0.0, "count": 0, "children": 0}
                term_groups[key]["cpu"] += p["cpu"]
                term_groups[key]["mem"] += p["mem_mb"]
                term_groups[key]["count"] += 1
                try:
                    term_groups[key]["children"] += len(p["proc"].children())
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass

        terminals = [
            TerminalProcess(
                name=g["name"],
                cpu_percent=g["cpu"],
                memory_mb=g["mem"],
                process_count=g["count"],
                child_count=g["children"],
            )
            for g in term_groups.values()
        ]
        terminals.sort(key=lambda t: t.cpu_percent, reverse=True)
        self._cached_terminals = terminals[:6]

        # Group all processes by app name
        groups: dict[str, dict] = {}
        for p in procs:
            name = p["name"]
            if name not in groups:
                groups[name] = {"cpu": 0.0, "mem_mb": 0.0, "count": 0}
            groups[name]["cpu"] += p["cpu"]
            groups[name]["mem_mb"] += p["mem_mb"]
            groups[name]["count"] += 1

        app_groups = [
            AppGroup(
                name=name.removesuffix(".exe"),
                process_count=g["count"],
                cpu_percent=g["cpu"],
                memory_mb=g["mem_mb"],
            )
            for name, g in groups.items()
        ]

        # Top 5 app groups by CPU
        by_cpu_g = sorted(app_groups, key=lambda g: g.cpu_percent, reverse=True)
        self._cached_top_cpu_groups = by_cpu_g[:5]

        # Top 5 app groups by Memory
        by_mem_g = sorted(app_groups, key=lambda g: g.memory_mb, reverse=True)
        self._cached_top_mem_groups = by_mem_g[:5]
