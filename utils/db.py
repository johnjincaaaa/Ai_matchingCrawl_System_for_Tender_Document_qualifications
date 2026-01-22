from sqlalchemy import create_engine, Column, Integer, BigInteger, String, Text, DateTime, Enum, extract
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import enum
from config import DB_CONFIG, A_CERTIFICATE_CONFIG, B_RULE_CONFIG
from utils.log import log
import os
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# 创建数据库引擎
if DB_CONFIG["db_type"] == "postgresql":
    DB_URL = f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['db_name']}"
elif DB_CONFIG["db_type"] == "sqlite":
    DB_URL = f"sqlite:///{DB_CONFIG['db_path']}"
else:
    raise ValueError(f"不支持的数据库类型：{DB_CONFIG['db_type']}")

# 优化SQLite连接池配置，提高性能
if DB_CONFIG["db_type"] == "sqlite":
    # SQLite连接池优化：增加池大小，启用连接检查
    engine = create_engine(
        DB_URL, 
        echo=False,
        pool_size=5,  # 连接池大小
        max_overflow=10,  # 最大溢出连接数
        pool_pre_ping=True,  # 连接前检查连接是否有效
        connect_args={"check_same_thread": False}  # SQLite允许多线程
    )
else:
    # PostgreSQL连接池配置
    engine = create_engine(
        DB_URL,
        echo=False,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True
    )
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# 项目状态枚举
class ProjectStatus(str, enum.Enum):
    DOWNLOADED = "已下载"
    PARSED = "已解析"
    ANALYZED = "已分析"
    COMPARED = "已比对"
    ERROR = "异常"
    EXCLUDED = "已排除"

# 项目表模型
class TenderProject(Base):
    __tablename__ = "tender_projects"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_name = Column(String(512), nullable=False, comment="项目名称")
    site_name = Column(String(128), nullable=False, comment="来源网站")
    publish_time = Column(DateTime, nullable=False, comment="发布时间")
    publish_timestamp = Column(BigInteger, comment="发布时间戳（毫秒，原始API返回的时间戳）")
    download_url = Column(String(1024), comment="下载链接")
    file_path = Column(String(1024), comment="本地文件路径")
    file_format = Column(String(16), comment="文件格式")
    evaluation_content = Column(Text, comment="提取的评分表内容")
    ai_extracted_text = Column(Text, comment="AI提取的原始文本")
    project_requirements = Column(Text, comment="AI提取的资质要求")
    comparison_result = Column(Text, comment="资质比对结果")
    status = Column(Enum(ProjectStatus), default=ProjectStatus.DOWNLOADED, comment="项目状态")
    error_msg = Column(Text, comment="错误信息")
    create_time = Column(DateTime, default=datetime.now, comment="创建时间")
    update_time = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")
    project_id = Column(String(128), unique=True, comment="平台项目唯一标识（如articleId）")
    region = Column(String(64), comment="项目所属区域（如：浙江省本级、杭州市等）")
    final_decision = Column(String(32), default="未判定", comment="最终判定（可以参与/不可以参与）")
    tender_method = Column(String(64), comment="招标方式（如：最低价中标、综合评分法等）")
    objective_scores = Column(Text, comment="客观分项目列表（JSON格式）")
    subjective_scores = Column(Text, comment="主观分项目列表（JSON格式）")
    objective_score_decisions = Column(Text, comment="客观分条目判定结果（JSON格式）")
    all_objective_recommended = Column(Integer, default=0, comment="是否所有客观分条目均推荐：1-是，0-否")
    review_status = Column(String(32), default="待复核", comment="复核状态：待复核、已复核")
    review_result = Column(String(32), default="未确认", comment="复核结果：确认推荐、复核不推荐")
    review_reason = Column(Text, comment="复核原因")
    review_time = Column(DateTime, comment="复核时间")

# 公司资质表模型
class CompanyQualification(Base):
    __tablename__ = "company_qualifications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    category = Column(String(64), nullable=False, comment="资质类别：企业资质、人员资质、设备要求、业绩要求、其他要求")
    content = Column(Text, nullable=False, comment="资质内容")
    is_active = Column(Integer, default=1, comment="是否启用：1-启用，0-禁用")
    create_time = Column(DateTime, default=datetime.now, comment="创建时间")
    update_time = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")

# A类证书库表模型
class ClassACertificate(Base):
    __tablename__ = "class_a_certificates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    certificate_name = Column(String(256), nullable=False, comment="证书名称")
    certificate_number = Column(String(128), nullable=False, comment="认证标准")
    issuing_authority = Column(String(256), comment="查询机构")
    valid_from = Column(DateTime, comment="有效期开始时间")
    valid_until = Column(DateTime, comment="有效期结束时间")
    certificate_type = Column(String(64), comment="证书类型（如：质量管理体系认证、环境管理体系认证等）")
    is_active = Column(Integer, default=1, comment="是否有效：1-有效，0-无效")
    create_time = Column(DateTime, default=datetime.now, comment="创建时间")
    update_time = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")

# B类规则库表模型
class ClassBRule(Base):
    __tablename__ = "class_b_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    rule_name = Column(String(256), nullable=False, comment="规则名称")
    trigger_condition = Column(Text, nullable=False, comment="触发条件（描述该规则适用的场景）")
    conclusion = Column(Text, nullable=False, comment="结论（满足规则时的判定结果）")
    rule_type = Column(String(64), comment="规则类型（如：证书类、业绩类、检测报告类等）")
    is_active = Column(Integer, default=1, comment="是否启用：1-启用，0-禁用")
    create_time = Column(DateTime, default=datetime.now, comment="创建时间")
    update_time = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")

# 初始化数据库
def init_db():
    try:
        Base.metadata.create_all(bind=engine)
        
        # 性能优化：创建常用查询字段的索引
        from sqlalchemy import Index, inspect
        inspector = inspect(engine)
        existing_indexes = [idx['name'] for idx in inspector.get_indexes('tender_projects')] if 'tender_projects' in inspector.get_table_names() else []
        
        # 为常用查询字段创建索引（如果不存在）
        indexes_to_create = [
            ('idx_project_id', TenderProject.project_id),
            ('idx_status', TenderProject.status),
            ('idx_publish_time', TenderProject.publish_time),
            ('idx_final_decision', TenderProject.final_decision),
            ('idx_region', TenderProject.region),
        ]
        
        for index_name, column in indexes_to_create:
            if index_name not in existing_indexes:
                try:
                    Index(index_name, column).create(bind=engine)
                    log.info(f"创建索引成功：{index_name}")
                except Exception as e:
                    log.warning(f"创建索引失败 {index_name}：{str(e)}（可能已存在）")
        
        log.info("数据库初始化成功（包括索引）")
        
        # 添加默认数据
        db = SessionLocal()
        try:
            # 检查并添加A类证书默认数据
            if db.query(ClassACertificate).count() == 0:
                for cert_data in A_CERTIFICATE_CONFIG["default_certificates"]:
                    cert = ClassACertificate(**cert_data)
                    db.add(cert)
                db.commit()
                log.info(f"添加默认A类证书 {len(A_CERTIFICATE_CONFIG['default_certificates'])} 条")
            
            # 检查并添加B类规则默认数据
            if db.query(ClassBRule).count() == 0:
                for rule_data in B_RULE_CONFIG["default_rules"]:
                    rule = ClassBRule(**rule_data)
                    db.add(rule)
                db.commit()
                log.info(f"添加默认B类规则 {len(B_RULE_CONFIG['default_rules'])} 条")
                
        except Exception as e:
            db.rollback()
            log.error(f"添加默认数据失败：{str(e)}")
        finally:
            db.close()
            
    except Exception as e:
        log.error(f"数据库初始化失败：{str(e)}")
        raise

# 获取数据库会话
def get_db():
    """获取数据库会话，使用上下文管理器确保连接正确关闭"""
    db = None
    try:
        db = SessionLocal()
        yield db
    except Exception as e:
        log.error(f"数据库会话出错：{str(e)}")
        if db:
            db.rollback()
        raise
    finally:
        if db:
            try:
                db.close()
            except Exception as e:
                log.warning(f"关闭数据库连接时出错：{str(e)}")

# 保存项目数据
def save_project(db, project_data):
    try:
        # 检查项目是否已存在（通过project_id）
        project_id = project_data.get('project_id')
        if project_id:
            existing_project = db.query(TenderProject).filter_by(project_id=project_id).first()
            if existing_project:
                log.info(f"项目已存在（project_id: {project_id}），跳过保存：{project_data.get('project_name', 'Unknown')[:50]}")
                return existing_project
        
        # 验证 publish_time 是否存在（仅记录警告，不拒绝保存）
        if "publish_time" in project_data:
            publish_time = project_data["publish_time"]
            if publish_time:
                from datetime import datetime
                time_diff = abs((datetime.now() - publish_time).total_seconds())
                if time_diff < 60:  # 如果发布时间和当前时间过于接近（小于60秒）
                    log.warning(
                        f"⚠️  警告：publish_time ({publish_time.strftime('%Y-%m-%d %H:%M:%S')}) "
                        f"与当前时间过于接近（相差 {time_diff:.0f} 秒），可能是爬取时间而非实际发布时间。"
                        f"项目名: {project_data.get('project_name', 'Unknown')[:50]}。"
                        f"但仍会保存该项目。"
                    )
                else:
                    log.debug(
                        f"✓ 保存项目，发布时间: {publish_time.strftime('%Y-%m-%d %H:%M:%S')}, "
                        f"与当前时间相差: {time_diff/3600:.2f} 小时"
                    )
            else:
                log.warning(f"⚠️  警告：publish_time 为空: {project_data.get('project_name', 'Unknown')[:50]}。但仍会保存该项目。")
        else:
            log.warning(f"⚠️  警告：缺少 publish_time 字段: {project_data.get('project_name', 'Unknown')[:50]}。但仍会保存该项目。")
        
        project = TenderProject(**project_data)
        db.add(project)
        db.commit()
        db.refresh(project)
        
        log.info(f"项目保存成功：{project.project_name}（ID：{project.id}）")
        return project
    except Exception as e:
        db.rollback()
        log.error(f"项目保存失败：{str(e)}")
        raise

# 更新项目数据
def update_project(db, project_id, update_data):
    try:
        # 使用更高效的更新方式，直接更新指定字段
        result = db.query(TenderProject).filter(TenderProject.id == project_id).update(
            update_data,
            synchronize_session='evaluate'  # 使用evaluate确保会话同步，正确处理枚举类型
        )
        db.commit()
        log.info(f"项目更新成功：ID={project_id}，影响行数：{result}")
        return result > 0
    except Exception as e:
        db.rollback()
        log.error(f"项目更新失败：ID={project_id}，错误：{str(e)}")
        raise

# 公司资质管理函数

def get_company_qualifications(db):
    """获取所有启用的公司资质"""
    try:
        qualifications = db.query(CompanyQualification).filter(CompanyQualification.is_active == 1).all()
        # 按类别分组，确保每个content只出现一次
        grouped = {}
        for qual in qualifications:
            if qual.category not in grouped:
                grouped[qual.category] = []
            # 确保同一个类别下的content不重复
            if qual.content not in grouped[qual.category]:
                grouped[qual.category].append(qual.content)
        return grouped
    except Exception as e:
        log.error(f"获取公司资质失败：{str(e)}")
        raise

def add_company_qualification(db, category, content):
    """添加公司资质"""
    try:
        qualification = CompanyQualification(category=category, content=content)
        db.add(qualification)
        db.commit()
        db.refresh(qualification)
        log.info(f"添加公司资质成功：{category} - {content}")
        return qualification
    except Exception as e:
        db.rollback()
        log.error(f"添加公司资质失败：{str(e)}")
        raise

def update_company_qualification(db, qual_id, category=None, content=None, is_active=None):
    """更新公司资质"""
    try:
        update_data = {}
        if category is not None:
            update_data["category"] = category
        if content is not None:
            update_data["content"] = content
        if is_active is not None:
            update_data["is_active"] = is_active
            
        if update_data:
            db.query(CompanyQualification).filter(CompanyQualification.id == qual_id).update(update_data)
            db.commit()
            log.info(f"更新公司资质成功：ID={qual_id}")
        return True
    except Exception as e:
        db.rollback()
        log.error(f"更新公司资质失败：ID={qual_id}，错误：{str(e)}")
        raise

def delete_company_qualification(db, qual_id):
    """删除公司资质"""
    try:
        db.query(CompanyQualification).filter(CompanyQualification.id == qual_id).delete()
        db.commit()
        log.info(f"删除公司资质成功：ID={qual_id}")
        return True
    except Exception as e:
        db.rollback()
        log.error(f"删除公司资质失败：ID={qual_id}，错误：{str(e)}")
        raise

def batch_add_qualifications(db, qualifications):
    """批量添加公司资质"""
    try:
        for category, items in qualifications.items():
            for item in items:
                qualification = CompanyQualification(category=category, content=item)
                db.add(qualification)
        db.commit()
        log.info(f"批量添加公司资质成功")
        return True
    except Exception as e:
        db.rollback()
        log.error(f"批量添加公司资质失败：{str(e)}")
        raise

# A类证书库管理函数
def get_class_a_certificates(db, active_only=True):
    """获取A类证书"""
    try:
        query = db.query(ClassACertificate)
        if active_only:
            query = query.filter(ClassACertificate.is_active == 1)
        certificates = query.all()
        return certificates
    except Exception as e:
        log.error(f"获取A类证书失败：{str(e)}")
        raise

def add_class_a_certificate(db, certificate_name, certificate_number, issuing_authority=None, valid_from=None, valid_until=None, certificate_type=None):
    """添加A类证书"""
    try:
        certificate = ClassACertificate(
            certificate_name=certificate_name,
            certificate_number=certificate_number,
            issuing_authority=issuing_authority,
            valid_from=valid_from,
            valid_until=valid_until,
            certificate_type=certificate_type
        )
        db.add(certificate)
        db.commit()
        db.refresh(certificate)
        log.info(f"添加A类证书成功：{certificate_name} - {certificate_number}")
        return certificate
    except Exception as e:
        db.rollback()
        log.error(f"添加A类证书失败：{str(e)}")
        raise

def update_class_a_certificate(db, cert_id, certificate_name=None, certificate_number=None, issuing_authority=None, valid_from=None, valid_until=None, certificate_type=None, is_active=None):
    """更新A类证书"""
    try:
        update_data = {}
        if certificate_name is not None:
            update_data["certificate_name"] = certificate_name
        if certificate_number is not None:
            update_data["certificate_number"] = certificate_number
        if issuing_authority is not None:
            update_data["issuing_authority"] = issuing_authority
        if valid_from is not None:
            update_data["valid_from"] = valid_from
        if valid_until is not None:
            update_data["valid_until"] = valid_until
        if certificate_type is not None:
            update_data["certificate_type"] = certificate_type
        if is_active is not None:
            update_data["is_active"] = is_active
            
        if update_data:
            db.query(ClassACertificate).filter(ClassACertificate.id == cert_id).update(update_data)
            db.commit()
            log.info(f"更新A类证书成功：ID={cert_id}")
        return True
    except Exception as e:
        db.rollback()
        log.error(f"更新A类证书失败：ID={cert_id}，错误：{str(e)}")
        raise

def delete_class_a_certificate(db, cert_id):
    """删除A类证书"""
    try:
        db.query(ClassACertificate).filter(ClassACertificate.id == cert_id).delete()
        db.commit()
        log.info(f"删除A类证书成功：ID={cert_id}")
        return True
    except Exception as e:
        db.rollback()
        log.error(f"删除A类证书失败：ID={cert_id}，错误：{str(e)}")
        raise

# B类规则库管理函数
def get_class_b_rules(db, active_only=True):
    """获取B类规则"""
    try:
        query = db.query(ClassBRule)
        if active_only:
            query = query.filter(ClassBRule.is_active == 1)
        rules = query.all()
        return rules
    except Exception as e:
        log.error(f"获取B类规则失败：{str(e)}")
        raise

def add_class_b_rule(db, rule_name, trigger_condition, conclusion, rule_type=None):
    """添加B类规则"""
    try:
        rule = ClassBRule(
            rule_name=rule_name,
            trigger_condition=trigger_condition,
            conclusion=conclusion,
            rule_type=rule_type
        )
        db.add(rule)
        db.commit()
        db.refresh(rule)
        log.info(f"添加B类规则成功：{rule_name}")
        return rule
    except Exception as e:
        db.rollback()
        log.error(f"添加B类规则失败：{str(e)}")
        raise

def update_class_b_rule(db, rule_id, rule_name=None, trigger_condition=None, conclusion=None, rule_type=None, is_active=None):
    """更新B类规则"""
    try:
        update_data = {}
        if rule_name is not None:
            update_data["rule_name"] = rule_name
        if trigger_condition is not None:
            update_data["trigger_condition"] = trigger_condition
        if conclusion is not None:
            update_data["conclusion"] = conclusion
        if rule_type is not None:
            update_data["rule_type"] = rule_type
        if is_active is not None:
            update_data["is_active"] = is_active
            
        if update_data:
            db.query(ClassBRule).filter(ClassBRule.id == rule_id).update(update_data)
            db.commit()
            log.info(f"更新B类规则成功：ID={rule_id}")
        return True
    except Exception as e:
        db.rollback()
        log.error(f"更新B类规则失败：ID={rule_id}，错误：{str(e)}")
        raise

def delete_class_b_rule(db, rule_id):
    """删除B类规则"""
    try:
        db.query(ClassBRule).filter(ClassBRule.id == rule_id).delete()
        db.commit()
        log.info(f"删除B类规则成功：ID={rule_id}")
        return True
    except Exception as e:
        db.rollback()
        log.error(f"删除B类规则失败：ID={rule_id}，错误：{str(e)}")
        raise

# 初始化数据库
init_db()
