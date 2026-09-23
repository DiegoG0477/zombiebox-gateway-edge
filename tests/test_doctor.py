import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location(
    "doctor", Path(__file__).resolve().parents[1] / "scripts/doctor.py"
)
doctor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(doctor)


class DoctorTests(unittest.TestCase):
    def test_process_presence_never_implies_account_or_media_readiness(self):
        with tempfile.TemporaryDirectory() as temporary:
            runtime, prefix = Path(temporary) / "runtime", Path(temporary) / "prefix"
            (runtime / "bin").mkdir(parents=True)
            (runtime / "bin/threadfin").touch()
            service = prefix / "var/service/zombie-threadfin"
            service.mkdir(parents=True)
            (service / "run").write_text("private configuration must not be read")
            with (
                patch.object(doctor, "command", return_value="run: fixture: 42s"),
                patch.object(doctor.shutil, "which", return_value=None),
            ):
                result = doctor.module_status(runtime, prefix)
                self.assertEqual(result["iptv_threadfin"]["serviceState"], "running")
                self.assertEqual(result["iptv_threadfin"]["installation"], "present")
                self.assertEqual(
                    result["iptv_threadfin"]["accountReadiness"], "not_probed"
                )
                self.assertFalse(result["iptv_threadfin"]["mediaValidated"])
                self.assertEqual(result["airplay"]["serviceState"], "not_installed")
                self.assertIn("bin/uxplay", result["airplay"]["missing"])
                (service / "down").touch()
                self.assertEqual(
                    doctor.module_status(runtime, prefix)["iptv_threadfin"][
                        "serviceState"
                    ],
                    "disabled",
                )

    def test_node_version_contract_is_not_just_presence(self):
        with (
            tempfile.TemporaryDirectory() as temporary,
            patch.object(doctor.shutil, "which", return_value="/bin/node"),
        ):
            for version, expected in (
                ("v22.22.2", True),
                ("v22.22.1", False),
                ("v24.1.0", False),
                ("v24.18.0", True),
                ("v24.19.0", True),
                ("v23.10.0", False),
                ("UNKNOWN", False),
            ):
                with patch.object(doctor, "command", return_value=version):
                    result = doctor.module_status(Path(temporary), Path(temporary))
                self.assertEqual(
                    result["youtube_receiver"]["runtimeVersionCompatible"], expected
                )


class NetworkDoctorTests(unittest.TestCase):
    def test_shared_core_probe_results_are_allowlisted(self):
        payload = {
            "reportVersion": 1,
            "httpHealth": {"state": "ok", "elapsedMs": 3, "secret": "excluded"},
            "discoveryUnicast": {"state": "port_mismatch", "elapsedMs": 8},
            "rtspOptions": {"state": "authentication_required", "elapsedMs": 4},
            "mediaValidated": True,
            "secret": "excluded",
        }
        completed = subprocess.CompletedProcess(
            [], 0, json.dumps(payload), "private stderr"
        )
        with patch.object(doctor.subprocess, "run", return_value=completed) as run:
            result = doctor.network_report(
                Path("/runtime"), "127.0.0.1", 8090, 8098, 8554
            )
        self.assertFalse(result["mediaValidated"])
        self.assertFalse(result["accountValidated"])
        self.assertNotIn("excluded", json.dumps(result))
        self.assertEqual(result["discoveryUnicast"]["state"], "port_mismatch")
        self.assertEqual(
            run.call_args.args[0][:3],
            ["/runtime/bin/zombied", "--diagnose-address", "127.0.0.1"],
        )
        self.assertEqual(run.call_args.kwargs["timeout"], 4)

    def test_older_binary_or_malformed_output_remains_unknown(self):
        for completed in (
            subprocess.CompletedProcess([], 2, "", "unknown flag and private config"),
            subprocess.CompletedProcess([], 0, "[]", ""),
            subprocess.CompletedProcess([], 0, '{"reportVersion":1}', ""),
        ):
            with patch.object(doctor.subprocess, "run", return_value=completed):
                self.assertEqual(
                    doctor.network_report(
                        Path("/runtime"), "127.0.0.1", 8090, 8098, 8554
                    ),
                    {"state": "unavailable_or_unsupported"},
                )

    def test_timeout_does_not_escape_or_report_success(self):
        with patch.object(
            doctor.subprocess, "run", side_effect=subprocess.TimeoutExpired([], 4)
        ):
            self.assertEqual(
                doctor.network_report(Path("/runtime"), "127.0.0.1", 8090, 8098, 8554),
                {"state": "unavailable_or_unsupported"},
            )


class MediaDoctorTests(unittest.TestCase):
    def test_decode_evidence_does_not_promote_receiver_or_network_support(self):
        payload = {
            "reportVersion": 1,
            **{
                key: {"state": "pass", "videoFrames": 10, "audioFrames": 44}
                for key in ("fixture", "remux", "transcode")
            },
            "receiverValidated": True,
            "secret": "private",
        }
        with patch.object(
            doctor.subprocess,
            "run",
            return_value=subprocess.CompletedProcess(
                [], 0, json.dumps(payload), "private stderr"
            ),
        ) as run:
            report = doctor.media_report(Path("/runtime"))
        self.assertTrue(report["gatewayPipelineVerified"])
        self.assertFalse(report["receiverValidated"])
        self.assertFalse(report["networkValidated"])
        self.assertNotIn("private", str(report))
        self.assertEqual(run.call_args.kwargs["timeout"], 35)
        payload["transcode"]["audioFrames"] = 0
        with patch.object(
            doctor.subprocess,
            "run",
            return_value=subprocess.CompletedProcess([], 0, json.dumps(payload), ""),
        ):
            self.assertEqual(
                doctor.media_report(Path("/runtime")),
                {"state": "unavailable_or_unsupported"},
            )

    def test_missing_core_or_timeout_is_not_decoder_failure(self):
        for failure in (FileNotFoundError(), subprocess.TimeoutExpired([], 35)):
            with patch.object(doctor.subprocess, "run", side_effect=failure):
                self.assertEqual(
                    doctor.media_report(Path("/runtime")),
                    {"state": "unavailable_or_unsupported"},
                )
