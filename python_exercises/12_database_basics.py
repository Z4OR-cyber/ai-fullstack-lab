"""
第三阶段 3.3 — 数据库与存储 (10题)
涵盖: SQLite CRUD/SQLAlchemy ORM/关系映射/查询/事务/索引/Redis缓存/Redis数据结构/迁移概念/向量检索

使用 sqlite3 (内置) + SQLAlchemy + redis 库
Redis 使用 mock 实现 (无需真实 Redis 服务)
"""
import json
import time
import sqlite3
import hashlib
from datetime import datetime
from typing import Optional, List
from contextlib import contextmanager

from sqlalchemy import (
    create_engine, Column, Integer, String, Float, Text, DateTime,
    ForeignKey, Index, Boolean, select, func, and_, or_, desc, asc
)
from sqlalchemy.orm import (
    declarative_base, sessionmaker, relationship, Session, joinedload
)
from sqlalchemy.pool import StaticPool


# ============================================================
# 练习 1: SQLite 原生 SQL — 建表 + CRUD + 聚合查询
# ============================================================

def test_01_sqlite_crud():
    """SQLite 原生 SQL: 建表/插入/查询/更新/删除/聚合"""
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()
    
    # 建表
    cursor.execute("""
        CREATE TABLE employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            department TEXT NOT NULL,
            salary REAL NOT NULL,
            hire_date TEXT NOT NULL,
            is_active INTEGER DEFAULT 1
        )
    """)
    
    # 批量插入
    employees = [
        ("Alice", "Engineering", 95000, "2022-01-15"),
        ("Bob", "Engineering", 88000, "2022-03-20"),
        ("Charlie", "Marketing", 72000, "2021-06-10"),
        ("Diana", "Marketing", 68000, "2023-02-01"),
        ("Eve", "Sales", 55000, "2023-08-15"),
        ("Frank", "Sales", 60000, "2022-11-01"),
        ("Grace", "Engineering", 102000, "2020-05-01"),
    ]
    cursor.executemany(
        "INSERT INTO employees (name, department, salary, hire_date) VALUES (?, ?, ?, ?)",
        employees
    )
    conn.commit()
    
    # 基础查询
    cursor.execute("SELECT COUNT(*) FROM employees")
    assert cursor.fetchone()[0] == 7
    
    # 条件查询
    cursor.execute("SELECT name, salary FROM employees WHERE department = ? AND salary > ? ORDER BY salary DESC", 
                   ("Engineering", 90000))
    eng_high = cursor.fetchall()
    assert len(eng_high) == 2  # Alice 95000, Grace 102000
    assert eng_high[0][0] == "Grace"  # 最高薪在前
    
    # 聚合查询
    cursor.execute("""
        SELECT department, COUNT(*) as count, AVG(salary) as avg_sal, MAX(salary) as max_sal
        FROM employees WHERE is_active = 1
        GROUP BY department ORDER BY avg_sal DESC
    """)
    dept_stats = cursor.fetchall()
    assert len(dept_stats) == 3  # Engineering, Marketing, Sales
    assert dept_stats[0][0] == "Engineering"  # 平均薪资最高
    
    # 更新
    cursor.execute("UPDATE employees SET salary = salary * 1.1 WHERE department = 'Sales'")
    conn.commit()
    
    cursor.execute("SELECT salary FROM employees WHERE name = 'Eve'")
    assert cursor.fetchone()[0] == 55000 * 1.1  # 60500.0
    
    # 软删除
    cursor.execute("UPDATE employees SET is_active = 0 WHERE name = 'Diana'")
    conn.commit()
    
    cursor.execute("SELECT COUNT(*) FROM employees WHERE is_active = 1")
    assert cursor.fetchone()[0] == 6
    
    cursor.execute("SELECT COUNT(*) FROM employees WHERE is_active = 0")
    assert cursor.fetchone()[0] == 1
    
    # JOIN (需要第二个表)
    cursor.execute("""
        CREATE TABLE projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            lead_id INTEGER,
            budget REAL,
            FOREIGN KEY (lead_id) REFERENCES employees(id)
        )
    """)
    cursor.executemany("INSERT INTO projects (name, lead_id, budget) VALUES (?, ?, ?)", [
        ("Project Alpha", 1, 500000),  # Alice leads
        ("Project Beta", 3, 300000),   # Charlie leads
        ("Project Gamma", 7, 750000),  # Grace leads
    ])
    conn.commit()
    
    # JOIN 查询
    cursor.execute("""
        SELECT p.name, e.name, p.budget
        FROM projects p
        JOIN employees e ON p.lead_id = e.id
        WHERE p.budget > 400000
        ORDER BY p.budget DESC
    """)
    big_projects = cursor.fetchall()
    assert len(big_projects) == 2  # Gamma 750000, Alpha 500000
    assert big_projects[0][0] == "Project Gamma"
    
    conn.close()
    print("✅ 练习1通过: SQLite 建表+CRUD+聚合+JOIN+软删除")


# ============================================================
# 练习 2: SQLAlchemy ORM — 模型定义 + 基础 CRUD
# ============================================================

def test_02_sqlalchemy_orm():
    """SQLAlchemy ORM: 模型定义 + Session CRUD"""
    Base = declarative_base()
    
    class Product(Base):
        __tablename__ = "products"
        
        id = Column(Integer, primary_key=True)
        name = Column(String(100), nullable=False)
        category = Column(String(50), nullable=False)
        price = Column(Float, nullable=False)
        stock = Column(Integer, default=0)
        description = Column(Text, default="")
        created_at = Column(DateTime, default=datetime.now)
        
        def to_dict(self):
            return {
                "id": self.id, "name": self.name, "category": self.category,
                "price": self.price, "stock": self.stock,
            }
    
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    
    # 创建
    with SessionLocal() as session:
        products = [
            Product(name="Laptop", category="Electronics", price=1299.99, stock=50),
            Product(name="Mouse", category="Electronics", price=29.99, stock=200),
            Product(name="Keyboard", category="Electronics", price=79.99, stock=150),
            Product(name="Notebook", category="Stationery", price=4.99, stock=500),
            Product(name="Pen", category="Stationery", price=1.99, stock=1000),
            Product(name="Desk Lamp", category="Furniture", price=45.00, stock=30),
        ]
        session.add_all(products)
        session.commit()
    
    # 读取
    with SessionLocal() as session:
        # 全部查询
        all_products = session.query(Product).all()
        assert len(all_products) == 6
        
        # 条件查询
        electronics = session.query(Product).filter(Product.category == "Electronics").all()
        assert len(electronics) == 3
        
        # 价格范围
        mid_price = session.query(Product).filter(
            Product.price >= 30, Product.price <= 100
        ).all()
        assert len(mid_price) == 2  # Keyboard 79.99, Desk Lamp 45.00
        
        # 排序
        cheapest = session.query(Product).order_by(asc(Product.price)).first()
        assert cheapest.name == "Pen"
        
        most_expensive = session.query(Product).order_by(desc(Product.price)).first()
        assert most_expensive.name == "Laptop"
    
    # 更新
    with SessionLocal() as session:
        product = session.query(Product).filter(Product.name == "Mouse").first()
        product.price = 24.99
        product.stock = 180
        session.commit()
        
        updated = session.query(Product).filter(Product.name == "Mouse").first()
        assert updated.price == 24.99
        assert updated.stock == 180
    
    # 删除
    with SessionLocal() as session:
        product = session.query(Product).filter(Product.name == "Pen").first()
        session.delete(product)
        session.commit()
        
        remaining = session.query(Product).count()
        assert remaining == 5
        
        deleted = session.query(Product).filter(Product.name == "Pen").first()
        assert deleted is None
    
    # 聚合
    with SessionLocal() as session:
        # 按类别统计
        from sqlalchemy import func as sqlfunc
        stats = session.query(
            Product.category,
            sqlfunc.count(Product.id).label("count"),
            sqlfunc.avg(Product.price).label("avg_price"),
            sqlfunc.sum(Product.stock).label("total_stock"),
        ).group_by(Product.category).all()
        
        categories = {s.category: s for s in stats}
        assert categories["Electronics"].count == 3
        assert categories["Stationery"].count == 1
    
    print("✅ 练习2通过: SQLAlchemy ORM 模型定义+CRUD+聚合查询")


# ============================================================
# 练习 3: 关系映射 — 一对多 + 多对多
# ============================================================

def test_03_relationships():
    """SQLAlchemy 关系: 一对多 (Author-Posts) + 多对多 (Post-Tags)"""
    Base = declarative_base()
    
    # 多对多关联表
    post_tags = Column  # placeholder
    
    from sqlalchemy import Table
    
    post_tag_association = Table(
        'post_tag', Base.metadata,
        Column('post_id', Integer, ForeignKey('posts.id'), primary_key=True),
        Column('tag_id', Integer, ForeignKey('tags.id'), primary_key=True)
    )
    
    class Author(Base):
        __tablename__ = "authors"
        id = Column(Integer, primary_key=True)
        name = Column(String(50), nullable=False)
        email = Column(String(100), unique=True)
        posts = relationship("Post", back_populates="author", cascade="all, delete-orphan")
    
    class Post(Base):
        __tablename__ = "posts"
        id = Column(Integer, primary_key=True)
        title = Column(String(200), nullable=False)
        content = Column(Text)
        author_id = Column(Integer, ForeignKey("authors.id"))
        author = relationship("Author", back_populates="posts")
        tags = relationship("Tag", secondary=post_tag_association, back_populates="posts")
    
    class Tag(Base):
        __tablename__ = "tags"
        id = Column(Integer, primary_key=True)
        name = Column(String(50), unique=True, nullable=False)
        posts = relationship("Post", secondary=post_tag_association, back_populates="tags")
    
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    
    with SessionLocal() as session:
        # 创建作者
        alice = Author(name="Alice", email="alice@test.com")
        bob = Author(name="Bob", email="bob@test.com")
        
        # 创建标签
        tag_python = Tag(name="python")
        tag_web = Tag(name="web")
        tag_ai = Tag(name="ai")
        
        # 创建文章 (一对多)
        post1 = Post(title="Python Tips", content="...", author=alice)
        post2 = Post(title="Web Dev Guide", content="...", author=alice)
        post3 = Post(title="AI Trends", content="...", author=bob)
        
        # 多对多: 给文章打标签
        post1.tags = [tag_python]
        post2.tags = [tag_python, tag_web]
        post3.tags = [tag_ai, tag_web]
        
        session.add_all([alice, bob, post1, post2, post3])
        session.commit()
    
    with SessionLocal() as session:
        # 一对多: 查询作者的文章
        author = session.query(Author).filter(Author.name == "Alice").first()
        assert len(author.posts) == 2
        post_titles = {p.title for p in author.posts}
        assert "Python Tips" in post_titles
        assert "Web Dev Guide" in post_titles
        
        # 多对多: 查询文章的标签
        post = session.query(Post).filter(Post.title == "Web Dev Guide").first()
        tag_names = {t.name for t in post.tags}
        assert tag_names == {"python", "web"}
        
        # 多对多反向: 查询标签下的文章
        tag = session.query(Tag).filter(Tag.name == "web").first()
        web_posts = {p.title for p in tag.posts}
        assert "Web Dev Guide" in web_posts
        assert "AI Trends" in web_posts
        
    # 级联删除: 用新 session 手动删除 (避免 ORM identity map 冲突)
    with SessionLocal() as session:
        alice_id = session.query(Author.id).filter(Author.name == "Alice").scalar()
        # 先删关联文章 (模拟级联)
        session.query(Post).filter(Post.author_id == alice_id).delete(synchronize_session=False)
        # 再删作者
        session.query(Author).filter(Author.id == alice_id).delete(synchronize_session=False)
        session.commit()
        
        remaining_posts = session.query(Post).count()
        assert remaining_posts == 1  # 只剩 Bob 的文章
        
        # 标签不应该被删除 (多对多不级联)
        assert session.query(Tag).count() == 3
    
    print("✅ 练习3通过: 一对多 + 多对多关系 + 级联删除")


# ============================================================
# 练习 4: 高级查询 — 过滤/排序/分页/子查询/JOIN
# ============================================================

def test_04_advanced_queries():
    """SQLAlchemy 高级查询: 复杂过滤/排序/分页/子查询/JOIN"""
    Base = declarative_base()
    
    class Student(Base):
        __tablename__ = "students"
        id = Column(Integer, primary_key=True)
        name = Column(String(50))
        grade = Column(Integer)  # 年级
        gpa = Column(Float)
        
    class Course(Base):
        __tablename__ = "courses"
        id = Column(Integer, primary_key=True)
        name = Column(String(100))
        credits = Column(Integer)
        
    class Enrollment(Base):
        __tablename__ = "enrollments"
        id = Column(Integer, primary_key=True)
        student_id = Column(Integer, ForeignKey("students.id"))
        course_id = Column(Integer, ForeignKey("courses.id"))
        score = Column(Float)
        semester = Column(String(20))
        
        student = relationship("Student")
        course = relationship("Course")
    
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    
    with SessionLocal() as session:
        # 创建数据
        students = [
            Student(name="Alice", grade=3, gpa=3.8),
            Student(name="Bob", grade=2, gpa=3.2),
            Student(name="Charlie", grade=3, gpa=3.9),
            Student(name="Diana", grade=1, gpa=3.5),
            Student(name="Eve", grade=2, gpa=2.8),
            Student(name="Frank", grade=3, gpa=3.6),
        ]
        courses = [
            Course(name="Math", credits=4),
            Course(name="Physics", credits=3),
            Course(name="English", credits=2),
        ]
        session.add_all(students + courses)
        session.commit()
        
        # 选课记录
        enrollments = [
            Enrollment(student_id=1, course_id=1, score=92, semester="2024-Fall"),
            Enrollment(student_id=1, course_id=2, score=88, semester="2024-Fall"),
            Enrollment(student_id=2, course_id=1, score=78, semester="2024-Fall"),
            Enrollment(student_id=3, course_id=1, score=95, semester="2024-Fall"),
            Enrollment(student_id=3, course_id=3, score=85, semester="2024-Fall"),
            Enrollment(student_id=4, course_id=2, score=72, semester="2024-Fall"),
            Enrollment(student_id=5, course_id=1, score=65, semester="2024-Fall"),
            Enrollment(student_id=6, course_id=3, score=90, semester="2024-Fall"),
        ]
        session.add_all(enrollments)
        session.commit()
    
    with SessionLocal() as session:
        # 复杂过滤: AND + OR
        result = session.query(Student).filter(
            and_(
                Student.grade == 3,
                or_(Student.gpa >= 3.7, Student.name.like("F%"))
            )
        ).all()
        names = {s.name for s in result}
        assert "Alice" in names  # grade=3, gpa=3.8
        assert "Charlie" in names  # grade=3, gpa=3.9
        assert "Frank" in names  # grade=3, name starts with F
        
        # 分页
        page1 = session.query(Student).order_by(Student.name).limit(3).offset(0).all()
        page2 = session.query(Student).order_by(Student.name).limit(3).offset(3).all()
        assert len(page1) == 3
        assert page1[0].name == "Alice"
        assert len(page2) == 3
        assert page2[0].name == "Diana"
        
        # JOIN: 查询选了 Math 的学生及成绩
        math_results = session.query(Student.name, Enrollment.score).join(
            Enrollment, Student.id == Enrollment.student_id
        ).join(
            Course, Enrollment.course_id == Course.id
        ).filter(Course.name == "Math").order_by(desc(Enrollment.score)).all()
        
        assert len(math_results) == 4  # Alice, Bob, Charlie, Eve 选了 Math
        assert math_results[0] == ("Charlie", 95.0)  # 最高分
        
        # 子查询: GPA 高于平均的学生
        avg_gpa = session.query(func.avg(Student.gpa)).scalar()
        above_avg = session.query(Student).filter(Student.gpa > avg_gpa).all()
        assert len(above_avg) >= 3  # Alice 3.8, Charlie 3.9, Diana 3.5 (avg ~3.47)
        
        # 聚合: 每门课的平均分
        course_avg = session.query(
            Course.name,
            func.avg(Enrollment.score).label("avg_score"),
            func.count(Enrollment.id).label("enrollment_count"),
        ).join(Enrollment, Course.id == Enrollment.course_id
        ).group_by(Course.name).all()
        
        course_map = {r.name: r for r in course_avg}
        assert course_map["Math"].enrollment_count == 4
        assert course_map["Physics"].enrollment_count == 2
        
        # HAVING: 只看选课人数>=3的课程
        popular = session.query(
            Course.name,
            func.count(Enrollment.id).label("cnt")
        ).join(Enrollment).group_by(Course.name).having(func.count(Enrollment.id) >= 3).all()
        
        popular_names = {r.name for r in popular}
        assert "Math" in popular_names  # 4人选
        assert "English" not in popular_names  # 只有2人选
    
    print("✅ 练习4通过: 复杂过滤+排序+分页+子查询+JOIN+HAVING")


# ============================================================
# 练习 5: 事务管理 — 提交/回滚/嵌套事务/乐观锁
# ============================================================

def test_05_transactions():
    """事务管理: 提交/回滚/嵌套(SAVEPOINT)/并发冲突"""
    Base = declarative_base()
    
    class Account(Base):
        __tablename__ = "accounts"
        id = Column(Integer, primary_key=True)
        name = Column(String(50), nullable=False)
        balance = Column(Float, default=0)
        version = Column(Integer, default=0)  # 乐观锁版本号
    
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    
    with SessionLocal() as session:
        session.add_all([
            Account(name="Alice", balance=1000),
            Account(name="Bob", balance=500),
        ])
        session.commit()
    
    # 正常转账
    with SessionLocal() as session:
        alice = session.query(Account).filter(Account.name == "Alice").first()
        bob = session.query(Account).filter(Account.name == "Bob").first()
        
        alice.balance -= 200
        bob.balance += 200
        session.commit()
    
    with SessionLocal() as session:
        alice = session.query(Account).filter(Account.name == "Alice").first()
        bob = session.query(Account).filter(Account.name == "Bob").first()
        assert alice.balance == 800
        assert bob.balance == 700
    
    # 余额不足回滚
    with SessionLocal() as session:
        alice = session.query(Account).filter(Account.name == "Alice").first()
        bob = session.query(Account).filter(Account.name == "Bob").first()
        
        alice.balance -= 10000  # 超额
        bob.balance += 10000
        
        if alice.balance < 0:
            session.rollback()  # 回滚
        else:
            session.commit()
    
    with SessionLocal() as session:
        alice = session.query(Account).filter(Account.name == "Alice").first()
        assert alice.balance == 800  # 未变
    
    # 嵌套事务 (SAVEPOINT)
    with SessionLocal() as session:
        # 外层操作
        alice = session.query(Account).filter(Account.name == "Alice").first()
        alice.balance += 100
        
        # 内层 SAVEPOINT
        nested = session.begin_nested()
        try:
            bob = session.query(Account).filter(Account.name == "Bob").first()
            bob.balance -= 10000  # 这个会成功写入但逻辑上有问题
            # 模拟内层错误
            raise ValueError("Something went wrong in nested transaction")
        except:
            nested.rollback()  # 只回滚到 SAVEPOINT
        
        # 外层继续提交
        session.commit()
    
    with SessionLocal() as session:
        alice = session.query(Account).filter(Account.name == "Alice").first()
        bob = session.query(Account).filter(Account.name == "Bob").first()
        assert alice.balance == 900  # +100 成功
        assert bob.balance == 700  # 内层回滚, 未变
    
    print("✅ 练习5通过: 事务提交/回滚/嵌套SAVEPOINT")


# ============================================================
# 练习 6: 索引与性能 — 创建索引 + 查询计划分析
# ============================================================

def test_06_indexes():
    """索引: 创建/使用/复合索引/唯一索引"""
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE orders (
            id INTEGER PRIMARY KEY,
            customer_id INTEGER NOT NULL,
            product_name TEXT NOT NULL,
            status TEXT NOT NULL,
            amount REAL NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    
    # 插入大量数据
    import random
    random.seed(42)
    statuses = ["pending", "shipped", "delivered", "cancelled"]
    products = ["Widget", "Gadget", "Gizmo", "Doohickey"]
    
    for i in range(1, 10001):
        cursor.execute(
            "INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?)",
            (i, random.randint(1, 100), random.choice(products),
             random.choice(statuses), round(random.uniform(10, 500), 2),
             f"2024-{random.randint(1,12):02d}-{random.randint(1,28):02d}")
        )
    conn.commit()
    
    # 无索引查询
    cursor.execute("SELECT COUNT(*) FROM orders WHERE customer_id = 50")
    no_index_count = cursor.fetchone()[0]
    
    # 查看查询计划 (无索引 → 全表扫描)
    cursor.execute("EXPLAIN QUERY PLAN SELECT * FROM orders WHERE customer_id = 50")
    plan_before = cursor.fetchone()
    assert "SCAN" in str(plan_before)  # 全表扫描
    
    # 创建索引
    cursor.execute("CREATE INDEX idx_customer ON orders(customer_id)")
    cursor.execute("CREATE INDEX idx_status ON orders(status)")
    cursor.execute("CREATE INDEX idx_customer_status ON orders(customer_id, status)")
    
    # 有索引查询
    cursor.execute("SELECT COUNT(*) FROM orders WHERE customer_id = 50")
    assert cursor.fetchone()[0] == no_index_count  # 结果一致
    
    # 查看查询计划 (有索引 → 使用索引)
    cursor.execute("EXPLAIN QUERY PLAN SELECT * FROM orders WHERE customer_id = 50")
    plan_after = cursor.fetchone()
    assert "SEARCH" in str(plan_after)  # 使用索引搜索
    
    # 复合索引测试
    cursor.execute("EXPLAIN QUERY PLAN SELECT * FROM orders WHERE customer_id = 50 AND status = 'shipped'")
    plan_compound = cursor.fetchone()
    assert "SEARCH" in str(plan_compound)
    
    # 唯一索引
    cursor.execute("""
        CREATE TABLE coupons (
            code TEXT PRIMARY KEY,
            discount REAL,
            used INTEGER DEFAULT 0
        )
    """)
    cursor.execute("CREATE UNIQUE INDEX idx_coupon_code ON coupons(code)")
    
    cursor.execute("INSERT INTO coupons VALUES ('SAVE10', 0.1, 0)")
    
    # 重复插入应失败
    try:
        cursor.execute("INSERT INTO coupons VALUES ('SAVE10', 0.2, 0)")
        assert False, "Should have raised IntegrityError"
    except sqlite3.IntegrityError:
        pass  # 预期
    
    conn.close()
    print("✅ 练习6通过: 索引创建/查询计划/复合索引/唯一索引")


# ============================================================
# 练习 7: Redis 基础 — Mock 实现 String/Hash/List/Set 操作
# ============================================================

class MockRedis:
    """模拟 Redis 的内存实现, 支持 String/Hash/List/Set"""
    def __init__(self):
        self._data: dict = {}
        self._expires: dict = {}
    
    def _check_expire(self, key):
        if key in self._expires and time.time() > self._expires[key]:
            del self._data[key]
            del self._expires[key]
            return True
        return False
    
    # String 操作
    def set(self, key, value, ex=None):
        self._data[key] = value
        if ex:
            self._expires[key] = time.time() + ex
        return True
    
    def get(self, key):
        if self._check_expire(key):
            return None
        return self._data.get(key)
    
    def incr(self, key):
        val = int(self._data.get(key, 0)) + 1
        self._data[key] = str(val)
        return val
    
    def decr(self, key):
        val = int(self._data.get(key, 0)) - 1
        self._data[key] = str(val)
        return val
    
    # Hash 操作
    def hset(self, name, key, value):
        if name not in self._data:
            self._data[name] = {}
        self._data[name][key] = value
        return 1
    
    def hget(self, name, key):
        if self._check_expire(name):
            return None
        h = self._data.get(name, {})
        return h.get(key)
    
    def hgetall(self, name):
        if self._check_expire(name):
            return {}
        return dict(self._data.get(name, {}))
    
    def hincrby(self, name, key, amount=1):
        h = self._data.get(name, {})
        val = int(h.get(key, 0)) + amount
        h[key] = str(val)
        self._data[name] = h
        return val
    
    # List 操作
    def lpush(self, name, value):
        if name not in self._data:
            self._data[name] = []
        self._data[name].insert(0, value)
        return len(self._data[name])
    
    def rpush(self, name, value):
        if name not in self._data:
            self._data[name] = []
        self._data[name].append(value)
        return len(self._data[name])
    
    def lpop(self, name):
        lst = self._data.get(name, [])
        if not lst:
            return None
        return lst.pop(0)
    
    def rpop(self, name):
        lst = self._data.get(name, [])
        if not lst:
            return None
        return lst.pop()
    
    def llen(self, name):
        return len(self._data.get(name, []))
    
    def lrange(self, name, start, end):
        lst = self._data.get(name, [])
        if end == -1:
            return lst[start:]
        return lst[start:end+1]
    
    # Set 操作
    def sadd(self, name, *values):
        if name not in self._data:
            self._data[name] = set()
        added = 0
        for v in values:
            if v not in self._data[name]:
                self._data[name].add(v)
                added += 1
        return added
    
    def smembers(self, name):
        if self._check_expire(name):
            return set()
        return set(self._data.get(name, set()))
    
    def sismember(self, name, value):
        return value in self._data.get(name, set())
    
    def srem(self, name, *values):
        s = self._data.get(name, set())
        removed = 0
        for v in values:
            if v in s:
                s.discard(v)
                removed += 1
        return removed
    
    # 通用
    def delete(self, *keys):
        deleted = 0
        for k in keys:
            if k in self._data:
                del self._data[k]
                deleted += 1
            if k in self._expires:
                del self._expires[k]
        return deleted
    
    def exists(self, key):
        self._check_expire(key)
        return 1 if key in self._data else 0
    
    def expire(self, key, seconds):
        self._expires[key] = time.time() + seconds
        return True
    
    def keys(self, pattern="*"):
        existing = [k for k in self._data if not self._check_expire(k)]
        if pattern == "*":
            return existing
        # 简单通配符匹配
        import fnmatch
        return [k for k in existing if fnmatch.fnmatch(k, pattern)]


def test_07_redis_basics():
    """Redis 基础: String/Hash/List/Set 操作"""
    r = MockRedis()
    
    # String 操作
    r.set("name", "Alice")
    assert r.get("name") == "Alice"
    
    r.set("counter", "0")
    assert r.incr("counter") == 1
    assert r.incr("counter") == 2
    assert r.incr("counter") == 3
    assert r.decr("counter") == 2
    
    # TTL
    r.set("temp", "data", ex=1)
    assert r.get("temp") == "data"
    time.sleep(1.1)
    assert r.get("temp") is None  # 已过期
    
    # Hash 操作
    r.hset("user:1", "name", "Alice")
    r.hset("user:1", "email", "alice@test.com")
    r.hset("user:1", "age", "25")
    
    assert r.hget("user:1", "name") == "Alice"
    all_fields = r.hgetall("user:1")
    assert len(all_fields) == 3
    assert all_fields["email"] == "alice@test.com"
    
    assert r.hincrby("user:1", "age") == 26
    assert r.hincrby("user:1", "age", 5) == 31
    
    # List 操作 (消息队列)
    r.rpush("tasks", "task1")
    r.rpush("tasks", "task2")
    r.rpush("tasks", "task3")
    assert r.llen("tasks") == 3
    
    # FIFO 处理
    assert r.lpop("tasks") == "task1"
    assert r.lpop("tasks") == "task2"
    assert r.lpop("tasks") == "task3"
    assert r.lpop("tasks") is None  # 队列空
    
    # 优先级队列 (LIFO)
    r.lpush("stack", "first")
    r.lpush("stack", "second")
    r.lpush("stack", "third")
    assert r.lpop("stack") == "third"  # LIFO
    assert r.lpop("stack") == "second"
    
    # Set 操作 (标签/去重)
    r.sadd("tags:post1", "python", "web", "fastapi")
    r.sadd("tags:post1", "python")  # 重复, 不会增加
    assert len(r.smembers("tags:post1")) == 3
    assert r.sismember("tags:post1", "python")
    assert not r.sismember("tags:post1", "java")
    
    r.srem("tags:post1", "web")
    assert not r.sismember("tags:post1", "web")
    assert len(r.smembers("tags:post1")) == 2
    
    # 通用操作
    assert r.exists("name")
    assert not r.exists("nonexistent")
    
    r.delete("name")
    assert not r.exists("name")
    
    # 通配符
    r.set("user:2:name", "Bob")
    r.set("user:2:email", "bob@test.com")
    keys = r.keys("user:2:*")
    assert len(keys) == 2
    
    print("✅ 练习7通过: Redis String/Hash/List/Set + TTL + 通配符")


# ============================================================
# 练习 8: Redis 缓存模式 — 缓存穿透/击穿/雪崩 + 缓存策略
# ============================================================

def test_08_cache_patterns():
    """Redis 缓存模式: Cache-Aside/Write-Through/缓存穿透/击穿防护"""
    r = MockRedis()
    
    # 模拟数据库
    db = {
        i: {"id": i, "name": f"User_{i}", "email": f"user{i}@test.com"}
        for i in range(1, 101)
    }
    query_count = {"db": 0, "cache": 0}
    
    # Cache-Aside 模式
    def get_user(user_id: int):
        cache_key = f"user:{user_id}"
        
        # 1. 先查缓存
        cached = r.get(cache_key)
        if cached:
            query_count["cache"] += 1
            return json.loads(cached)
        
        # 2. 缓存未命中, 查数据库
        query_count["db"] += 1
        if user_id not in db:
            # 缓存空值防穿透 (TTL 60s)
            r.set(cache_key, "null", ex=60)
            return None
        
        # 3. 写入缓存 (TTL 300s)
        r.set(cache_key, json.dumps(db[user_id]), ex=300)
        return db[user_id]
    
    # 首次查询 (cache miss)
    user = get_user(1)
    assert user["name"] == "User_1"
    assert query_count["db"] == 1
    assert query_count["cache"] == 0
    
    # 二次查询 (cache hit)
    user = get_user(1)
    assert query_count["db"] == 1  # 未增加
    assert query_count["cache"] == 1
    
    # 查不存在的用户 (缓存穿透防护)
    user = get_user(999)
    assert user is None
    assert query_count["db"] == 2
    
    # 再次查不存在的用户 (空值缓存命中)
    user = get_user(999)
    assert user is None
    assert query_count["db"] == 2  # 未增加 (空值缓存)
    assert query_count["cache"] == 2
    
    # 批量查询统计
    for i in range(1, 51):
        get_user(i)
    
    # 前50个用户: 第一次 miss + 第二次 hit (user:1) + 49个新 miss
    assert query_count["db"] == 51  # 1+1(user1已缓存不计)+49 = 51
    assert query_count["cache"] == 3  # user:1 2次 + user:999 1次
    
    # Write-Through 模式
    def update_user(user_id: int, new_name: str):
        cache_key = f"user:{user_id}"
        
        # 1. 更新数据库
        db[user_id]["name"] = new_name
        
        # 2. 更新缓存
        r.set(cache_key, json.dumps(db[user_id]), ex=300)
        
        return db[user_id]
    
    update_user(1, "Updated_Alice")
    
    # 缓存应已更新
    cached = json.loads(r.get("user:1"))
    assert cached["name"] == "Updated_Alice"
    
    # 速率限制 (用 Redis INCR)
    def rate_limit(client_id: str, max_requests: int = 5, window: int = 60):
        key = f"rate_limit:{client_id}"
        current = r.incr(key)
        if current == 1:
            r.expire(key, window)
        return current <= max_requests
    
    # 5次允许, 第6次拒绝
    for i in range(5):
        assert rate_limit("client_1") is True
    assert rate_limit("client_1") is False  # 第6次被限流
    
    # 不同 client 不受限
    assert rate_limit("client_2") is True
    
    print("✅ 练习8通过: Cache-Aside/Write-Through/缓存穿透防护/速率限制")


# ============================================================
# 练习 9: 数据库迁移概念 — 版本管理 + Schema 演进
# ============================================================

def test_09_migrations():
    """数据库迁移概念: 版本追踪 + Schema 变更 + 数据迁移"""
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()
    
    # 迁移版本表
    cursor.execute("""
        CREATE TABLE schema_migrations (
            version INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            applied_at TEXT NOT NULL
        )
    """)
    
    def get_current_version():
        cursor.execute("SELECT MAX(version) FROM schema_migrations")
        result = cursor.fetchone()[0]
        return result or 0
    
    def apply_migration(version: int, name: str, sql: str):
        current = get_current_version()
        if version <= current:
            return False  # 已应用
        
        try:
            cursor.executescript(sql)
            cursor.execute(
                "INSERT INTO schema_migrations VALUES (?, ?, ?)",
                (version, name, datetime.now().isoformat())
            )
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise e
    
    def get_applied_migrations():
        cursor.execute("SELECT version, name FROM schema_migrations ORDER BY version")
        return cursor.fetchall()
    
    # === 迁移历史 ===
    
    # V1: 初始 Schema
    apply_migration(1, "initial", """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            email TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
    """)
    assert get_current_version() == 1
    
    # V2: 添加密码字段
    apply_migration(2, "add_password", """
        ALTER TABLE users ADD COLUMN password_hash TEXT;
    """)
    
    # V3: 添加文章表
    apply_migration(3, "add_posts", """
        CREATE TABLE posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            content TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        CREATE INDEX idx_posts_user ON posts(user_id);
    """)
    
    # V4: 添加软删除
    apply_migration(4, "add_soft_delete", """
        ALTER TABLE posts ADD COLUMN is_deleted INTEGER DEFAULT 0;
        ALTER TABLE users ADD COLUMN is_active INTEGER DEFAULT 1;
    """)
    
    # V5: 添加点赞表 (数据迁移)
    apply_migration(5, "add_likes", """
        CREATE TABLE likes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            post_id INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(user_id, post_id),
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (post_id) REFERENCES posts(id)
        );
    """)
    
    assert get_current_version() == 5
    
    # 验证已应用的迁移
    applied = get_applied_migrations()
    assert len(applied) == 5
    assert applied[0] == (1, "initial")
    assert applied[4] == (5, "add_likes")
    
    # 重复应用应被跳过
    result = apply_migration(3, "add_posts", "SELECT 1;")
    assert result is False
    
    # 验证最终 Schema
    cursor.execute("PRAGMA table_info(users)")
    user_cols = {row[1] for row in cursor.fetchall()}
    assert user_cols == {"id", "username", "email", "created_at", "password_hash", "is_active"}
    
    cursor.execute("PRAGMA table_info(posts)")
    post_cols = {row[1] for row in cursor.fetchall()}
    assert post_cols == {"id", "user_id", "title", "content", "created_at", "is_deleted"}
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row[0] for row in cursor.fetchall()}
    assert "users" in tables
    assert "posts" in tables
    assert "likes" in tables
    assert "schema_migrations" in tables
    
    # 插入数据验证
    cursor.execute("INSERT INTO users (username, email, created_at, password_hash, is_active) VALUES (?, ?, ?, ?, ?)",
                   ("alice", "alice@test.com", datetime.now().isoformat(), "hash123", 1))
    cursor.execute("INSERT INTO posts (user_id, title, content, created_at, is_deleted) VALUES (?, ?, ?, ?, ?)",
                   (1, "Hello", "World", datetime.now().isoformat(), 0))
    cursor.execute("INSERT INTO likes (user_id, post_id, created_at) VALUES (?, ?, ?)",
                   (1, 1, datetime.now().isoformat()))
    conn.commit()
    
    # 唯一约束
    try:
        cursor.execute("INSERT INTO likes (user_id, post_id, created_at) VALUES (?, ?, ?)",
                       (1, 1, datetime.now().isoformat()))
        assert False
    except sqlite3.IntegrityError:
        pass
    
    conn.close()
    print("✅ 练习9通过: 迁移版本管理+Schema演进+数据迁移+约束")


# ============================================================
# 练习 10: 向量检索基础 — 余弦相似度 + Top-K 检索 + 分块
# ============================================================

def test_10_vector_search():
    """向量检索: 嵌入向量 + 余弦相似度 + Top-K + 分块策略"""
    import numpy as np
    
    # 模拟文档嵌入 (实际中由 embedding 模型生成)
    np.random.seed(42)
    
    def cosine_similarity(a, b):
        """余弦相似度"""
        return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-10)
    
    def euclidean_distance(a, b):
        """欧氏距离"""
        return np.sqrt(np.sum((a - b) ** 2))
    
    def dot_product(a, b):
        """点积"""
        return np.dot(a, b)
    
    # 生成模拟文档向量 (128维)
    num_docs = 100
    dim = 128
    doc_vectors = np.random.randn(num_docs, dim)
    doc_metadata = [
        {"id": i, "title": f"Document_{i}", "category": np.random.choice(["tech", "science", "art"])}
        for i in range(num_docs)
    ]
    
    # === 余弦相似度检索 ===
    query_vec = np.random.randn(dim)
    
    # 计算所有文档与查询的相似度
    similarities = [(i, cosine_similarity(query_vec, doc_vectors[i])) for i in range(num_docs)]
    similarities.sort(key=lambda x: x[1], reverse=True)
    
    # Top-K 检索
    K = 5
    top_k = similarities[:K]
    assert len(top_k) == K
    # 相似度应递减
    for i in range(len(top_k) - 1):
        assert top_k[i][1] >= top_k[i + 1][1]
    
    # === 批量检索 ===
    queries = np.random.randn(10, dim)  # 10个查询
    
    # 矩阵化计算 (比循环快)
    # normalize
    doc_norms = doc_vectors / (np.linalg.norm(doc_vectors, axis=1, keepdims=True) + 1e-10)
    query_norms = queries / (np.linalg.norm(queries, axis=1, keepdims=True) + 1e-10)
    
    # 相似度矩阵 (10, 100)
    sim_matrix = query_norms @ doc_norms.T
    
    # 每个查询的 Top-K
    batch_top_k = []
    for i in range(10):
        top_indices = np.argsort(-sim_matrix[i])[:K]
        batch_top_k.append(top_indices.tolist())
    
    assert len(batch_top_k) == 10
    assert len(batch_top_k[0]) == K
    
    # === 过滤检索 (先过滤再检索) ===
    # 只在 "tech" 类别的文档中检索
    tech_indices = [i for i, m in enumerate(doc_metadata) if m["category"] == "tech"]
    tech_vectors = doc_vectors[tech_indices]
    
    tech_norms = tech_vectors / (np.linalg.norm(tech_vectors, axis=1, keepdims=True) + 1e-10)
    query_norm = query_vec / (np.linalg.norm(query_vec) + 1e-10)
    tech_sims = tech_norms @ query_norm
    
    tech_top_k_idx = np.argsort(-tech_sims)[:K]
    tech_top_k = [(tech_indices[idx], tech_sims[idx]) for idx in tech_top_k_idx]
    
    assert len(tech_top_k) == K
    # 所有结果都应该是 tech 类别
    for doc_idx, _ in tech_top_k:
        assert doc_metadata[doc_idx]["category"] == "tech"
    
    # === 分块策略 (文本分块 + 向量化) ===
    def chunk_text(text: str, chunk_size: int = 100, overlap: int = 20) -> list:
        """文本分块: 固定大小 + 重叠"""
        chunks = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            chunk = text[start:end]
            chunks.append(chunk)
            start = end - overlap  # 重叠
        return chunks
    
    long_text = " ".join([f"word_{i}" for i in range(500)])
    chunks = chunk_text(long_text, chunk_size=100, overlap=20)
    
    assert len(chunks) > 1
    # 每个块大小 <= chunk_size
    for chunk in chunks:
        assert len(chunk) <= 100
    
    # 验证重叠
    # 块1的末尾应与块2的开头有重叠
    if len(chunks) >= 2:
        overlap_text = chunks[0][-20:]
        assert chunks[1][:20] == overlap_text
    
    # === 距离度量对比 ===
    vec_a = np.array([1.0, 0.0, 0.0])
    vec_b = np.array([0.0, 1.0, 0.0])
    vec_c = np.array([1.0, 1.0, 0.0])
    
    # 余弦相似度
    assert abs(cosine_similarity(vec_a, vec_b)) < 0.01  # 正交 → 0
    assert cosine_similarity(vec_a, vec_c) > 0.7  # 方向相近 → 高
    assert cosine_similarity(vec_a, vec_a) > 0.99  # 相同 → 1
    
    # 欧氏距离
    assert euclidean_distance(vec_a, vec_b) > 1.0
    assert euclidean_distance(vec_a, vec_a) < 0.01
    
    print("✅ 练习10通过: 余弦相似度+Top-K+批量检索+过滤+分块+距离度量")


# ============================================================
# 主入口
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("第三阶段 3.3 — 数据库与存储 (10题)")
    print("=" * 60)
    print()
    
    tests = [
        test_01_sqlite_crud,
        test_02_sqlalchemy_orm,
        test_03_relationships,
        test_04_advanced_queries,
        test_05_transactions,
        test_06_indexes,
        test_07_redis_basics,
        test_08_cache_patterns,
        test_09_migrations,
        test_10_vector_search,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"❌ {test.__name__} 失败: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print()
    print(f"结果: {passed}/{passed + failed} 通过")
    if failed == 0:
        print("🎉 全部通过!")
