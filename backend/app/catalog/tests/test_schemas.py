from app.catalog.models import Store
from app.catalog.schemas import StoreOut


def test_store_out_exposes_id_as_store_id():
    store = Store(
        id="482010105",
        source="zakaz",
        chain="novus",
        name="NOVUS SkyMall DRIVE",
        city="Київ",
        address="Романа Шухевича, 2т",
        lat=50.4931815,
        lng=30.5581461,
        has_pickup=True,
    )
    out = StoreOut.model_validate(store).model_dump()
    assert out["store_id"] == "482010105"
    assert "id" not in out
    assert out["chain"] == "novus"
