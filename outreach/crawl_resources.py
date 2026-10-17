"""Resource-aware job admission; active browser jobs finish without being killed."""
import json
import math
import time
from pathlib import Path

import psutil


def cgroup_read(root, name):
    try:
        return (root/name).read_text().strip()
    except OSError:
        return ''


def container_limits(root=Path('/sys/fs/cgroup')):
    """Read common cgroup v2/v1 limits; unknown layouts fall back to host metrics."""
    result = {}
    maximum = cgroup_read(root, 'memory.max') or cgroup_read(root, 'memory/memory.limit_in_bytes')
    usage = cgroup_read(root, 'memory.current') or cgroup_read(root, 'memory/memory.usage_in_bytes')
    try:
        limit, used = int(maximum), int(usage)
        if 0 < limit < 2**60:
            result.update(memory_limit=limit, memory_used=used)
    except ValueError:
        pass
    quota = cgroup_read(root, 'cpu.max').split()
    if not quota:
        quota = [cgroup_read(root, 'cpu/cpu.cfs_quota_us'), cgroup_read(root, 'cpu/cpu.cfs_period_us')]
    try:
        if int(quota[0]) > 0 and int(quota[1]) > 0:
            result['cpu_cores'] = int(quota[0])/int(quota[1])
    except (ValueError, IndexError):
        pass
    for line in cgroup_read(root, 'cpu.stat').splitlines():
        if line.startswith('usage_usec '):
            try:
                result['cpu_used_seconds'] = int(line.split()[1])/1_000_000
            except (ValueError, IndexError):
                pass
    return result


class ResourceProbe:
    def __init__(self):
        self.previous = None
        psutil.cpu_percent(interval=None)  # Prime the nonblocking CPU sample.

    def __call__(self, settings):
        memory = psutil.virtual_memory()
        cpu = psutil.cpu_percent(interval=None)
        free, percent = memory.available, memory.percent
        limits = container_limits()
        if limits.get('memory_limit'):
            limit, used = limits['memory_limit'], limits['memory_used']
            free, percent = min(free, max(0, limit-used)), max(percent, 100*used/limit)
        now = time.monotonic()
        if 'cpu_used_seconds' in limits and 'cpu_cores' in limits:
            if self.previous and now > self.previous[0]:
                load = 100*max(0, limits['cpu_used_seconds']-self.previous[1])/(now-self.previous[0])/limits['cpu_cores']
                cpu = max(cpu, load)
            self.previous = (now, limits['cpu_used_seconds'])
        if settings.crawl_memory_budget_mb:
            process = psutil.Process()
            used = 0
            for child in [process, *process.children(recursive=True)]:
                try:
                    used += child.memory_info().rss
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            budget = settings.crawl_memory_budget_mb*1024**2
            free, percent = min(free, max(0, budget-used)), max(percent, 100*used/budget)
        return {'cpu_percent': round(cpu, 2), 'memory_percent': round(percent, 2),
                'available_mb': round(free/1024**2, 2), 'container_limit': bool(limits.get('memory_limit'))}


class AdaptiveConcurrency:
    def __init__(self, settings, db, probe=None, clock=None):
        self.settings, self.db = settings, db
        self.probe = probe or ResourceProbe()
        self.clock = clock or time.monotonic
        self.active, self.desired, self.last_sample = 0, 1, None
        self.metrics, self.reason, self.paused = {}, 'starting', False

    def update(self):
        now = self.clock()
        if self.last_sample is not None and now-self.last_sample < 5:
            return
        first = self.last_sample is None
        self.last_sample = now
        if not self.settings.crawl_adaptive_concurrency:
            self.desired, self.paused, self.reason = self.settings.crawl_concurrency, False, 'configured_limit'
            return
        try:
            self.metrics = self.probe(self.settings)
            cpu, memory, free = (self.metrics[k] for k in ('cpu_percent', 'memory_percent', 'available_mb'))
            if not all(math.isfinite(v) and v >= 0 for v in (cpu, memory, free)):
                raise ValueError('Invalid resource metrics')
            reserve = self.settings.crawl_task_memory_mb
            self.paused = memory >= 95 or cpu >= 98 or free < reserve/2
            if self.paused:
                self.desired, self.reason = max(1, self.desired-1), 'resource_pressure_pause'
            elif cpu >= 85 or memory >= 85 or free < reserve:
                self.desired, self.reason = max(1, self.desired-1), 'resource_pressure_reduce'
            elif not first and cpu < 70 and memory < 85 and free >= 2*reserve:
                self.desired, self.reason = min(self.settings.crawl_concurrency, self.desired+1), 'headroom_available'
            else:
                self.reason = 'starting' if first else 'steady'
        except (psutil.Error, OSError, ValueError, KeyError):
            self.metrics = {}
            self.desired, self.paused, self.reason = 1, False, 'metrics_unavailable_serial'

    def publish(self):
        self.db.set('crawler_runtime', json.dumps({**self.metrics, 'desired': self.desired,
            'active': self.active, 'maximum': self.settings.crawl_concurrency,
            'reason': self.reason, 'paused_admission': self.paused, 'at': time.time()}))

    def acquire(self):
        self.update()
        allowed = not self.paused and self.active < self.desired
        if allowed:
            self.active += 1
        self.publish()
        return allowed

    def release(self):
        self.active = max(0, self.active-1)
        self.publish()
