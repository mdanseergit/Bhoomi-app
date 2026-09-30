from app.services.cooperation.adapters import KarnatakaAdapter, KeralaAdapter, TamilNaduAdapter
from app.services.cooperation.canonical_schema import SCHEMA_VERSION


def test_tamil_nadu_adapter_maps_local_fields_to_canonical():
    adapter = TamilNaduAdapter()
    local_record = {"soil_N": 180, "soil_P": 20, "soil_K": 140, "district": "Salem", "mandal": "Salem", "crop": "rice"}
    canonical = adapter.to_canonical(local_record)
    assert canonical["schema_version"] == SCHEMA_VERSION
    assert canonical["soil"]["nitrogen"] == 180
    assert canonical["farm"]["location"]["state"] == "Tamil Nadu"
    assert canonical["farm"]["location"]["taluk"] == "Salem"


def test_karnataka_adapter_maps_local_fields():
    adapter = KarnatakaAdapter()
    local_record = {"n_kg_ha": 150, "p_kg_ha": 18, "k_kg_ha": 120, "district": "Mysuru", "taluka": "Mysuru", "crop": "ragi"}
    canonical = adapter.to_canonical(local_record)
    assert canonical["soil"]["nitrogen"] == 150
    assert canonical["farm"]["crop"]["name"] == "ragi"


def test_kerala_adapter_maps_local_fields():
    adapter = KeralaAdapter()
    local_record = {"soil_nitrogen_pct": 0.4, "district": "Palakkad", "panchayat": "Kollengode", "crop": "rice"}
    canonical = adapter.to_canonical(local_record)
    assert canonical["soil"]["nitrogen"] == 0.4
    assert canonical["farm"]["location"]["village"] == "Kollengode"


def test_all_adapters_produce_same_schema_version():
    for adapter in (TamilNaduAdapter(), KarnatakaAdapter(), KeralaAdapter()):
        result = adapter.to_canonical({})
        assert result["schema_version"] == SCHEMA_VERSION
        assert set(result.keys()) >= {"farm", "soil", "weather", "vegetation", "risk"}
