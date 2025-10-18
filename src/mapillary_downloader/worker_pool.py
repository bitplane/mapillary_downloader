"""Adaptive worker pool for parallel processing."""

import logging
import multiprocessing as mp
import queue
import time
from collections import deque

logger = logging.getLogger("mapillary_downloader")


class AdaptiveWorkerPool:
    """Worker pool that scales based on throughput.

    Monitors throughput every 30 seconds and adjusts worker count:
    - If throughput increasing: add workers (up to max)
    - If throughput plateauing/decreasing: reduce workers
    """

    def __init__(self, worker_func, min_workers=4, max_workers=16, monitoring_interval=30):
        """Initialize adaptive worker pool.

        Args:
            worker_func: Function to run in each worker (must accept work_queue, result_queue)
            min_workers: Minimum number of workers
            max_workers: Maximum number of workers
            monitoring_interval: Seconds between throughput checks
        """
        self.worker_func = worker_func
        self.min_workers = min_workers
        self.max_workers = max_workers
        self.monitoring_interval = monitoring_interval

        # Queues
        self.work_queue = mp.Queue(maxsize=max_workers)
        self.result_queue = mp.Queue()

        # Worker management
        self.workers = []
        self.current_workers = min_workers

        # Throughput monitoring
        self.throughput_history = deque(maxlen=5)  # Last 5 measurements
        self.last_processed = 0
        self.last_check_time = time.time()

        self.running = False

    def start(self):
        """Start the worker pool."""
        self.running = True
        logger.info(f"Starting worker pool with {self.current_workers} workers")

        for i in range(self.current_workers):
            self._add_worker(i)

    def _add_worker(self, worker_id):
        """Add a new worker to the pool."""
        p = mp.Process(target=self.worker_func, args=(self.work_queue, self.result_queue, worker_id))
        p.start()
        self.workers.append(p)
        logger.debug(f"Started worker {worker_id}")

    def submit(self, work_item):
        """Submit work to the pool (blocks if queue is full)."""
        self.work_queue.put(work_item)

    def get_result(self, timeout=None):
        """Get a result from the workers.

        Returns:
            Result from worker, or None if timeout
        """
        try:
            return self.result_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def check_throughput(self, total_processed):
        """Check throughput and adjust workers if needed.

        Args:
            total_processed: Total number of items processed so far
        """
        now = time.time()
        elapsed = now - self.last_check_time

        if elapsed < self.monitoring_interval:
            return

        # Calculate current throughput (items/sec)
        items_since_check = total_processed - self.last_processed
        throughput = items_since_check / elapsed

        self.throughput_history.append(throughput)
        self.last_processed = total_processed
        self.last_check_time = now

        # Need at least 3 measurements to detect trends
        if len(self.throughput_history) < 3:
            return

        # Check if throughput is increasing
        recent_avg = sum(list(self.throughput_history)[-2:]) / 2
        older_avg = sum(list(self.throughput_history)[-4:-2]) / 2

        if recent_avg > older_avg * 1.1 and len(self.workers) < self.max_workers:
            # Throughput increasing by >10%, add workers
            new_worker_id = len(self.workers)
            self._add_worker(new_worker_id)
            self.current_workers += 1
            logger.info(f"Throughput increasing ({throughput:.1f} items/s), added worker (now {self.current_workers})")

        elif recent_avg < older_avg * 0.9 and len(self.workers) > self.min_workers:
            # Throughput decreasing by >10%, remove worker
            # (workers will exit naturally when they finish current work)
            self.current_workers = max(self.min_workers, self.current_workers - 1)
            logger.info(f"Throughput plateauing ({throughput:.1f} items/s), reducing to {self.current_workers} workers")

    def shutdown(self, timeout=30):
        """Shutdown the worker pool gracefully."""
        logger.info("Shutting down worker pool...")
        self.running = False

        # Send stop signals
        for _ in self.workers:
            self.work_queue.put(None)

        # Wait for workers to finish
        for p in self.workers:
            p.join(timeout=timeout)
            if p.is_alive():
                logger.warning(f"Worker {p.pid} did not exit cleanly, terminating")
                p.terminate()

        logger.info("Worker pool shutdown complete")
