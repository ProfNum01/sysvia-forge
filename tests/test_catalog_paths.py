from pathlib import Path

from backend.app.services.catalog import reference_path


def test_windows_registered_reference_resolves_inside_container_data(tmp_path):
    references = tmp_path / "references"
    references.mkdir()
    image = references / "img-green-box.png"
    image.write_bytes(b"fixture")
    stored = r"E:\Amiir_Work\SYSVIA\Hackthon\data\references\img-green-box.png"
    assert reference_path(tmp_path, "img-green-box", "IMG-GREEN-BOX", stored) == image


def test_versioned_synthetic_reference_maps_only_its_registered_product(tmp_path):
    references = tmp_path / "references"
    references.mkdir()
    image = references / "img-green-box-v2.png"
    image.write_bytes(b"fixture")
    stored = r"E:\Amiir_Work\SYSVIA\Hackthon\data\references\img-green-box-v2.png"
    assert reference_path(tmp_path, "img-green-box", "IMG-GREEN-BOX", stored) == image
    assert reference_path(tmp_path, "img-red-box", "IMG-RED-BOX", stored) is None


def test_windows_reference_cannot_map_wrong_product_or_untrusted_filename(tmp_path):
    references = tmp_path / "references"
    references.mkdir()
    (references / "img-green-box.png").write_bytes(b"fixture")
    stored = r"E:\data\references\img-green-box.png"
    assert reference_path(tmp_path, "img-red-box", "IMG-RED-BOX", stored) is None
    assert reference_path(tmp_path, "img-green-box", "WRONG-SKU", stored) is None
    assert reference_path(tmp_path, "img-green-box", "IMG-GREEN-BOX", r"E:\other\img-green-box.png") is None
