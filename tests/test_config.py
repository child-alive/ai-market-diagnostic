"""配置加载的安全边界。"""

from src import config


def test_root_only_dotenv_can_be_supplied_by_process_environment(monkeypatch):
    def deny_file_read(*_args, **_kwargs):
        raise PermissionError("root-only dotenv")

    monkeypatch.setattr(config, "load_dotenv", deny_file_read)

    # systemd 已注入环境变量时，服务不应因无权重读 .env 而退出。
    config._load_project_dotenv()
