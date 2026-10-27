import pytest

import db
from validators import normalize_experiment, validate_experiment


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setenv("EXPERIMENT_DB_PATH", str(tmp_path / "test.db"))
    db.init_db()


def sample(**overrides):
    data = {
        "grade": "SCM440",
        "q_condition": 850.0,
        "t_condition": 550.0,
        "hardness": 38.5,
        "yield_strength": 1050.0,
        "tensile_strength": 1180.0,
        "impact_strength": 62.0,
    }
    data.update(overrides)
    return data


def test_init_db_creates_empty_table():
    assert db.list_experiments().empty
    assert db.get_summary()["total"] == 0


def test_add_and_get():
    new_id = db.add_experiment(sample())
    row = db.get_experiment(new_id)
    assert row["grade"] == "SCM440"
    assert row["tensile_strength"] == 1180.0
    assert row["created_at"] == row["updated_at"]


def test_add_with_blank_property_stores_null():
    new_id = db.add_experiment(sample(impact_strength=""))
    assert db.get_experiment(new_id)["impact_strength"] is None


def test_add_missing_required_raises():
    with pytest.raises(ValueError):
        db.add_experiment(sample(grade=""))


def test_update():
    new_id = db.add_experiment(sample())
    assert db.update_experiment(new_id, {"hardness": 40.0})
    row = db.get_experiment(new_id)
    assert row["hardness"] == 40.0
    assert row["tensile_strength"] == 1180.0  # 다른 값은 그대로


def test_update_missing_id_returns_false():
    assert db.update_experiment(9999, {"hardness": 40.0}) is False


def test_update_cannot_blank_required():
    new_id = db.add_experiment(sample())
    with pytest.raises(ValueError):
        db.update_experiment(new_id, {"grade": "  "})


def test_delete():
    new_id = db.add_experiment(sample())
    assert db.delete_experiment(new_id)
    assert db.get_experiment(new_id) is None
    assert db.delete_experiment(new_id) is False


def test_delete_experiments_bulk():
    ids = [db.add_experiment(sample()) for _ in range(3)]
    assert db.delete_experiments([ids[0], ids[2], 9999]) == 2
    assert list(db.list_experiments()["id"]) == [ids[1]]
    assert db.delete_experiments([]) == 0


def test_list_with_filters_and_order():
    db.add_experiment(sample(t_condition=600.0))
    db.add_experiment(sample(t_condition=500.0))
    db.add_experiment(sample())
    db.add_experiment(sample(q_condition=870.0))
    db.add_experiment(sample(grade="S45C"))

    df = db.list_experiments({"grade": ["SCM440"], "q_condition": [850.0]})
    assert list(df["t_condition"]) == [500.0, 550.0, 600.0]
    assert db.list_experiments({"grade": []}).shape[0] == 5  # 빈 필터는 무시
    with pytest.raises(ValueError):
        db.list_experiments({"bad_col": 1})


def test_list_conditions_and_grades():
    db.add_experiment(sample(q_condition=870.0, t_condition=600.0))
    db.add_experiment(sample(q_condition=830.0, t_condition=500.0))
    db.add_experiment(sample(grade="S45C", q_condition=900.0))
    assert db.list_grades() == ["S45C", "SCM440"]
    assert db.list_q_conditions("SCM440") == [830.0, 870.0]
    assert db.list_t_conditions("SCM440") == [500.0, 600.0]


def test_filter_value_is_parameterized():
    db.add_experiment(sample())
    assert db.list_experiments({"grade": "' OR 1=1 --"}).empty


def test_add_experiments_bulk_and_summary():
    assert db.add_experiments([sample(), sample(), sample(t_condition=600.0)]) == 3
    summary = db.get_summary()
    assert summary["total"] == 3
    assert summary["grades"] == 1
    assert summary["combos"] == 2


def test_validate_experiment():
    assert validate_experiment(sample()) == []
    assert validate_experiment(sample(hardness="", impact_strength=None)) == []
    errors = validate_experiment(sample(grade=" ", q_condition="abc", t_condition=None, hardness=-1))
    assert len(errors) == 4


def test_normalize_experiment():
    record = normalize_experiment(sample(grade=" SCM440 ", q_condition="850", hardness=""))
    assert record["grade"] == "SCM440"
    assert record["q_condition"] == 850.0
    assert record["hardness"] is None


def test_summary_recent_count():
    db.add_experiment(sample())
    assert db.get_summary()["recent"] == 1
    assert db.get_summary(recent_days=0)["recent"] in (0, 1)  # 경계값에서 오류 없이 동작
