import importlib.util
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
                ("UNKNOWN", False),
            ):
                with patch.object(doctor, "command", return_value=version):
                    result = doctor.module_status(Path(temporary), Path(temporary))
                self.assertEqual(
                    result["youtube_receiver"]["runtimeVersionCompatible"], expected
                )
