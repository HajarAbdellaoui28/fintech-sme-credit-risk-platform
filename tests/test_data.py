import pandas as pd
import pandera.pandas as pa
import pytest

from fintech_risk.data import validate_prepared
from fintech_risk.features import POLISH_FEATURES, polish_dictionary


def test_data_schema_duplicate_ids_and_bad_labels():
    data = pd.DataFrame(
        {
            "Attr2": [0.2, 0.4],
            "Attr4": [1.0, 2.0],
            "target": pd.Series([0, 1], dtype="int64"),
            "split": ["train", "test"],
            "row_id": ["a", "b"],
        }
    )
    validate_prepared(data, ["Attr2", "Attr4"])
    invalid = data.copy()
    invalid.loc[1, "row_id"] = "a"
    with pytest.raises(pa.errors.SchemaErrors):
        validate_prepared(invalid, ["Attr2", "Attr4"])
    invalid = data.copy()
    invalid.loc[1, "target"] = 2
    with pytest.raises(pa.errors.SchemaErrors):
        validate_prepared(invalid, ["Attr2", "Attr4"])


def test_dictionary_has_all_features_and_correct_main_definitions():
    dictionary = polish_dictionary()
    assert set(dictionary) == set(POLISH_FEATURES)
    assert dictionary["Attr2"]["definition"] == "Total liabilities / total assets"
    assert dictionary["Attr4"]["definition"] == "Current assets / short-term liabilities"
