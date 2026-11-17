import os
import unittest
from unittest.mock import patch

import refresh_strava
from refresh_strava import _validate_activities, format_activity, refresh, render_activity_json


class FormatActivityTests(unittest.TestCase):
    def test_formats_activity_with_german_numbers_and_half_up_elevation(self):
        activity = {
            "id": 123456789,
            "name": "Morgenrunde",
            "start_date_local": "2026-11-17T08:10:00Z",
            "distance": 42123.4,
            "moving_time": 5421,
            "total_elevation_gain": 320.5,
            "calories": 1755,
        }
        self.assertEqual(
            format_activity(activity),
            ["Morgenrunde", "https://www.strava.com/activities/123456789", "17.11.2026 · 42,12 km · 1:30:21 h · 321 hm · 1.755 kcal"],
        )

    def test_serializes_activity_list_without_credentials(self):
        data = render_activity_json([{
            "id": 1, "name": "Testfahrt", "start_date_local": "2026-11-17T09:00:00Z",
            "distance": 1000, "moving_time": 60, "total_elevation_gain": 1,
        }], "https://maps.googleapis.com/maps/api/staticmap?size=600x400")
        self.assertIn('"activities"', data)
        self.assertIn("Testfahrt", data)
        for secret_name in ("access_token", "refresh_token", "client_secret"):
            self.assertNotIn(secret_name, data)

    def test_rejects_empty_and_malformed_responses(self):
        for invalid in ([], {}, [{"id": "not-an-id", "name": "x", "start_date_local": "not-a-date"}]):
            with self.subTest(invalid=invalid), self.assertRaises(RuntimeError):
                _validate_activities(invalid)


class RotationSafetyTests(unittest.TestCase):
    def setUp(self):
        self.env = {
            "STRAVA_CLIENT_ID": "id",
            "STRAVA_CLIENT_SECRET": "secret",
            "STRAVA_REFRESH_TOKEN": "old",
            "STRAVA_TOKEN_ENCRYPTION_KEY": "encryption-key-that-is-long-enough-for-testing",
        }
        self.activity = {"id": 1, "name": "Test", "start_date_local": "2026-11-17T09:00:00Z", "distance": 1000, "moving_time": 60, "total_elevation_gain": 1}

    def test_rotated_token_persisted_before_activity_request(self):
        calls = []
        with patch.dict(os.environ, self.env, clear=True), \
             patch("refresh_strava._preflight"), \
             patch("refresh_strava._read_refresh_token", return_value="old"), \
             patch("refresh_strava._post_form", return_value={"access_token": "access", "refresh_token": "new"}), \
             patch("refresh_strava._persist_rotated_token", side_effect=lambda *_: calls.append("persist")), \
             patch("refresh_strava._get_json", side_effect=lambda *_: calls.append("activities") or [self.activity]), \
             patch("refresh_strava._update_map", return_value="https://maps.googleapis.com/maps/api/staticmap?size=600x400"), \
             patch("refresh_strava._atomic_write"):
            self.assertEqual(refresh(), 0)
        self.assertEqual(calls, ["persist", "activities"])

    def test_persistence_failure_aborts_before_activity_fetch(self):
        with patch.dict(os.environ, self.env, clear=True), \
             patch("refresh_strava._preflight"), \
             patch("refresh_strava._read_refresh_token", return_value="old"), \
             patch("refresh_strava._post_form", return_value={"access_token": "access", "refresh_token": "new"}), \
             patch("refresh_strava._persist_rotated_token", side_effect=RuntimeError("persistence error")), \
             patch("refresh_strava._get_json") as get_activities, \
             patch("refresh_strava._atomic_write") as write_file:
            with self.assertRaisesRegex(RuntimeError, "persistence error"):
                refresh()
        get_activities.assert_not_called()
        write_file.assert_not_called()


if __name__ == "__main__":
    unittest.main()
