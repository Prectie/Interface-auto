from Core.repository import YamlRepository


def test_repository_loads_p0_minimal_assets(p0_minimal_data_dir):
    repo = YamlRepository(p0_minimal_data_dir)
    assets = repo.load()

    assert assets.config.active_env == "test"
    assert set(repo.apis) == {
        "api_start_task",
        "api_update_task_member",
        "api_stop_task",
    }
    assert set(repo.cases) == {
        "case_start_task_success",
        "case_update_task_member_level_4",
        "case_stop_task_success",
    }
    assert set(repo.scenarios) == {"scn_hanoi_main_flow"}
    assert set(repo.plans) == {"plan_hanoi_regression"}


def test_repository_get_env_uses_active_env(p0_minimal_data_dir):
    repo = YamlRepository(p0_minimal_data_dir)
    repo.load()

    env = repo.get_env()

    assert env.variables["scenario_make_id"] == "demo_scenario_make_id"
    assert env.hosts["task_service"] == "http://127.0.0.1:1806"
