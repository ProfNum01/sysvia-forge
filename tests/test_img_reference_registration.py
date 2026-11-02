from pathlib import Path

from PIL import Image
from sqlalchemy import select

from backend.app.models.database import AuditEvent, Base, Product, connect_database
from backend.app.services.img_reference_registration import install_img_references


def test_installs_versioned_references_without_replacing_originals(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    target = tmp_path / "data"
    (target / "references").mkdir(parents=True)
    for color in ("yellow", "green", "blue", "red"):
        Image.new("RGB", (512, 512), color).save(source / f"img-{color}-box-v2.png")
        Image.new("RGB", (520, 520), "white").save(target / "references" / f"img-{color}-box.png")
    engine, sessions = connect_database(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    with sessions() as db:
        for color in ("yellow", "green", "blue", "red"):
            db.add(Product(id=f"img-{color}-box", sku=f"IMG-{color.upper()}-BOX", name=f"{color.title()} rectangular box",
                           color="", description="no visible sku label", reference_provenance="SYNTHETIC",
                           visible_label="NONE", registered_reference_path=str(target / "references" / f"img-{color}-box.png")))
        db.commit()
        assert install_img_references(db, target, source) == 4
        assert install_img_references(db, target, source) == 0
        products = list(db.scalars(select(Product).where(Product.id.like("img-%"))))
        assert all(p.registered_reference_path.endswith("-v2.png") for p in products)
        assert all("no visible sku label" in p.description for p in products)
        assert db.query(AuditEvent).filter(AuditEvent.event_type == "SYNTHETIC_REFERENCE_UPDATED").count() == 4
    assert all((target / "references" / f"img-{color}-box.png").is_file() for color in ("yellow", "green", "blue", "red"))
    engine.dispose()
