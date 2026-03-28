# -*- coding: utf-8 -*-
"""
启动 Streamlit，并在同一端口注册 /tender-files/ → 项目 tender_files 目录，
使报告 Excel 中的「来源网站」链接可直接下载本地标书。

请在项目根目录执行:
  python run_streamlit.py
  python run_streamlit.py app.py --server.port 8501

注意: 若仍使用「streamlit run app.py」启动，/tender-files/ 会返回 Streamlit 页面而非文件。
"""
import os
import sys

_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from utils.tender_files_streamlit_route import install_tender_files_route

install_tender_files_route()

if __name__ == "__main__":
    from streamlit.web import cli as stcli

    if len(sys.argv) > 1:
        sys.argv = ["streamlit", "run", *sys.argv[1:]]
    else:
        sys.argv = ["streamlit", "run", "app.py"]
    raise SystemExit(stcli.main())
