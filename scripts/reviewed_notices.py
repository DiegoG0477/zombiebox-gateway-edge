"""Version- and package-scoped reviews of notices embedded in upstream source."""

import hashlib
import zipfile

REVIEWS = {
    ("github.com/benburkert/openpgp", "v0.0.0-20160410205803-c2471f86866c"): {
        "package": "aes/keywrap",
        "noticeFile": "keywrap.go",
        "noticeLines": 23,
        "license": "BSD-2-Clause",
        "files": {
            "doc.go": "4d174657bb31cb5ccb0676495270f50adbe990e2072b30abd8f2064cde3a8884",
            "keywrap.go": "1003ae68bf74ac039e624a5e100a2b89723e06d00b473b52251024d34abeb3c4",
            "keywrap_test.go": "12ed21abf6964d6cee5ed10caa99112a4e78a2596a22dbe349a5c1ba3005d235",
        },
    }
}


def collect_reviewed(module, version, compiled_packages, upstream_zip, output, notice):
    """Fail closed if the build uses any unreviewed package or changed source."""
    review = REVIEWS.get((module, version))
    if review is None or compiled_packages != {module + "/" + review["package"]}:
        raise ValueError(
            "No exact inline-license review for linked packages: " + module
        )
    prefix = module + "@" + version + "/" + review["package"] + "/"
    files = {}
    with zipfile.ZipFile(upstream_zip) as source:
        for name, checksum in review["files"].items():
            entry = source.getinfo(prefix + name)
            if entry.file_size > 262144:
                raise ValueError("Oversized reviewed source")
            data = source.read(entry)
            if hashlib.sha256(data).hexdigest() != checksum:
                raise ValueError("Reviewed inline-license source has changed")
            files[prefix + name] = data
    header = (
        files[prefix + review["noticeFile"]]
        .decode()
        .splitlines()[: review["noticeLines"]]
    )
    if any(not line.startswith("//") for line in header):
        raise ValueError("Reviewed notice boundary has changed")
    notice.write_text("\n".join(line[2:].removeprefix(" ") for line in header) + "\n")
    # Other OpenPGP packages are neither linked nor covered by this review. Do not
    # distribute their source or represent this subset as the original Go proxy ZIP.
    with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_DEFLATED) as target:
        for name, data in files.items():
            target.writestr(name, data)
    return {
        "sourceScope": "reviewed-package-subset",
        "packages": sorted(compiled_packages),
        "license": review["license"],
        "noticeOrigin": prefix + review["noticeFile"],
        "reviewedFiles": review["files"],
    }
