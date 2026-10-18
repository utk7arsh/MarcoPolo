from marco.photon_requests import PendingLabelRequests


def message(touch):
    return dict(type="label_request", touch_id=touch, crop_url=f"/v1/touch/{touch}/crop.jpg")


def test_requests_are_bounded_deduplicated_and_resolved():
    pending = PendingLabelRequests(max_entries=2)
    pending.add(message("first"))
    pending.add(message("second"))
    pending.add(message("second"))
    pending.add(message("third"))
    assert pending.pending() == [message("second"), message("third")]
    pending.resolve("second")
    pending.resolve("missing")
    assert pending.pending() == [message("third")]


def test_old_requests_expire_without_refreshing_on_read():
    now = [0.0]
    pending = PendingLabelRequests(clock=lambda: now[0], max_age_s=600)
    pending.add(message("old"))
    now[0] = 599
    assert pending.pending() == [message("old")]
    now[0] = 600
    assert pending.pending() == []
