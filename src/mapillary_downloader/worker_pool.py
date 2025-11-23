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

    def __init__(self, worker_func, max_workers=16, monitoring_interval=10):
        """Initialize adaptive worker pool.

        Args:
            worker_func: Function to run in each worker (must accept work_queue, result_queue)
            max_workers: Maximum number of workers
            monitoring_interval: Seconds between throughput checks
        """
        self.worker_func = worker_func
        self.max_workers = max_workers
        self.monitoring_interval = monitoring_interval

        # Queues
        self.work_queue = mp.Queue(maxsize=max_workers)
        self.result_queue = mp.Queue()

        # Worker management
        self.workers = []
        # Start at 25% of max_workers (at least 1)
        self.current_workers = max(1, int(max_workers * 0.25))

        # Throughput monitoring
        self.throughput_history = deque(maxlen=5)  # Last 5 measurements
        self.worker_count_history = deque(maxlen=5)  # Track worker counts at each measurement
        self.last_processed = 0
        self.last_check_time = time.time()

        self.running = False

    def start(self):
        """Start the worker pool."""
        self.running = True
        logger.debug(f"Starting worker pool with {self.current_workers} workers")

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
            logger.debug(f"Throughput check skipped (elapsed {elapsed:.1f}s < {self.monitoring_interval}s)")
            return

        # Calculate current throughput (items/sec)
        items_since_check = total_processed - self.last_processed
        throughput = items_since_check / elapsed

        current_workers = len(self.workers)
        self.throughput_history.append(throughput)
        self.worker_count_history.append(current_workers)
        self.last_processed = total_processed
        self.last_check_time = now

        logger.info(f"Throughput: {throughput:.1f} items/s (workers: {current_workers}/{self.max_workers})")

        # Need at least 2 measurements to calculate gain per worker
        if len(self.throughput_history) < 2:
            # First measurement - add 20% more workers
            if current_workers < self.max_workers:
                workers_to_add = max(1, int(current_workers * 0.2))
                for i in range(workers_to_add):
                    if len(self.workers) < self.max_workers:
                        new_worker_id = len(self.workers)
                        self._add_worker(new_worker_id)
                        self.current_workers += 1
                logger.info(
                    f"Ramping up: added {workers_to_add} workers (now {self.current_workers}/{self.max_workers})"
                )
            return

        # Calculate throughput gain per worker added
        current_throughput = self.throughput_history[-1]
        previous_throughput = self.throughput_history[-2]
        previous_workers = self.worker_count_history[-2]

        throughput_gain = current_throughput - previous_throughput
        workers_added = current_workers - previous_workers

        logger.debug(
            f"Trend: {previous_throughput:.1f} items/s @ {previous_workers} workers → "
            f"{current_throughput:.1f} items/s @ {current_workers} workers "
            f"(gain: {throughput_gain:.1f}, added: {workers_added})"
        )

        # If throughput decreased significantly, stop adding workers
        if current_throughput < previous_throughput * 0.95:
            logger.info(
                f"Throughput decreasing ({current_throughput:.1f} vs {previous_throughput:.1f} items/s), "
                f"stopping at {current_workers} workers"
            )
        # If throughput is still increasing or stable, add more workers
        elif current_throughput >= previous_throughput * 0.95 and current_workers < self.max_workers:
            if workers_added > 0 and throughput_gain > 0:
                # Calculate gain per worker
                gain_per_worker = throughput_gain / workers_added
                logger.debug(f"Gain per worker: {gain_per_worker:.2f} items/s")

                # Estimate how many more workers we could benefit from
                # Assume diminishing returns, so be conservative
                if gain_per_worker > 0.5:
                    # Good gain per worker - add more aggressively
                    workers_to_add = max(1, int(current_workers * 0.3))
                elif gain_per_worker > 0.2:
                    # Moderate gain - add moderately
                    workers_to_add = max(1, int(current_workers * 0.2))
                else:
                    # Small gain - add conservatively
                    workers_to_add = max(1, int(current_workers * 0.1))

                added = 0
                for i in range(workers_to_add):
                    if len(self.workers) < self.max_workers:
                        new_worker_id = len(self.workers)
                        self._add_worker(new_worker_id)
                        self.current_workers += 1
                        added += 1

                logger.info(
                    f"Throughput increasing (gain: {gain_per_worker:.2f} items/s per worker), "
                    f"added {added} workers (now {self.current_workers}/{self.max_workers})"
                )
            else:
                # Fallback to 20% if we can't calculate gain per worker
                workers_to_add = max(1, int(current_workers * 0.2))
                added = 0
                for i in range(workers_to_add):
                    if len(self.workers) < self.max_workers:
                        new_worker_id = len(self.workers)
                        self._add_worker(new_worker_id)
                        self.current_workers += 1
                        added += 1
                logger.info(f"Ramping up: added {added} workers (now {self.current_workers}/{self.max_workers})")

    def shutdown(self, timeout=2):
        """Shutdown the worker pool gracefully."""
        logger.debug("Shutting down worker pool")
        self.running = False

        # Terminate all workers immediately (they ignore SIGINT so we need to be forceful)
        for p in self.workers:
            if p.is_alive():
                p.terminate()

        # Give them a brief moment to exit
        for p in self.workers:
            p.join(timeout=timeout)
