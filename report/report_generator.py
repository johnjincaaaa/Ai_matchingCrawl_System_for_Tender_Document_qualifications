import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side  # 新增 Font 等样式类
from openpyxl.utils.dataframe import dataframe_to_rows
from datetime import datetime, date
from sqlalchemy import and_, or_
import os
import json
from config import REPORT_DIR
from utils.log import log
from utils.db import get_db, TenderProject, ProjectStatus


class ReportGenerator:
    def __init__(self):
        self.db = next(get_db())
        self.report_date = datetime.now().strftime("%Y-%m-%d")
        self.report_path = os.path.join(REPORT_DIR, f"标书资质匹配报告_{self.report_date}.xlsx")

    def _extract_procurement_type(self, site_name):
        """从site_name中提取采购类型，默认为公开招标"""
        # 采购类型默认为公开招标
        return "公开招标"

    def _extract_province_city(self, region):
        """从region中提取省份和城市
        
        根据aaaa.py，API返回的districtName可能是：
        - 市级：杭州市、宁波市等
        - 区级：拱墅区、余杭区、临平区、上城区、滨江区等
        - 县级：淳安县、桐庐县等
        """
        if not region:
            return "未知", "未知"
        
        province = "浙江省"  # 默认省份
        
        # 精确匹配区域名称
        region = region.strip()  # 去除前后空格
        
        # 浙江省的城市和区县映射（根据aaaa.py返回的实际数据）
        city_mapping = {
            # 市级
            "浙江省本级": "浙江省本级",
            "杭州市": "杭州市",
            "宁波市": "宁波市",
            "温州市": "温州市",
            "嘉兴市": "嘉兴市",
            "湖州市": "湖州市",
            "绍兴市": "绍兴市",
            "金华市": "金华市",
            "衢州市": "衢州市",
            "舟山市": "舟山市",
            "台州市": "台州市",
            "丽水市": "丽水市",
            # 杭州市的区县（根据aaaa.py返回的数据）
            "拱墅区": "杭州市",
            "余杭区": "杭州市",
            "临平区": "杭州市",
            "上城区": "杭州市",
            "滨江区": "杭州市",
            "淳安县": "杭州市",
            "桐庐县": "杭州市",
            # 其他可能的区县
            "无区域": "未知"
        }
        
        # 优先精确匹配
        if region in city_mapping:
            city = city_mapping[region]
        else:
            # 如果精确匹配失败，尝试部分匹配
            # 如果包含"区"或"县"，可能是区县，需要映射到对应的市
            if "区" in region or "县" in region:
                # 尝试匹配市级名称
                for city_name in ["杭州市", "宁波市", "温州市", "嘉兴市", "湖州市", "绍兴市", 
                                 "金华市", "衢州市", "舟山市", "台州市", "丽水市"]:
                    if city_name in region or region in city_name:
                        city = city_name
                        break
                else:
                    # 如果没匹配到，默认归到杭州市（因为大部分区县都在杭州市）
                    city = "杭州市"
            elif "市" in region:
                # 直接是市级名称
                city = region if region.endswith("市") else region + "市"
            else:
                # 尝试部分匹配
                city = "未知"
                for key, value in city_mapping.items():
                    if key in region or region in key:
                        city = value
                        break
        
        return province, city

    def _extract_objective_attainable_score(self, comparison_result):
        """从comparison_result中提取客观分可得分
        
        Args:
            comparison_result: 资质比对结果（文本字符串）
        
        Returns:
            客观分可得分（浮点数），如果无法提取则返回None
        """
        if not comparison_result:
            return None
        
        try:
            import re
            
            # 尝试多种格式匹配"客观分可得分"
            attainable_patterns = [
                r'客观分可得分[：:]\s*(\d+(?:\.\d+)?)\s*分',
                r'客观分可得分[：:]\s*\[(\d+(?:\.\d+)?)\]\s*分',
                r'客观分可得分\s*[：:]\s*(\d+(?:\.\d+)?)\s*分',
                r'可得分[：:]\s*(\d+(?:\.\d+)?)\s*分',
                r'可得分[：:]\s*\[(\d+(?:\.\d+)?)\]\s*分',
                r'可得分\s*[：:]\s*(\d+(?:\.\d+)?)\s*分',
            ]
            
            # 尝试匹配可得分
            for pattern in attainable_patterns:
                match = re.search(pattern, comparison_result)
                if match:
                    try:
                        attainable_score = float(match.group(1))
                        return attainable_score
                    except ValueError:
                        continue
            
            return None
        except Exception as e:
            log.debug(f"从comparison_result中提取客观分可得分失败：{str(e)}")
            return None

    def _get_project_data(self, start_date=None, end_date=None, regions=None, procurement_types=None, platform_code=None):
        """获取项目数据（支持筛选）
        
        Args:
            start_date: 开始日期（datetime或date对象）
            end_date: 结束日期（datetime或date对象）
            regions: 城市列表（如["杭州市", "宁波市"]），会按提取的城市进行筛选，None表示全选
            procurement_types: 采购类型列表（如["政府采购", "国企采购"]），None表示全选
            platform_code: 平台代码（如"zhejiang"、"hangzhou"），None表示全选
        """
        query = self.db.query(TenderProject)
        
        # 时间筛选
        if start_date:
            if isinstance(start_date, date) and not isinstance(start_date, datetime):
                start_date = datetime.combine(start_date, datetime.min.time())
            query = query.filter(TenderProject.publish_time >= start_date)
        
        if end_date:
            if isinstance(end_date, date) and not isinstance(end_date, datetime):
                end_date = datetime.combine(end_date, datetime.max.time())
            query = query.filter(TenderProject.publish_time <= end_date)
        
        projects = query.all()
        data = []
        for proj in projects:
            # 提取采购类型
            procurement_type = self._extract_procurement_type(proj.site_name)
            
            # 提取省份和城市（添加调试日志）
            if proj.region:
                log.debug(f"项目 {proj.id} 的 region 值为: {proj.region}")
            province, city = self._extract_province_city(proj.region)
            
            # 城市筛选（按提取的城市进行筛选）
            if regions and len(regions) > 0:
                if city not in regions and proj.region not in regions:
                    continue
            
            # 采购类型筛选
            if procurement_types and len(procurement_types) > 0:
                if procurement_type not in procurement_types:
                    continue
            
            # 平台筛选
            if platform_code:
                # 从site_name中提取平台代码（避免循环导入）
                site_name = proj.site_name or ""
                project_platform = None
                platform_map = {
                    "浙江省政府采购网": "zhejiang",
                    "杭州市公共资源交易网": "hangzhou",
                }
                for platform_name, code in platform_map.items():
                    if platform_name in site_name:
                        project_platform = code
                        break
                
                if project_platform != platform_code:
                    continue
            
            final_decision = proj.final_decision if hasattr(proj, 'final_decision') and proj.final_decision else "未判定"
            
            # 从comparison_result中提取客观分可得分
            objective_attainable_score = self._extract_objective_attainable_score(proj.comparison_result)
            objective_attainable_score_str = f"{objective_attainable_score:.1f}" if objective_attainable_score is not None else ""
            
            # 使用发布时间（publish_time），已经正常提取，无需异常检查
            # 时间格式：只保留日期，舍去小时、分钟和秒
            if proj.publish_time:
                publish_time_str = proj.publish_time.strftime("%Y-%m-%d")
            else:
                # 如果发布时间为空，使用创建时间作为备选（极少情况）
                if hasattr(proj, 'create_time') and proj.create_time:
                    publish_time_str = proj.create_time.strftime("%Y-%m-%d")
                else:
                    publish_time_str = "未知"
            
            # 生成来源网站URL：优先使用download_url，如果没有则根据project_id生成，最后使用site_name
            source_url = ""
            if proj.download_url:
                source_url = proj.download_url
            elif hasattr(proj, 'project_id') and proj.project_id:
                # 如果有project_id，生成标准URL
                source_url = f"https://zfcg.czt.zj.gov.cn/site/detail?parentId=600007&articleId={proj.project_id}"
            else:
                # 最后使用site_name（可能是"本地上传"等文本）
                source_url = proj.site_name or ""
            
            data.append({
                "项目ID": proj.id,
                "项目名称": proj.project_name,
                "省份": province,
                "城市": city,
                "区域": proj.region or "未知",
                "采购类型": procurement_type,
                "来源网站": source_url,
                "发布时间": publish_time_str,
                "文件格式": proj.file_format or "",
                "状态": proj.status.value,
                "最终判定": final_decision,
                "客观分总分值": objective_attainable_score_str,
                "错误信息": proj.error_msg or "无"
            })
        return pd.DataFrame(data)

    def _get_qualified_projects(self, all_data):
        """筛选可参与项目

        说明：
        - 系统内部可能使用多种文案表示“推荐参与”，例如：
          - “可以参与”（早期版本）
          - “客观分满分”（基于评分逻辑的判定说明）
          - “推荐参与”（当前 AI 分析 run 方法使用的文案）
        - 这里统一视为“可参与”，后续如需新增文案，只需补充列表。
        """
        qualified_flags = ["可以参与", "客观分满分", "推荐参与"]
        return all_data[all_data["最终判定"].isin(qualified_flags)].copy()

    def _add_style_to_workbook(self, wb):
        """为Excel添加样式和自动筛选"""
        # 表头样式
        header_font = Font(name='微软雅黑', size=11, bold=True, color='FFFFFF')
        header_fill = PatternFill(start_color='4472C4', end_color='4472C4', fill_type='solid')
        # 对齐样式
        align_center = Alignment(horizontal='center', vertical='center')
        align_left = Alignment(horizontal='left', vertical='center')
        # 边框样式
        border = Border(
            left=Side(style='thin'), right=Side(style='thin'),
            top=Side(style='thin'), bottom=Side(style='thin')
        )

        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            
            # 设置列宽（根据实际列数动态调整）
            column_widths = {
                'A': 10,  # 项目ID
                'B': 40,  # 项目名称
                'C': 12,  # 省份
                'D': 12,  # 城市
                'E': 15,  # 区域
                'F': 12,  # 采购类型
                'G': 25,  # 来源网站
                'H': 18,  # 发布时间
                'I': 10,  # 文件格式
                'J': 10,  # 状态
                'K': 12,  # 最终判定
                'L': 15,  # 客观分总分值
                'M': 30,  # 错误信息
            }
            for col, width in column_widths.items():
                ws.column_dimensions[col].width = width

            # 为表头添加样式
            if ws.max_row > 0:
                for cell in ws[1]:
                    cell.font = header_font
                    cell.fill = header_fill
                    cell.alignment = align_center
                    cell.border = border

                # 为数据行添加边框和对齐
                for row in ws.iter_rows(min_row=2, max_row=ws.max_row):
                    for idx, cell in enumerate(row):
                        cell.border = border
                        # 项目名称左对齐，其他居中
                        if idx == 1:  # 项目名称列
                            cell.alignment = align_left
                        else:
                            cell.alignment = align_center

                # 添加自动筛选
                if ws.max_row > 1:
                    ws.auto_filter.ref = ws.dimensions

        return wb

    def generate_report(self, start_date=None, end_date=None, regions=None, procurement_types=None, platform_code=None, report_filename=None):
        """生成Excel报告（支持筛选）
        
        Args:
            start_date: 开始日期（datetime或date对象），None表示不限制
            end_date: 结束日期（datetime或date对象），None表示不限制
            regions: 区域列表（如["杭州市", "宁波市"]），None或空列表表示全选
            procurement_types: 采购类型列表（如["政府采购", "国企采购"]），None或空列表表示全选
            platform_code: 平台代码（如"zhejiang"、"hangzhou"），None表示全选
            report_filename: 报告文件名，None表示使用默认名称
        """
        try:
            log.info(f"开始生成报告：{self.report_date}")
            if start_date:
                log.info(f"时间范围：{start_date} 至 {end_date}")
            if regions and len(regions) > 0:
                log.info(f"筛选区域：{regions}")
            if procurement_types and len(procurement_types) > 0:
                log.info(f"筛选采购类型：{procurement_types}")
            if platform_code:
                log.info(f"筛选平台：{platform_code}")
            
            # 1. 获取数据（应用筛选条件）
            all_data = self._get_project_data(
                start_date=start_date,
                end_date=end_date,
                regions=regions,
                procurement_types=procurement_types,
                platform_code=platform_code
            )
            
            if len(all_data) == 0:
                raise ValueError("没有符合筛选条件的项目数据")

            # 2. 创建Excel工作簿
            wb = Workbook()
            # 删除默认工作表
            wb.remove(wb.active)

            # 3. 添加「项目列表」工作表
            ws = wb.create_sheet("项目列表")
            for r in dataframe_to_rows(all_data, index=False, header=True):
                ws.append(r)

            # 4. 添加样式和自动筛选
            wb = self._add_style_to_workbook(wb)

            # 5. 保存报告
            os.makedirs(REPORT_DIR, exist_ok=True)
            if report_filename:
                report_path = os.path.join(REPORT_DIR, report_filename)
            else:
                # 生成带时间戳的文件名
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                report_path = os.path.join(REPORT_DIR, f"标书资质匹配报告_{timestamp}.xlsx")
            
            wb.save(report_path)
            log.info(f"报告生成完成：{report_path}，共{len(all_data)}条记录")
            return report_path
        except Exception as e:
            log.error(f"报告生成失败：{str(e)}")
            raise


if __name__ == "__main__":
    generator = ReportGenerator()
    generator.generate_report()