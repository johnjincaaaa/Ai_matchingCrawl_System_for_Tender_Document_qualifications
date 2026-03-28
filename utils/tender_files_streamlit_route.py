# -*- coding: utf-8 -*-
"""
在 Streamlit 内置 Tornado 上注册 tender_files 静态路由（与报告中的 TENDER_FILES_URL_PREFIX 一致）。

必须在创建 Server 并调用 _create_app 之前替换 Server._create_app，因此请用项目根的
run_streamlit.py 启动，而不是直接使用 streamlit run app.py。

可通过环境变量 TENDER_FILES_STREAMLIT_ROUTE=0 禁用。
"""
from __future__ import annotations

import logging
import os

log = logging.getLogger(__name__)

_INSTALLED = False


def install_tender_files_route() -> None:
    """Monkey-patch streamlit Server._create_app，在应用中注册 tender-files 静态目录。"""
    global _INSTALLED
    raw = os.environ.get("TENDER_FILES_STREAMLIT_ROUTE", "1").strip().lower()
    if raw in ("0", "false", "no", "off"):
        return
    if _INSTALLED:
        return

    try:
        from tornado.web import StaticFileHandler

        from streamlit import config as st_config
        from streamlit.web.server.server import Server
        from streamlit.web.server.server_util import make_url_path_regex

        import config as project_config
    except ImportError as e:
        log.warning("install_tender_files_route 跳过：%s", e)
        return

    prefix = (getattr(project_config, "TENDER_FILES_URL_PREFIX", "") or "").strip().strip("/")
    if not prefix:
        log.info("TENDER_FILES_URL_PREFIX 为空，不注册 Streamlit 静态 tender 路由")
        return

    files_root = os.path.abspath(project_config.FILES_DIR)
    _orig_create_app = Server._create_app

    def _create_app_with_tender_files(self):
        application = _orig_create_app(self)
        base = (st_config.get_option("server.baseUrlPath") or "").strip("/")
        if base:
            pattern = make_url_path_regex(base, prefix, "(.*)")
        else:
            pattern = make_url_path_regex(prefix, "(.*)")

        application.add_handlers(
            r".*",
            [
                (
                    pattern,
                    StaticFileHandler,
                    {"path": files_root},
                ),
            ],
        )
        log.info("已注册标书静态目录: pattern=%s path=%s", pattern, files_root)
        return application

    Server._create_app = _create_app_with_tender_files
    _INSTALLED = True
