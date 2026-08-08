"""ThrottledRestClient._throttle must enforce the rate limit ACROSS threads.
The client is shared between the data cycle and the order path (and a ws
REST-fallback can hit it off-thread); without a lock, concurrent callers
race _last_call and burst past the venue limit - a ban risk on the
execution venue."""
import threading
import time

import pytest

from data._http import ThrottledRestClient


def test_concurrent_callers_are_serialized_to_the_rate_limit():
    # 5/s -> 0.2s min interval; 10 concurrent throttle passes must take at
    # least (10-1)*0.2s if the limiter holds across threads.
    c = ThrottledRestClient(rate_limit_per_sec=5)
    n = 10
    start = time.time()
    threads = [threading.Thread(target=c._throttle) for _ in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    elapsed = time.time() - start
    assert elapsed >= (n - 1) * 0.2 * 0.9   # ~1.8s floor (10% slack)


# timing: UPPER-bounds three 1ms throttle passes at 0.5s of wall clock -
# one bad deschedule under a saturated battery blows it with no defect.
# The serialization test above only LOWER-bounds elapsed (load-safe).
@pytest.mark.timing
def test_single_threaded_behavior_unchanged():
    c = ThrottledRestClient(rate_limit_per_sec=1000)   # 1ms interval
    t0 = time.time()
    for _ in range(3):
        c._throttle()
    # fast path still fast: no lock contention, tiny interval
    assert time.time() - t0 < 0.5


def test_lock_is_not_held_across_the_network_call():
    # _throttle must release before returning so GETs overlap on the wire;
    # verify the lock is free immediately after a throttle pass.
    c = ThrottledRestClient(rate_limit_per_sec=1000)
    c._throttle()
    assert c._throttle_lock.acquire(blocking=False)
    c._throttle_lock.release()
