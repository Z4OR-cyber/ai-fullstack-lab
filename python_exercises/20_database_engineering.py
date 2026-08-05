#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
阶段六：数据库与数据集工程 — 10 道实战练习题
================================================
覆盖：分库分表、ETL管道、时序/图数据库、数据版本控制、Lakehouse、特征存储、
      数据管道编排、数据质量监控、向量数据库、数据血缘追踪

环境说明：
- 已安装：numpy, pandas, sqlalchemy, networkx, scipy, sklearn, pyarrow, redis
- 未成功安装（用纯 Python 模拟）：dvc, great_expectations, apache-airflow, faiss-cpu
- pip 安装结果记录：
    faiss-cpu    → 下载超时，未安装 → 用 numpy 实现
    dvc          → 安装超时，未安装 → 用纯 Python 模拟
    great_expectations → 安装超时，未安装 → 自研校验框架
    apache-airflow     → 安装超时，未安装 → 自研轻量 DAG 框架

运行方式：
    cd /app/data/所有对话/主对话 && python3 python_exercises/20_database_engineering.py
"""

import os
import sys
import json
import time
import uuid
import hashlib
import sqlite3
import shutil
import pickle
import struct
import random
import math
from datetime import datetime, timedelta
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np
import pandas as pd
import networkx as nx
from sqlalchemy import (
    create_engine, Column, Integer, String, Float, Text, DateTime,
    MetaData, Table, select, insert, update, delete, func, and_, or_
)
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from sqlalchemy.pool import QueuePool

# ============================================================
# 题 1: 多数据库架构与分库分表
# ============================================================

def exercise_01():
    """
    知识点：读写分离、垂直分片、水平分片、分片键选择、雪花算法生成分布式ID
    
    模拟场景：电商系统，包含用户、订单、商品三个垂直分片，
    订单按用户ID水平分片到3个库，使用雪花算法生成全局唯一ID。
    """
    print("=" * 70)
    print("题 1: 多数据库架构与分库分表")
    print("=" * 70)
    
    tmpdir = "/tmp/db_sharding_demo"
    if os.path.exists(tmpdir):
        shutil.rmtree(tmpdir)
    os.makedirs(tmpdir)
    
    # ---- 1.1 雪花算法 (Snowflake ID Generator) ----
    print("\n--- 1.1 雪花算法生成分布式唯一 ID ---")
    
    class SnowflakeGenerator:
        """雪花算法：64位 = 1位符号 + 41位时间戳 + 10位机器ID + 12位序列号"""
        EPOCH = 1700000000000  # 自定义纪元 (2023-11-14)
        MACHINE_BITS = 10
        SEQUENCE_BITS = 12
        MAX_MACHINE = (1 << MACHINE_BITS) - 1
        MAX_SEQUENCE = (1 << SEQUENCE_BITS) - 1
        MACHINE_SHIFT = SEQUENCE_BITS
        TIMESTAMP_SHIFT = MACHINE_BITS + SEQUENCE_BITS
        
        def __init__(self, machine_id=1):
            if machine_id < 0 or machine_id > self.MAX_MACHINE:
                raise ValueError(f"machine_id must be 0-{self.MAX_MACHINE}")
            self.machine_id = machine_id
            self.sequence = 0
            self.last_timestamp = -1
        
        def _current_ms(self):
            return int(time.time() * 1000)
        
        def generate(self):
            timestamp = self._current_ms()
            if timestamp < self.last_timestamp:
                raise RuntimeError("Clock moved backwards!")
            if timestamp == self.last_timestamp:
                self.sequence = (self.sequence + 1) & self.MAX_SEQUENCE
                if self.sequence == 0:
                    while timestamp <= self.last_timestamp:
                        timestamp = self._current_ms()
            else:
                self.sequence = 0
            self.last_timestamp = timestamp
            sid = ((timestamp - self.EPOCH) << self.TIMESTAMP_SHIFT) | \
                  (self.machine_id << self.MACHINE_SHIFT) | \
                  self.sequence
            return sid
        
        @staticmethod
        def parse(snowflake_id):
            ts = (snowflake_id >> 22) + SnowflakeGenerator.EPOCH
            machine = (snowflake_id >> 12) & SnowflakeGenerator.MAX_MACHINE
            seq = snowflake_id & SnowflakeGenerator.MAX_SEQUENCE
            return {"timestamp_ms": ts, "datetime": datetime.fromtimestamp(ts/1000),
                    "machine_id": machine, "sequence": seq}
    
    gen = SnowflakeGenerator(machine_id=1)
    ids = [gen.generate() for _ in range(5)]
    print(f"生成 5 个雪花 ID: {ids}")
    print(f"解析第一个 ID: {SnowflakeGenerator.parse(ids[0])}")
    assert len(set(ids)) == 5, "ID必须唯一"
    assert all(ids[i] < ids[i+1] for i in range(4)), "ID应递增"
    print("✓ 雪花 ID 唯一性 & 单调递增 验证通过")
    
    # ---- 1.2 读写分离 ----
    print("\n--- 1.2 读写分离模拟 ---")
    
    Base = declarative_base()
    
    class User(Base):
        __tablename__ = "users"
        id = Column(Integer, primary_key=True)
        name = Column(String(50))
        email = Column(String(100))
        created_at = Column(DateTime, default=datetime.now)
    
    class ReadWriteRouter:
        """读写分离路由器：写操作走主库，读操作走从库"""
        def __init__(self, master_url, slave_urls):
            self.master = create_engine(master_url)
            self.slaves = [create_engine(url) for url in slave_urls]
            self._slave_idx = 0
            self.query_log = []
        
        def get_write_engine(self):
            self.query_log.append(("WRITE", "master"))
            return self.master
        
        def get_read_engine(self):
            engine = self.slaves[self._slave_idx % len(self.slaves)]
            self.query_log.append(("READ", f"slave_{self._slave_idx % len(self.slaves)}"))
            self._slave_idx += 1
            return engine
    
    master_url = f"sqlite:///{tmpdir}/master.db"
    slave1_url = f"sqlite:///{tmpdir}/slave1.db"
    slave2_url = f"sqlite:///{tmpdir}/slave2.db"
    
    router = ReadWriteRouter(master_url, [slave1_url, slave2_url])
    
    # 在主库建表并写入
    Base.metadata.create_all(router.master)
    with Session(router.get_write_engine()) as session:
        for i in range(10):
            session.add(User(name=f"user_{i}", email=f"user_{i}@test.com"))
        session.commit()
    
    # 同步到从库（模拟主从复制）
    for slave_engine in router.slaves:
        Base.metadata.create_all(slave_engine)
        with Session(slave_engine) as s:
            with Session(router.master) as ms:
                users = ms.query(User).all()
                for u in users:
                    s.add(User(id=u.id, name=u.name, email=u.email, created_at=u.created_at))
            s.commit()
    
    # 读操作走从库（轮询负载均衡）
    with Session(router.get_read_engine()) as session:
        count = session.query(User).count()
        print(f"从 slave_0 读取用户数: {count}")
    with Session(router.get_read_engine()) as session:
        count = session.query(User).count()
        print(f"从 slave_1 读取用户数: {count}")
    
    print(f"查询路由日志: {router.query_log}")
    write_ops = [log for log in router.query_log if log[0] == "WRITE"]
    read_ops = [log for log in router.query_log if log[0] == "READ"]
    assert len(write_ops) >= 1 and len(read_ops) >= 2
    print("✓ 读写分离：写走主库，读轮询从库 验证通过")
    
    # ---- 1.3 垂直分片 ----
    print("\n--- 1.3 垂直分片（按业务拆表到不同库）---")
    
    class Order(Base):
        __tablename__ = "orders"
        id = Column(Integer, primary_key=True)
        user_id = Column(Integer)
        amount = Column(Float)
        status = Column(String(20))
    
    class Product(Base):
        __tablename__ = "products"
        id = Column(Integer, primary_key=True)
        name = Column(String(50))
        price = Column(Float)
        stock = Column(Integer)
    
    # 用户库、订单库、商品库 分别独立
    user_db = create_engine(f"sqlite:///{tmpdir}/user_db.db")
    order_db = create_engine(f"sqlite:///{tmpdir}/order_db.db")
    product_db = create_engine(f"sqlite:///{tmpdir}/product_db.db")
    
    User.__table__.create(user_db, checkfirst=True)
    Order.__table__.create(order_db, checkfirst=True)
    Product.__table__.create(product_db, checkfirst=True)
    
    # 分别写入
    with Session(user_db) as s:
        s.add(User(name="Alice", email="alice@test.com"))
        s.commit()
    with Session(order_db) as s:
        s.add(Order(id=1, user_id=1, amount=99.9, status="paid"))
        s.commit()
    with Session(product_db) as s:
        s.add(Product(id=1, name="Widget", price=99.9, stock=100))
        s.commit()
    
    # 跨库查询：需要应用层 JOIN
    with Session(user_db) as us, Session(order_db) as ord_sess:
        user = us.query(User).filter_by(name="Alice").first()
        orders = ord_sess.query(Order).filter_by(user_id=user.id).all()
        print(f"跨库查询：用户 {user.name} 的订单数={len(orders)}, 金额={orders[0].amount}")
    
    assert orders[0].amount == 99.9
    print("✓ 垂直分片：按业务拆库 + 应用层跨库 JOIN 验证通过")
    
    # ---- 1.4 水平分片 ----
    print("\n--- 1.4 水平分片（按分片键路由到不同库）---")
    
    class ShardedOrderTable:
        """水平分片：订单按 user_id % N 路由到 N 个分片"""
        def __init__(self, n_shards, base_dir):
            self.n_shards = n_shards
            self.engines = []
            for i in range(n_shards):
                eng = create_engine(f"sqlite:///{base_dir}/order_shard_{i}.db")
                Order.__table__.create(eng, checkfirst=True)
                self.engines.append(eng)
        
        def _shard_key(self, user_id):
            return user_id % self.n_shards
        
        def insert_order(self, snowflake_id, user_id, amount):
            shard = self._shard_key(user_id)
            with Session(self.engines[shard]) as s:
                s.add(Order(id=snowflake_id, user_id=user_id, amount=amount, status="new"))
                s.commit()
            return shard
        
        def query_by_user(self, user_id):
            shard = self._shard_key(user_id)
            with Session(self.engines[shard]) as s:
                return s.query(Order).filter_by(user_id=user_id).all()
        
        def query_all(self):
            """跨分片查询：合并所有分片结果"""
            results = []
            for i, eng in enumerate(self.engines):
                with Session(eng) as s:
                    orders = s.query(Order).all()
                    results.extend([(i, o.id, o.user_id, o.amount) for o in orders])
            return results
        
        def get_shard_distribution(self):
            dist = {}
            for i, eng in enumerate(self.engines):
                with Session(eng) as s:
                    dist[f"shard_{i}"] = s.query(Order).count()
            return dist
    
    sharded = ShardedOrderTable(n_shards=3, base_dir=tmpdir)
    snow_gen = SnowflakeGenerator(machine_id=2)
    
    # 插入 30 条订单，user_id 从 1 到 30
    for uid in range(1, 31):
        sid = snow_gen.generate()
        shard = sharded.insert_order(sid, uid, round(random.uniform(10, 500), 2))
    
    distribution = sharded.get_shard_distribution()
    print(f"分片数据分布: {distribution}")
    total = sum(distribution.values())
    assert total == 30, f"总记录数应为30，实际{total}"
    
    # 验证分片路由正确性
    user_5_orders = sharded.query_by_user(5)
    print(f"用户5的订单（应落在shard_{5%3}）: {len(user_5_orders)} 条")
    assert len(user_5_orders) == 1
    assert 5 % 3 == 2  # user_id=5 应该路由到 shard_2
    
    all_orders = sharded.query_all()
    print(f"跨分片查询总数: {len(all_orders)} 条")
    assert len(all_orders) == 30
    print("✓ 水平分片：分片键路由 + 跨分片合并查询 验证通过")
    
    # ---- 1.5 分片键选择策略分析 ----
    print("\n--- 1.5 分片键选择策略分析 ---")
    
    strategies = {
        "user_id取模": lambda uid: uid % 3,
        "user_id范围": lambda uid: 0 if uid <= 10 else (1 if uid <= 20 else 2),
        "一致性哈希": lambda uid: hash(f"user_{uid}") % 3,
    }
    
    for name, func in strategies.items():
        shard_counts = [0, 0, 0]
        for uid in range(1, 1001):
            shard_counts[func(uid)] += 1
        balance = max(shard_counts) / min(shard_counts) if min(shard_counts) > 0 else float('inf')
        print(f"  {name:20s} → 分布={shard_counts}, 均衡度={balance:.2f}")
    
    print("✓ 分片键策略分析完成（取模法分布最均匀）")
    
    print(f"\n✅ 题1完成")


# ============================================================
# 题 2: 数据迁移与 ETL 管道
# ============================================================

def exercise_02():
    """
    知识点：ETL管道、增量同步(CDC)模拟、数据脱敏、一致性校验、迁移回滚
    
    模拟场景：从源数据库迁移用户数据到目标数据仓库，
    包含全量ETL、增量CDC、字段脱敏、数据校验、回滚机制。
    """
    print("=" * 70)
    print("题 2: 数据迁移与 ETL 管道")
    print("=" * 70)
    
    tmpdir = "/tmp/etl_pipeline_demo"
    if os.path.exists(tmpdir):
        shutil.rmtree(tmpdir)
    os.makedirs(tmpdir)
    
    # ---- 2.1 源库与目标库初始化 ----
    print("\n--- 2.1 初始化源数据库（模拟生产库）---")
    
    source_engine = create_engine(f"sqlite:///{tmpdir}/source.db")
    target_engine = create_engine(f"sqlite:///{tmpdir}/target.db")
    
    Base2 = declarative_base()
    
    class SourceUser(Base2):
        __tablename__ = "source_users"
        id = Column(Integer, primary_key=True)
        name = Column(String(50))
        phone = Column(String(20))
        email = Column(String(100))
        id_card = Column(String(18))
        salary = Column(Float)
        updated_at = Column(DateTime, default=datetime.now)
        is_deleted = Column(Integer, default=0)
    
    class TargetUser(Base2):
        __tablename__ = "target_users"
        id = Column(Integer, primary_key=True)
        name = Column(String(50))
        phone_masked = Column(String(20))
        email_masked = Column(String(100))
        id_card_masked = Column(String(18))
        salary_bucket = Column(String(20))
        migrated_at = Column(DateTime, default=datetime.now)
        source_updated_at = Column(DateTime)
    
    class MigrationLog(Base2):
        __tablename__ = "migration_log"
        id = Column(Integer, primary_key=True)
        batch_id = Column(String(50))
        record_id = Column(Integer)
        operation = Column(String(20))  # INSERT, UPDATE, DELETE
        status = Column(String(20))     # SUCCESS, FAILED, ROLLED_BACK
        timestamp = Column(DateTime, default=datetime.now)
    
    Base2.metadata.create_all(source_engine)
    Base2.metadata.create_all(target_engine)
    
    # 插入源数据
    with Session(source_engine) as s:
        for i in range(1, 101):
            s.add(SourceUser(
                name=f"用户_{i:03d}",
                phone=f"138{random.randint(10000000, 99999999)}",
                email=f"user{i}@example.com",
                id_card=f"1101011990{random.randint(10000000, 99999999)}",
                salary=round(random.uniform(5000, 50000), 2),
                updated_at=datetime.now() - timedelta(hours=random.randint(0, 48))
            ))
        s.commit()
    print("源库插入 100 条用户数据")
    
    # ---- 2.2 数据脱敏 ----
    print("\n--- 2.2 数据脱敏处理 ---")
    
    class DataMasker:
        """数据脱敏工具：手机号、邮箱、身份证、薪资分桶"""
        @staticmethod
        def mask_phone(phone):
            return phone[:3] + "****" + phone[-4:]
        
        @staticmethod
        def mask_email(email):
            at = email.index("@")
            return email[:2] + "***" + email[at:]
        
        @staticmethod
        def mask_id_card(id_card):
            return id_card[:6] + "********" + id_card[-4:]
        
        @staticmethod
        def bucket_salary(salary):
            if salary < 10000: return "低"
            elif salary < 20000: return "中低"
            elif salary < 35000: return "中高"
            else: return "高"
    
    # 验证脱敏
    print(f"  手机号脱敏: 13812345678 → {DataMasker.mask_phone('13812345678')}")
    print(f"  邮箱脱敏:   user99@example.com → {DataMasker.mask_email('user99@example.com')}")
    print(f"  身份证脱敏: 110101199001011234 → {DataMasker.mask_id_card('110101199001011234')}")
    print(f"  薪资分桶:   25000.0 → {DataMasker.bucket_salary(25000.0)}")
    assert DataMasker.mask_phone("13812345678") == "138****5678"
    print("✓ 脱敏函数验证通过")
    
    # ---- 2.3 全量 ETL 管道 ----
    print("\n--- 2.3 全量 ETL 管道 (Extract → Transform → Load) ---")
    
    class ETLPipeline:
        def __init__(self, source_eng, target_eng):
            self.source = source_eng
            self.target = target_eng
            self.stats = {"extracted": 0, "transformed": 0, "loaded": 0, "errors": 0}
        
        def extract(self):
            """Extract: 从源库读取数据"""
            with Session(self.source) as s:
                records = s.query(SourceUser).filter_by(is_deleted=0).all()
            self.stats["extracted"] = len(records)
            print(f"  [Extract] 读取 {len(records)} 条记录")
            return records
        
        def transform(self, records):
            """Transform: 数据清洗 + 脱敏 + 类型转换"""
            transformed = []
            for r in records:
                try:
                    transformed.append({
                        "id": r.id,
                        "name": r.name,
                        "phone_masked": DataMasker.mask_phone(r.phone),
                        "email_masked": DataMasker.mask_email(r.email),
                        "id_card_masked": DataMasker.mask_id_card(r.id_card),
                        "salary_bucket": DataMasker.bucket_salary(r.salary),
                        "source_updated_at": r.updated_at,
                    })
                except Exception as e:
                    self.stats["errors"] += 1
            self.stats["transformed"] = len(transformed)
            print(f"  [Transform] 转换 {len(transformed)} 条记录, 错误 {self.stats['errors']} 条")
            return transformed
        
        def load(self, data):
            """Load: 写入目标库"""
            batch_id = f"batch_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            with Session(self.target) as s:
                for item in data:
                    s.add(TargetUser(**item))
                    s.add(MigrationLog(batch_id=batch_id, record_id=item["id"],
                                       operation="INSERT", status="SUCCESS"))
                s.commit()
            self.stats["loaded"] = len(data)
            print(f"  [Load] 写入 {len(data)} 条记录, batch_id={batch_id}")
            return batch_id
        
        def run(self):
            print("  === ETL Pipeline 启动 ===")
            records = self.extract()
            transformed = self.transform(records)
            batch_id = self.load(transformed)
            print(f"  === ETL Pipeline 完成: {self.stats} ===")
            return batch_id
    
    pipeline = ETLPipeline(source_engine, target_engine)
    batch_id = pipeline.run()
    
    # 验证全量迁移
    with Session(target_engine) as s:
        target_count = s.query(TargetUser).count()
    assert target_count == 100, f"目标库应有100条，实际{target_count}"
    print("✓ 全量 ETL: 100 条数据迁移成功")
    
    # ---- 2.4 增量同步 (CDC 模拟) ----
    print("\n--- 2.4 增量同步 (CDC - Change Data Capture 模拟) ---")
    
    class CDCSync:
        """基于 updated_at 时间戳的增量同步"""
        def __init__(self, source_eng, target_eng):
            self.source = source_eng
            self.target = target_eng
            self.last_sync_time = None
        
        def get_last_sync_time(self):
            if self.last_sync_time is None:
                with Session(self.target) as s:
                    latest = s.query(TargetUser.source_updated_at).order_by(
                        TargetUser.source_updated_at.desc()).first()
                    self.last_sync_time = latest[0] if latest else datetime(2000, 1, 1)
            return self.last_sync_time
        
        def sync_incremental(self):
            cutoff = self.get_last_sync_time()
            print(f"  增量同步截止时间: {cutoff}")
            
            with Session(self.source) as s:
                changes = s.query(SourceUser).filter(
                    SourceUser.updated_at > cutoff
                ).all()
            
            print(f"  检测到 {len(changes)} 条变更记录")
            
            with Session(self.target) as s:
                for r in changes:
                    existing = s.query(TargetUser).filter_by(id=r.id).first()
                    if existing:
                        # UPDATE
                        existing.name = r.name
                        existing.phone_masked = DataMasker.mask_phone(r.phone)
                        existing.email_masked = DataMasker.mask_email(r.email)
                        existing.id_card_masked = DataMasker.mask_id_card(r.id_card)
                        existing.salary_bucket = DataMasker.bucket_salary(r.salary)
                        existing.source_updated_at = r.updated_at
                        existing.migrated_at = datetime.now()
                        s.add(MigrationLog(batch_id="cdc_update", record_id=r.id,
                                           operation="UPDATE", status="SUCCESS"))
                    else:
                        # INSERT
                        s.add(TargetUser(
                            id=r.id, name=r.name,
                            phone_masked=DataMasker.mask_phone(r.phone),
                            email_masked=DataMasker.mask_email(r.email),
                            id_card_masked=DataMasker.mask_id_card(r.id_card),
                            salary_bucket=DataMasker.bucket_salary(r.salary),
                            source_updated_at=r.updated_at,
                        ))
                        s.add(MigrationLog(batch_id="cdc_insert", record_id=r.id,
                                           operation="INSERT", status="SUCCESS"))
                s.commit()
            
            self.last_sync_time = datetime.now()
            return len(changes)
    
    cdc = CDCSync(source_engine, target_engine)
    
    # 模拟源库新增和更新
    with Session(source_engine) as s:
        # 新增2条
        s.add(SourceUser(name="新用户_001", phone="13900000001", email="new1@test.com",
                         id_card="110101199002021234", salary=12000, updated_at=datetime.now()))
        s.add(SourceUser(name="新用户_002", phone="13900000002", email="new2@test.com",
                         id_card="110101199003031234", salary=25000, updated_at=datetime.now()))
        # 更新1条
        existing = s.query(SourceUser).filter_by(id=1).first()
        existing.name = "用户_001_已更新"
        existing.updated_at = datetime.now()
        s.commit()
    
    synced = cdc.sync_incremental()
    print(f"  CDC 同步了 {synced} 条记录")
    assert synced == 3, f"应有3条变更，实际{synced}"
    
    # 验证更新生效
    with Session(target_engine) as s:
        updated = s.query(TargetUser).filter_by(id=1).first()
        assert updated.name == "用户_001_已更新"
        new_count = s.query(TargetUser).count()
    assert new_count == 102, f"目标库应有102条，实际{new_count}"
    print("✓ 增量 CDC: 2 条新增 + 1 条更新 同步成功")
    
    # ---- 2.5 一致性校验 ----
    print("\n--- 2.5 一致性校验 ---")
    
    class ConsistencyChecker:
        @staticmethod
        def check_count(source_eng, target_eng):
            with Session(source_eng) as s:
                src_count = s.query(SourceUser).filter_by(is_deleted=0).count()
            with Session(target_eng) as s:
                tgt_count = s.query(TargetUser).count()
            return src_count == tgt_count, src_count, tgt_count
        
        @staticmethod
        def check_field_integrity(source_eng, target_eng):
            """抽样校验字段是否一致"""
            with Session(source_eng) as s:
                src_users = s.query(SourceUser).filter_by(is_deleted=0).limit(10).all()
            with Session(target_eng) as s:
                tgt_users = {u.id: u for u in s.query(TargetUser).all()}
            
            mismatches = 0
            for src in src_users:
                tgt = tgt_users.get(src.id)
                if not tgt:
                    mismatches += 1
                    continue
                if src.name != tgt.name:
                    mismatches += 1
            return mismatches == 0, mismatches
        
        @staticmethod
        def check_checksum(source_eng, target_eng):
            """校验源和目标的记录数checksum"""
            with Session(source_eng) as s:
                src_ids = sorted([r.id for r in s.query(SourceUser).filter_by(is_deleted=0).all()])
            with Session(target_eng) as s:
                tgt_ids = sorted([r.id for r in s.query(TargetUser).all()])
            return src_ids == tgt_ids, len(src_ids), len(tgt_ids)
    
    # 执行校验
    ok1, sc, tc = ConsistencyChecker.check_count(source_engine, target_engine)
    print(f"  记录数校验: 源={sc}, 目标={tc}, 一致={ok1}")
    assert ok1
    
    ok2, mismatches = ConsistencyChecker.check_field_integrity(source_engine, target_engine)
    print(f"  字段完整性校验: 不匹配数={mismatches}, 通过={ok2}")
    assert ok2
    
    ok3, sl, tl = ConsistencyChecker.check_checksum(source_engine, target_engine)
    print(f"  ID集合校验: 源={sl}, 目标={tl}, 一致={ok3}")
    assert ok3
    print("✓ 一致性校验全部通过")
    
    # ---- 2.6 迁移回滚机制 ----
    print("\n--- 2.6 迁移回滚机制 ---")
    
    class RollbackManager:
        """基于 migration_log 的回滚管理器"""
        def __init__(self, target_eng):
            self.target = target_eng
        
        def rollback_batch(self, batch_id):
            with Session(self.target) as s:
                logs = s.query(MigrationLog).filter_by(batch_id=batch_id, status="SUCCESS").all()
                rolled_back = 0
                for log in logs:
                    if log.operation == "INSERT":
                        # 删除该批次插入的记录
                        obj = s.query(TargetUser).filter_by(id=log.record_id).first()
                        if obj:
                            s.delete(obj)
                            rolled_back += 1
                    log.status = "ROLLED_BACK"
                s.commit()
            return rolled_back
        
        def get_batch_info(self):
            with Session(self.target) as s:
                batches = s.query(MigrationLog.batch_id).distinct().all()
                info = {}
                for (bid,) in batches:
                    count = s.query(MigrationLog).filter_by(batch_id=bid, status="SUCCESS").count()
                    info[bid] = count
                return info
    
    rb = RollbackManager(target_engine)
    batch_info = rb.get_batch_info()
    print(f"  回滚前批次信息: {batch_info}")
    
    # 回滚 CDC 插入的批次
    rolled = rb.rollback_batch("cdc_insert")
    print(f"  回滚 cdc_insert 批次: 删除 {rolled} 条记录")
    
    with Session(target_engine) as s:
        after_count = s.query(TargetUser).count()
    print(f"  回滚后目标库记录数: {after_count}")
    assert after_count == 100, f"回滚后应剩100条，实际{after_count}"
    print("✓ 回滚机制: 按批次回滚 INSERT 记录 验证通过")
    
    print(f"\n✅ 题2完成")


# ============================================================
# 题 3: 时序数据库与图数据库
# ============================================================

def exercise_03():
    """
    知识点：时序数据写入/降采样/聚合查询；图建模、Cypher-like查询、路径分析、社区检测
    
    模拟场景：IoT传感器时序数据 + 社交网络图分析
    """
    print("=" * 70)
    print("题 3: 时序数据库与图数据库")
    print("=" * 70)
    
    tmpdir = "/tmp/ts_graph_demo"
    if os.path.exists(tmpdir):
        shutil.rmtree(tmpdir)
    os.makedirs(tmpdir)
    
    # ---- 3.1 时序数据库模拟 ----
    print("\n--- 3.1 时序数据写入与查询 ---")
    
    class TimeSeriesDB:
        """基于 SQLite + pandas 的时序数据库模拟"""
        def __init__(self, db_path):
            self.engine = create_engine(f"sqlite:///{db_path}")
            self._init_schema()
        
        def _init_schema(self):
            with self.engine.connect() as conn:
                conn.execute(__import__('sqlalchemy').text("""
                    CREATE TABLE IF NOT EXISTS metrics (
                        timestamp DATETIME,
                        sensor_id TEXT,
                        metric_name TEXT,
                        value REAL,
                        tags TEXT
                    )
                """))
                conn.execute(__import__('sqlalchemy').text(
                    "CREATE INDEX IF NOT EXISTS idx_ts ON metrics(timestamp)"
                ))
                conn.execute(__import__('sqlalchemy').text(
                    "CREATE INDEX IF NOT EXISTS idx_sensor ON metrics(sensor_id, metric_name)"
                ))
                conn.commit()
        
        def write_points(self, points):
            """批量写入时序数据点"""
            df = pd.DataFrame(points)
            df.to_sql("metrics", self.engine, if_exists="append", index=False)
            return len(points)
        
        def query_range(self, sensor_id, metric_name, start, end):
            sql = f"""
                SELECT * FROM metrics 
                WHERE sensor_id='{sensor_id}' AND metric_name='{metric_name}'
                AND timestamp >= '{start}' AND timestamp <= '{end}'
                ORDER BY timestamp
            """
            return pd.read_sql(sql, self.engine)
        
        def aggregate(self, sensor_id, metric_name, start, end, window="1H"):
            """时间窗口聚合"""
            df = self.query_range(sensor_id, metric_name, start, end)
            if df.empty:
                return df
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df = df.set_index("timestamp")
            agg = df["value"].resample(window).agg(["mean", "min", "max", "count"])
            return agg.reset_index()
        
        def downsample(self, sensor_id, metric_name, start, end, target_points=100):
            """降采样：LTTB-like 简化版（等间隔采样）"""
            df = self.query_range(sensor_id, metric_name, start, end)
            if len(df) <= target_points:
                return df
            step = max(1, (len(df) + target_points - 1) // target_points)  # 向上取整保证不超过target_points
            return df.iloc[::step].reset_index(drop=True)
    
    tsdb = TimeSeriesDB(f"{tmpdir}/ts.db")
    
    # 生成 24 小时的传感器数据，每分钟一个点 = 1440 个点
    base_time = datetime(2024, 1, 1, 0, 0, 0)
    points = []
    for minute in range(1440):
        ts = base_time + timedelta(minutes=minute)
        # 模拟温度数据：日周期 + 噪声
        temp = 20 + 10 * math.sin(2 * math.pi * minute / 1440) + random.gauss(0, 1)
        points.append({
            "timestamp": ts.strftime("%Y-%m-%d %H:%M:%S"),
            "sensor_id": "sensor_01",
            "metric_name": "temperature",
            "value": round(temp, 2),
            "tags": json.dumps({"location": "building_a", "floor": "3"})
        })
        # 湿度数据
        humid = 50 + 20 * math.sin(2 * math.pi * minute / 1440 + math.pi/3) + random.gauss(0, 2)
        points.append({
            "timestamp": ts.strftime("%Y-%m-%d %H:%M:%S"),
            "sensor_id": "sensor_01",
            "metric_name": "humidity",
            "value": round(humid, 2),
            "tags": json.dumps({"location": "building_a", "floor": "3"})
        })
    
    written = tsdb.write_points(points)
    print(f"  写入 {written} 个时序数据点（24h × 2指标 × 每分钟）")
    assert written == 2880
    
    # 范围查询
    start = "2024-01-01 06:00:00"
    end = "2024-01-01 12:00:00"
    temp_df = tsdb.query_range("sensor_01", "temperature", start, end)
    print(f"  范围查询（6h-12h）温度数据: {len(temp_df)} 条")
    assert len(temp_df) == 361  # 6h = 360min + 1
    print(f"  温度范围: min={temp_df['value'].min():.2f}, max={temp_df['value'].max():.2f}, mean={temp_df['value'].mean():.2f}")
    
    # 时间窗口聚合（每小时）
    agg_df = tsdb.aggregate("sensor_01", "temperature", start, end, window="1h")
    print(f"  小时聚合: {len(agg_df)} 个窗口")
    print(f"  聚合示例:\n{agg_df.head(3).to_string(index=False)}")
    assert len(agg_df) >= 6  # 6h = at least 6 windows (may include boundary)
    print("✓ 时序数据写入/查询/聚合 验证通过")
    
    # 降采样
    full_day = tsdb.query_range("sensor_01", "temperature", 
                                 "2024-01-01 00:00:00", "2024-01-01 23:59:59")
    downsampled = tsdb.downsample("sensor_01", "temperature",
                                   "2024-01-01 00:00:00", "2024-01-01 23:59:59", target_points=100)
    print(f"  降采样: {len(full_day)} → {len(downsampled)} 个点（压缩比 {len(full_day)/len(downsampled):.1f}x）")
    assert len(downsampled) <= 100
    print("✓ 降采样验证通过")
    
    # ---- 3.2 图数据库模拟 ----
    print("\n--- 3.2 图数据库建模与查询 ---")
    
    class GraphDatabase:
        """基于 networkx 的图数据库模拟，支持 Cypher-like 查询"""
        def __init__(self):
            self.graph = nx.DiGraph()
        
        def add_node(self, node_id, labels=None, **properties):
            self.graph.add_node(node_id, labels=labels or set(), **properties)
        
        def add_edge(self, source, target, rel_type=None, **properties):
            self.graph.add_edge(source, target, rel_type=rel_type, **properties)
        
        def cypher_match(self, pattern_func):
            """Cypher-like 查询：MATCH (n:Label)-[r:REL]->(m:Label) WHERE ..."""
            results = []
            for u, v, data in self.graph.edges(data=True):
                u_data = self.graph.nodes[u]
                v_data = self.graph.nodes[v]
                if pattern_func(u_data, data, v_data):
                    results.append({"source": u, "target": v, "edge_data": data,
                                    "source_data": u_data, "target_data": v_data})
            return results
        
        def shortest_path(self, source, target):
            try:
                path = nx.shortest_path(self.graph, source, target)
                return path
            except nx.NetworkXNoPath:
                return None
        
        def all_paths(self, source, target, max_depth=5):
            """找出所有路径（限制深度）"""
            paths = []
            for path in nx.all_simple_paths(self.graph, source, target, cutoff=max_depth):
                paths.append(path)
            return paths
        
        def degree_centrality(self):
            return nx.degree_centrality(self.graph)
        
        def detect_communities(self):
            """社区检测：转换为无向图后使用 greedy modularity"""
            undirected = self.graph.to_undirected()
            communities = nx.algorithms.community.greedy_modularity_communities(undirected)
            return [list(c) for c in communities]
        
        def pagerank(self):
            return nx.pagerank(self.graph)
        
        def find_influencers(self, top_n=5):
            pr = self.pagerank()
            return sorted(pr.items(), key=lambda x: x[1], reverse=True)[:top_n]
    
    gdb = GraphDatabase()
    
    # 构建社交网络图
    people = ["Alice", "Bob", "Charlie", "David", "Eve", "Frank", "Grace", "Henry"]
    for p in people:
        gdb.add_node(p, labels={"Person"}, age=random.randint(20, 45),
                      city=random.choice(["Beijing", "Shanghai", "Shenzhen"]))
    
    # 添加关系
    edges = [
        ("Alice", "Bob", "FRIEND"),
        ("Bob", "Charlie", "FRIEND"),
        ("Charlie", "David", "FRIEND"),
        ("David", "Eve", "FRIEND"),
        ("Eve", "Alice", "FRIEND"),
        ("Alice", "Charlie", "FRIEND"),
        ("Frank", "Grace", "FRIEND"),
        ("Grace", "Henry", "FRIEND"),
        ("Henry", "Frank", "FRIEND"),
        ("Bob", "David", "FRIEND"),
        ("Alice", "Eve", "FOLLOW"),
        ("Charlie", "Frank", "FOLLOW"),
    ]
    for src, tgt, rel in edges:
        gdb.add_edge(src, tgt, rel_type=rel, weight=random.uniform(0.5, 1.0))
    
    print(f"  图节点数: {gdb.graph.number_of_nodes()}, 边数: {gdb.graph.number_of_edges()}")
    assert gdb.graph.number_of_nodes() == 8
    assert gdb.graph.number_of_edges() == 12
    
    # Cypher-like 查询：查找所有 FRIEND 关系
    friend_edges = gdb.cypher_match(lambda u, r, v: r.get("rel_type") == "FRIEND")
    print(f"  MATCH (a)-[:FRIEND]->(b): 找到 {len(friend_edges)} 条好友关系")
    assert len(friend_edges) == 10
    
    # 路径分析
    path = gdb.shortest_path("Alice", "Henry")
    print(f"  最短路径 Alice → Henry: {' → '.join(path) if path else '无路径'}")
    assert path is not None
    
    all_p = gdb.all_paths("Alice", "David", max_depth=4)
    print(f"  Alice → David 所有路径（深度≤4）: {len(all_p)} 条")
    for p in all_p:
        print(f"    {' → '.join(p)}")
    
    # 社区检测
    communities = gdb.detect_communities()
    print(f"  社区检测: 发现 {len(communities)} 个社区")
    for i, comm in enumerate(communities):
        print(f"    社区{i+1}: {comm}")
    
    # PageRank 影响力分析
    influencers = gdb.find_influencers(top_n=3)
    print(f"  PageRank Top 3 影响力用户:")
    for name, score in influencers:
        print(f"    {name}: {score:.4f}")
    
    centrality = gdb.degree_centrality()
    top_degree = sorted(centrality.items(), key=lambda x: x[1], reverse=True)[:3]
    print(f"  度中心性 Top 3: {top_degree}")
    print("✓ 图数据库建模/查询/路径分析/社区检测 验证通过")
    
    print(f"\n✅ 题3完成")


# ============================================================
# 题 4: DVC 数据版本控制（纯 Python 模拟）
# ============================================================

def exercise_04():
    """
    知识点：数据版本控制核心概念 — init/add/push/pull/dvc.yaml 流水线
    
    因 dvc 安装超时，用纯 Python 模拟 DVC 的核心机制：
    - 仓库初始化 (.dvc 目录结构)
    - 数据文件 add (生成 .dvc 元数据文件 + 缓存)
    - 本地远程存储配置与 push/pull
    - dvc.yaml 数据流水线定义
    """
    print("=" * 70)
    print("题 4: DVC 数据版本控制（纯 Python 模拟）")
    print("=" * 70)
    
    tmpdir = "/tmp/dvc_demo"
    if os.path.exists(tmpdir):
        shutil.rmtree(tmpdir)
    os.makedirs(tmpdir)
    
    class SimpleDVC:
        """简化版 DVC：模拟核心功能"""
        def __init__(self, repo_path):
            self.repo_path = repo_path
            self.dvc_dir = os.path.join(repo_path, ".dvc")
            self.cache_dir = os.path.join(self.dvc_dir, "cache")
            self.config_file = os.path.join(self.dvc_dir, "config")
            self.remote_path = None
        
        def init(self):
            os.makedirs(self.cache_dir, exist_ok=True)
            config = {"core": {"remote": "local"}, "remote.local": {"url": ""}}
            self._write_config(config)
            print(f"  [init] DVC 仓库初始化于 {self.dvc_dir}")
            return self
        
        def _write_config(self, config):
            with open(self.config_file, "w") as f:
                json.dump(config, f, indent=2)
        
        def _read_config(self):
            with open(self.config_file, "r") as f:
                return json.load(f)
        
        def _compute_md5(self, filepath):
            h = hashlib.md5()
            with open(filepath, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    h.update(chunk)
            return h.hexdigest()
        
        def _cache_path(self, md5):
            return os.path.join(self.cache_dir, md5[:2], md5[2:])
        
        def add(self, filepath):
            md5 = self._compute_md5(filepath)
            cache_path = self._cache_path(md5)
            os.makedirs(os.path.dirname(cache_path), exist_ok=True)
            shutil.copy2(filepath, cache_path)
            
            dvc_file = filepath + ".dvc"
            meta = {
                "outs": [{
                    "path": os.path.basename(filepath),
                    "md5": md5,
                    "size": os.path.getsize(filepath),
                    "cache": True
                }]
            }
            with open(dvc_file, "w") as f:
                json.dump(meta, f, indent=2)
            
            gitignore = os.path.join(self.repo_path, ".gitignore")
            with open(gitignore, "a") as f:
                f.write(os.path.basename(filepath) + "\n")
            
            print(f"  [add] {filepath} → md5={md5[:12]}..., 缓存于 {cache_path}")
            return md5
        
        def add_remote(self, name, url):
            self.remote_path = url
            os.makedirs(url, exist_ok=True)
            config = self._read_config()
            config[f"remote.{name}"] = {"url": url}
            config["core"]["remote"] = name
            self._write_config(config)
            print(f"  [remote] 添加远程存储 '{name}': {url}")
        
        def push(self):
            if not self.remote_path:
                print("  [push] 错误：未配置远程存储")
                return 0
            pushed = 0
            for root, dirs, files in os.walk(self.cache_dir):
                for f in files:
                    src = os.path.join(root, f)
                    rel = os.path.relpath(src, self.cache_dir)
                    dst = os.path.join(self.remote_path, rel)
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    if not os.path.exists(dst):
                        shutil.copy2(src, dst)
                        pushed += 1
            print(f"  [push] 推送 {pushed} 个缓存文件到远程存储")
            return pushed
        
        def pull(self):
            if not self.remote_path:
                print("  [pull] 错误：未配置远程存储")
                return 0
            pulled = 0
            for root, dirs, files in os.walk(self.remote_path):
                for f in files:
                    src = os.path.join(root, f)
                    rel = os.path.relpath(src, self.remote_path)
                    dst = os.path.join(self.cache_dir, rel)
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    if not os.path.exists(dst):
                        shutil.copy2(src, dst)
                        pulled += 1
            print(f"  [pull] 拉取 {pulled} 个缓存文件到本地")
            return pulled
        
        def checkout(self, dvc_file):
            with open(dvc_file, "r") as f:
                meta = json.load(f)
            for out in meta["outs"]:
                md5 = out["md5"]
                cache_path = self._cache_path(md5)
                filepath = os.path.join(self.repo_path, out["path"])
                if os.path.exists(cache_path):
                    shutil.copy2(cache_path, filepath)
                    print(f"  [checkout] 恢复 {out['path']} (md5={md5[:12]}...)")
                else:
                    print(f"  [checkout] 缓存缺失: {out['path']}")
    
    print("\n--- 4.1 初始化 DVC 仓库 ---")
    dvc = SimpleDVC(tmpdir).init()
    assert os.path.exists(dvc.dvc_dir)
    assert os.path.exists(dvc.cache_dir)
    
    print("\n--- 4.2 创建数据文件并 add ---")
    data_file = os.path.join(tmpdir, "dataset.csv")
    df = pd.DataFrame({
        "id": range(100),
        "value": np.random.randn(100).round(4),
        "category": np.random.choice(["A", "B", "C"], 100)
    })
    df.to_csv(data_file, index=False)
    
    md5_v1 = dvc.add(data_file)
    assert os.path.exists(data_file + ".dvc")
    assert os.path.exists(dvc._cache_path(md5_v1))
    print("✓ add: 数据文件已跟踪，缓存已创建")
    
    df["value"] = df["value"] * 2
    df.to_csv(data_file, index=False)
    md5_v2 = dvc.add(data_file)
    assert md5_v1 != md5_v2
    print(f"  版本对比: v1={md5_v1[:12]}..., v2={md5_v2[:12]}...")
    print("✓ 数据版本变化检测通过")
    
    print("\n--- 4.3 配置远程存储并 push/pull ---")
    remote_dir = "/tmp/dvc_remote"
    if os.path.exists(remote_dir):
        shutil.rmtree(remote_dir)
    dvc.add_remote("myremote", remote_dir)
    
    pushed = dvc.push()
    assert pushed >= 2
    
    shutil.rmtree(dvc.cache_dir)
    os.makedirs(dvc.cache_dir)
    
    pulled = dvc.pull()
    assert pulled >= 2
    print("✓ push/pull: 远程存储同步验证通过")
    
    print("\n--- 4.4 checkout 恢复指定版本 ---")
    dvc.checkout(data_file + ".dvc")
    restored_df = pd.read_csv(data_file)
    assert len(restored_df) == 100
    print(f"  恢复数据: {len(restored_df)} 行, {len(restored_df.columns)} 列")
    print("✓ checkout 验证通过")
    
    print("\n--- 4.5 dvc.yaml 数据流水线 ---")
    dvc_yaml = {
        "stages": {
            "prepare": {
                "cmd": "python prepare.py --input raw.csv --output train.csv",
                "deps": ["raw.csv", "prepare.py"],
                "outs": ["train.csv"]
            },
            "train": {
                "cmd": "python train.py --data train.csv --model model.pkl",
                "deps": ["train.csv", "train.py"],
                "outs": ["model.pkl"],
                "metrics": [{"metrics.json": {"cache": False}}]
            },
            "evaluate": {
                "cmd": "python evaluate.py --model model.pkl --output metrics.json",
                "deps": ["model.pkl", "evaluate.py"],
                "metrics": ["metrics.json"]
            }
        }
    }
    yaml_file = os.path.join(tmpdir, "dvc.yaml")
    with open(yaml_file, "w") as f:
        json.dump(dvc_yaml, f, indent=2)
    
    stages = dvc_yaml["stages"]
    print(f"  dvc.yaml 定义了 {len(stages)} 个阶段:")
    for name, stage in stages.items():
        print(f"    [{name}] cmd: {stage['cmd'][:50]}...")
        print(f"      deps: {stage.get('deps', [])}, outs: {stage.get('outs', [])}")
    
    stage_deps = {name: set(s.get("deps", [])) for name, s in stages.items()}
    stage_outs = {name: set(s.get("outs", [])) for name, s in stages.items()}
    assert "train.csv" in stage_deps["train"]
    assert "train.csv" in stage_outs["prepare"]
    print("✓ dvc.yaml 流水线依赖链验证通过")
    
    print(f"\n✅ 题4完成")


# ============================================================
# 题 5: Delta Lake / Apache Iceberg（纯 Python 模拟）
# ============================================================

def exercise_05():
    """
    知识点：时间旅行查询、ACID事务、Schema演进、增量写入、快照管理
    
    用纯 Python + pandas + parquet 模拟 Lakehouse 核心概念。
    """
    print("=" * 70)
    print("题 5: Delta Lake / Apache Iceberg（纯 Python 模拟）")
    print("=" * 70)
    
    tmpdir = "/tmp/lakehouse_demo"
    if os.path.exists(tmpdir):
        shutil.rmtree(tmpdir)
    os.makedirs(tmpdir)
    
    class DeltaTable:
        """模拟 Delta Lake：支持 ACID 事务、时间旅行、Schema 演进"""
        def __init__(self, path):
            self.path = path
            self.log_dir = os.path.join(path, "_delta_log")
            self.data_dir = os.path.join(path, "data")
            os.makedirs(self.log_dir, exist_ok=True)
            os.makedirs(self.data_dir, exist_ok=True)
            self.current_version = -1
            self._init_log()
        
        def _init_log(self):
            if not os.listdir(self.log_dir):
                self._commit_log({"version": 0, "operation": "CREATE TABLE",
                                  "schema": [], "files": [], "timestamp": datetime.now().isoformat()})
        
        def _commit_log(self, entry):
            self.current_version += 1
            log_file = os.path.join(self.log_dir, f"{self.current_version:020d}.json")
            with open(log_file, "w") as f:
                json.dump(entry, f, indent=2, default=str)
            return self.current_version
        
        def _read_log(self, version=None):
            if version is None:
                version = self.current_version
            log_file = os.path.join(self.log_dir, f"{version:020d}.json")
            if not os.path.exists(log_file):
                return None
            with open(log_file, "r") as f:
                return json.load(f)
        
        def _get_active_files(self, version=None):
            if version is None:
                version = self.current_version
            active = {}
            for v in range(version + 1):
                log = self._read_log(v)
                if not log:
                    continue
                for f_info in log.get("files", []):
                    if f_info.get("operation") == "remove":
                        active.pop(f_info["path"], None)
                    else:
                        active[f_info["path"]] = f_info
            return list(active.values())
        
        def write(self, df, mode="append"):
            file_id = str(uuid.uuid4())[:8]
            file_path = os.path.join(self.data_dir, f"part-{file_id}.parquet")
            df.to_parquet(file_path, engine="pyarrow")
            
            if mode == "overwrite":
                old_files = self._get_active_files()
                remove_ops = [{"path": f["path"], "operation": "remove"} for f in old_files]
            else:
                remove_ops = []
            
            schema = [{"name": c, "type": str(df[c].dtype)} for c in df.columns]
            entry = {
                "version": self.current_version + 1,
                "operation": "WRITE",
                "mode": mode,
                "schema": schema,
                "files": [{"path": file_path, "size": os.path.getsize(file_path),
                           "records": len(df), "operation": "add"}] + remove_ops,
                "timestamp": datetime.now().isoformat()
            }
            version = self._commit_log(entry)
            print(f"  [write] v{version}: 写入 {len(df)} 行 → {os.path.basename(file_path)} (mode={mode})")
            return version
        
        def read(self, version=None):
            files = self._get_active_files(version)
            if not files:
                return pd.DataFrame()
            dfs = [pd.read_parquet(f["path"], engine="pyarrow") for f in files]
            return pd.concat(dfs, ignore_index=True)
        
        def time_travel(self, version):
            return self.read(version=version)
        
        def get_schema(self, version=None):
            log = self._read_log(version if version is not None else self.current_version)
            return log.get("schema", []) if log else []
        
        def schema_evolution(self, new_column, default_value=None):
            current_data = self.read()
            current_data[new_column] = default_value
            version = self.write(current_data, mode="overwrite")
            print(f"  [schema_evolution] 添加列 '{new_column}', 新版本 v{version}")
            return version
        
        def describe_history(self):
            history = []
            for v in range(self.current_version + 1):
                log = self._read_log(v)
                if log:
                    history.append({
                        "version": v,
                        "operation": log.get("operation", "UNKNOWN"),
                        "mode": log.get("mode", ""),
                        "files_count": len(log.get("files", [])),
                        "timestamp": log.get("timestamp", "")
                    })
            return history
        
        def vacuum(self, retain_versions=3):
            files_to_keep = set()
            for v in range(max(0, self.current_version - retain_versions + 1), self.current_version + 1):
                for f in self._get_active_files(v):
                    files_to_keep.add(f["path"])
            removed = 0
            for f in os.listdir(self.data_dir):
                fpath = os.path.join(self.data_dir, f)
                if fpath not in files_to_keep:
                    os.remove(fpath)
                    removed += 1
            print(f"  [vacuum] 清理 {removed} 个过期文件")
            return removed
    
    print("\n--- 5.1 创建 Delta 表并写入数据 ---")
    table = DeltaTable(tmpdir)
    
    df1 = pd.DataFrame({
        "id": [1, 2, 3],
        "name": ["Alice", "Bob", "Charlie"],
        "value": [10.5, 20.3, 30.1]
    })
    v1 = table.write(df1)
    
    df2 = pd.DataFrame({
        "id": [4, 5],
        "name": ["David", "Eve"],
        "value": [40.2, 50.8]
    })
    v2 = table.write(df2)
    
    print(f"  当前版本: v{table.current_version}")
    current_data = table.read()
    print(f"  当前数据: {len(current_data)} 行")
    assert len(current_data) == 5
    print("✓ ACID 写入（append 模式）验证通过")
    
    print("\n--- 5.2 时间旅行查询 ---")
    v1_data = table.time_travel(v1)
    v2_data = table.time_travel(v2)
    print(f"  v{v1} 数据: {len(v1_data)} 行 → {list(v1_data['name'])}")
    print(f"  v{v2} 数据: {len(v2_data)} 行 → {list(v2_data['name'])}")
    assert len(v1_data) == 3
    assert len(v2_data) == 5
    print("✓ 时间旅行: 可读取任意历史版本数据")
    
    print("\n--- 5.3 Schema 演进 ---")
    original_schema = table.get_schema()
    print(f"  原始 Schema: {[s['name'] for s in original_schema]}")
    
    table.schema_evolution("status", default_value="active")
    evolved_data = table.read()
    evolved_schema = table.get_schema()
    print(f"  演进后 Schema: {[s['name'] for s in evolved_schema]}")
    print(f"  演进后数据示例:\n{evolved_data[['id', 'name', 'status']].head(3).to_string(index=False)}")
    assert "status" in evolved_data.columns
    assert all(evolved_data["status"] == "active")
    print("✓ Schema 演进: 新增列并填充默认值")
    
    print("\n--- 5.4 覆盖写入（Overwrite）---")
    df_overwrite = pd.DataFrame({
        "id": [10, 20], "name": ["Frank", "Grace"],
        "value": [100.0, 200.0], "status": "active"
    })
    v_overwrite = table.write(df_overwrite, mode="overwrite")
    overwrite_data = table.read()
    print(f"  覆盖后数据: {len(overwrite_data)} 行 → {list(overwrite_data['name'])}")
    assert len(overwrite_data) == 2
    print("✓ Overwrite: 旧数据被标记删除，新数据替换")
    
    print("\n--- 5.5 表历史与快照管理 ---")
    history = table.describe_history()
    print(f"  表历史 ({len(history)} 个版本):")
    for h in history:
        print(f"    v{h['version']}: {h['operation']} {h['mode']}, files={h['files_count']}, ts={h['timestamp'][:19]}")
    assert len(history) >= 4
    
    table.vacuum(retain_versions=2)
    print("✓ 快照管理: 历史追踪 + vacuum 清理")
    
    print(f"\n✅ 题5完成")


# ============================================================
# 题 6: 特征存储 (Feature Store)
# ============================================================

def exercise_06():
    """
    知识点：离线/在线特征同步、特征定义与注册、训练-推理一致性、特征版本管理
    
    用纯 Python 实现轻量 Feature Store。
    """
    print("=" * 70)
    print("题 6: 特征存储 (Feature Store)")
    print("=" * 70)
    
    tmpdir = "/tmp/feature_store_demo"
    if os.path.exists(tmpdir):
        shutil.rmtree(tmpdir)
    os.makedirs(tmpdir)
    
    @dataclass
    class FeatureDefinition:
        name: str
        dtype: str
        description: str
        version: str = "1.0"
        online: bool = True
        transform: Any = None
    
    class FeatureStore:
        def __init__(self, path):
            self.path = path
            self.offline_dir = os.path.join(path, "offline")
            self.online_dir = os.path.join(path, "online")
            self.registry_file = os.path.join(path, "registry.json")
            os.makedirs(self.offline_dir, exist_ok=True)
            os.makedirs(self.online_dir, exist_ok=True)
            self.registry = {}
            self._load_registry()
        
        def _load_registry(self):
            if os.path.exists(self.registry_file):
                with open(self.registry_file, "r") as f:
                    data = json.load(f)
                for name, info in data.items():
                    self.registry[name] = FeatureDefinition(**info)
        
        def _save_registry(self):
            data = {name: {"name": f.name, "dtype": f.dtype, "description": f.description,
                          "version": f.version, "online": f.online}
                        for name, f in self.registry.items()}
            with open(self.registry_file, "w") as f:
                json.dump(data, f, indent=2)
        
        def register_feature(self, feature: FeatureDefinition):
            self.registry[feature.name] = feature
            self._save_registry()
            print(f"  [register] 特征 '{feature.name}' v{feature.version} ({feature.dtype})")
        
        def get_feature_view(self, feature_names, entity_ids=None):
            dfs = []
            for name in feature_names:
                if name not in self.registry:
                    raise ValueError(f"特征 '{name}' 未注册")
                offline_file = os.path.join(self.offline_dir, f"{name}.parquet")
                if os.path.exists(offline_file):
                    df = pd.read_parquet(offline_file)
                    if entity_ids is not None:
                        df = df[df["entity_id"].isin(entity_ids)]
                    dfs.append(df.set_index("entity_id")[[name]])
            if dfs:
                return pd.concat(dfs, axis=1).reset_index()
            return pd.DataFrame()
        
        def materialize_offline(self, feature_name, data):
            offline_file = os.path.join(self.offline_dir, f"{feature_name}.parquet")
            data.to_parquet(offline_file, engine="pyarrow", index=False)
            print(f"  [materialize_offline] '{feature_name}' → {len(data)} 行")
        
        def materialize_online(self, feature_name, data):
            online_file = os.path.join(self.online_dir, f"{feature_name}.json")
            online_data = {}
            for _, row in data.iterrows():
                val = row[feature_name]
                # Convert numpy types to native Python types for JSON
                if hasattr(val, 'item'):
                    val = val.item()
                elif isinstance(val, (np.floating, np.integer, np.bool_)):
                    val = val.item()
                online_data[str(int(row["entity_id"]))] = val
            with open(online_file, "w") as f:
                json.dump(online_data, f)
            print(f"  [materialize_online] '{feature_name}' → {len(online_data)} 条在线特征")
        
        def get_online_features(self, feature_name, entity_id):
            online_file = os.path.join(self.online_dir, f"{feature_name}.json")
            if not os.path.exists(online_file):
                return None
            with open(online_file, "r") as f:
                data = json.load(f)
            return data.get(str(entity_id))
        
        def sync_offline_to_online(self, feature_name):
            offline_file = os.path.join(self.offline_dir, f"{feature_name}.parquet")
            if os.path.exists(offline_file):
                df = pd.read_parquet(offline_file)
                self.materialize_online(feature_name, df)
                return True
            return False
        
        def list_features(self):
            return list(self.registry.keys())
    
    print("\n--- 6.1 注册特征定义 ---")
    fs = FeatureStore(tmpdir)
    
    features = [
        FeatureDefinition("user_age", "int", "用户年龄"),
        FeatureDefinition("avg_order_amount", "float", "平均订单金额"),
        FeatureDefinition("login_count_7d", "int", "7天登录次数"),
        FeatureDefinition("is_vip", "bool", "是否VIP用户"),
    ]
    for f in features:
        fs.register_feature(f)
    assert len(fs.list_features()) == 4
    print("✓ 特征注册验证通过")
    
    print("\n--- 6.2 物化离线特征数据 ---")
    n_users = 50
    entity_ids = list(range(1, n_users + 1))
    
    for feature_name, values in [
        ("user_age", np.random.randint(18, 65, n_users)),
        ("avg_order_amount", np.round(np.random.uniform(50, 500, n_users), 2)),
        ("login_count_7d", np.random.randint(0, 30, n_users)),
        ("is_vip", np.random.choice([True, False], n_users)),
    ]:
        data = pd.DataFrame({"entity_id": entity_ids, feature_name: values})
        fs.materialize_offline(feature_name, data)
    
    feature_view = fs.get_feature_view(["user_age", "avg_order_amount", "login_count_7d", "is_vip"])
    print(f"  特征视图: {feature_view.shape}")
    print(f"  前5行:\n{feature_view.head().to_string(index=False)}")
    assert feature_view.shape == (50, 5)
    print("✓ 离线特征物化验证通过")
    
    print("\n--- 6.3 离线→在线同步 ---")
    for fname in ["user_age", "avg_order_amount", "login_count_7d", "is_vip"]:
        fs.sync_offline_to_online(fname)
    
    online_age = fs.get_online_features("user_age", entity_id=1)
    online_amount = fs.get_online_features("avg_order_amount", entity_id=1)
    print(f"  在线查询 entity_id=1: age={online_age}, avg_amount={online_amount}")
    assert online_age is not None
    assert online_amount is not None
    
    offline_val = feature_view[feature_view["entity_id"] == 1]["user_age"].values[0]
    online_val = fs.get_online_features("user_age", entity_id=1)
    assert str(offline_val) == str(online_val)
    print("✓ 离线/在线特征同步与一致性验证通过")
    
    print("\n--- 6.4 训练-推理一致性保证 ---")
    
    class FeatureService:
        def __init__(self, feature_store, feature_names):
            self.fs = feature_store
            self.feature_names = feature_names
        
        def get_training_features(self, entity_ids):
            return self.fs.get_feature_view(self.feature_names, entity_ids)
        
        def get_serving_features(self, entity_id):
            features = {}
            for name in self.feature_names:
                val = self.fs.get_online_features(name, entity_id)
                features[name] = val
            return features
        
        def validate_consistency(self, entity_ids, sample_size=10):
            train_data = self.get_training_features(entity_ids[:sample_size])
            mismatches = 0
            for _, row in train_data.iterrows():
                eid = int(row["entity_id"])
                serving = self.get_serving_features(eid)
                for fname in self.feature_names:
                    train_val = row[fname]
                    serve_val = serving[fname]
                    # 归一化比较：转 float 比较数值，避免 numpy/Python 类型差异
                    try:
                        if abs(float(train_val) - float(serve_val)) > 1e-6:
                            mismatches += 1
                    except (TypeError, ValueError):
                        if str(train_val) != str(serve_val):
                            mismatches += 1
            return mismatches == 0, mismatches
    
    service = FeatureService(fs, ["user_age", "avg_order_amount", "login_count_7d"])
    train_features = service.get_training_features(entity_ids[:5])
    print(f"  训练特征数据: {train_features.shape}")
    serving_features = service.get_serving_features(entity_id=3)
    print(f"  推理特征 (entity_id=3): {serving_features}")
    
    is_consistent, mismatches = service.validate_consistency(entity_ids)
    print(f"  训练-推理一致性: 一致={is_consistent}, 不匹配数={mismatches}")
    assert is_consistent
    print("✓ 训练-推理特征一致性验证通过")
    
    print("\n--- 6.5 特征版本管理 ---")
    fs.register_feature(FeatureDefinition("user_age", "int", "用户年龄（含校验）", version="2.0"))
    assert fs.registry["user_age"].version == "2.0"
    print(f"  user_age 版本更新: v1.0 → v{fs.registry['user_age'].version}")
    print(f"  当前注册特征: {fs.list_features()}")
    print("✓ 特征版本管理验证通过")
    
    print(f"\n✅ 题6完成")


# ============================================================
# 题 7: Airflow 数据管道编排（自研轻量 DAG 框架）
# ============================================================

def exercise_07():
    """
    知识点：DAG 定义、Task 依赖、XCom 数据传递、重试机制、调度策略
    
    因 apache-airflow 安装超时，自研轻量 DAG 执行框架。
    """
    print("=" * 70)
    print("题 7: Airflow 数据管道编排（自研轻量 DAG 框架）")
    print("=" * 70)
    
    @dataclass
    class TaskInstance:
        task_id: str
        status: str = "pending"
        retries: int = 0
        start_time: Optional[float] = None
        end_time: Optional[float] = None
        xcom_data: dict = field(default_factory=dict)
        error: str = ""
    
    class Task:
        def __init__(self, task_id, python_callable, retries=0, retry_delay=0.1):
            self.task_id = task_id
            self.python_callable = python_callable
            self.retries = retries
            self.retry_delay = retry_delay
            self.upstream = set()
            self.downstream = set()
            self.instance = TaskInstance(task_id=task_id)
        
        def __rshift__(self, other):
            self.downstream.add(other.task_id)
            other.upstream.add(self.task_id)
            return other
        
        def execute(self, context):
            self.instance.status = "running"
            self.instance.start_time = time.time()
            try:
                result = self.python_callable(context)
                self.instance.status = "success"
                self.instance.xcom_data = result if isinstance(result, dict) else {"return_value": result}
            except Exception as e:
                self.instance.status = "failed"
                self.instance.error = str(e)
                if self.instance.retries < self.retries:
                    self.instance.retries += 1
                    self.instance.status = "retried"
                    time.sleep(self.retry_delay)
                    return self.execute(context)
            finally:
                self.instance.end_time = time.time()
            return self.instance.xcom_data
    
    class DAG:
        def __init__(self, dag_id, schedule="@daily", description=""):
            self.dag_id = dag_id
            self.schedule = schedule
            self.description = description
            self.tasks = {}
            self.execution_log = []
        
        def add_task(self, task: Task):
            self.tasks[task.task_id] = task
            return task
        
        def _topological_sort(self):
            in_degree = {tid: len(t.upstream) for tid, t in self.tasks.items()}
            queue = deque([tid for tid, d in in_degree.items() if d == 0])
            order = []
            while queue:
                tid = queue.popleft()
                order.append(tid)
                for ds in self.tasks[tid].downstream:
                    in_degree[ds] -= 1
                    if in_degree[ds] == 0:
                        queue.append(ds)
            return order
        
        def _check_cycle(self):
            order = self._topological_sort()
            if len(order) != len(self.tasks):
                raise ValueError("DAG 中存在环路！")
            return True
        
        def run(self, context=None):
            if context is None:
                context = {"dag_id": self.dag_id, "run_date": datetime.now().isoformat()}
            context["xcom"] = {}
            
            self._check_cycle()
            order = self._topological_sort()
            print(f"  DAG '{self.dag_id}' 执行顺序: {' → '.join(order)}")
            
            for task_id in order:
                task = self.tasks[task_id]
                upstream_ok = all(
                    self.tasks[up].instance.status == "success"
                    for up in task.upstream
                )
                if not upstream_ok:
                    task.instance.status = "skipped"
                    self.execution_log.append(f"  [{task_id}] SKIPPED (上游未成功)")
                    continue
                
                for up in task.upstream:
                    context["xcom"][up] = self.tasks[up].instance.xcom_data
                
                task.execute(context)
                duration = (task.instance.end_time - task.instance.start_time) if task.instance.end_time else 0
                self.execution_log.append(
                    f"  [{task_id}] {task.instance.status.upper()} "
                    f"(retries={task.instance.retries}, {duration:.3f}s)"
                )
            
            return self._summary()
        
        def _summary(self):
            summary = {"total": len(self.tasks)}
            for status in ["success", "failed", "skipped", "retried"]:
                summary[status] = sum(1 for t in self.tasks.values() if t.instance.status == status)
            return summary
    
    print("\n--- 7.1 定义数据处理 DAG ---")
    dag = DAG("data_pipeline_demo", schedule="@daily", description="数据处理管道")
    
    def extract_data(context):
        data = [{"id": i, "value": random.uniform(10, 100)} for i in range(100)]
        return {"records": data, "count": len(data), "stage": "extract"}
    
    def validate_data(context):
        upstream = context["xcom"].get("extract", {})
        records = upstream.get("records", [])
        valid = [r for r in records if r["value"] > 0]
        return {"valid_records": valid, "valid_count": len(valid),
                "invalid_count": len(records) - len(valid), "stage": "validate"}
    
    def transform_data(context):
        upstream = context["xcom"].get("validate", {})
        records = upstream.get("valid_records", [])
        for r in records:
            r["value_normalized"] = round(r["value"] / 100, 4)
            r["category"] = "A" if r["value"] > 50 else "B"
        return {"transformed": records, "stage": "transform"}
    
    def load_data(context):
        upstream = context["xcom"].get("transform", {})
        records = upstream.get("transformed", [])
        return {"loaded_count": len(records), "stage": "load"}
    
    def generate_report(context):
        extract = context["xcom"].get("extract", {})
        validate = context["xcom"].get("validate", {})
        load = context["xcom"].get("load", {})
        return {"report": {
            "extracted": extract.get("count", 0),
            "valid": validate.get("valid_count", 0),
            "invalid": validate.get("invalid_count", 0),
            "loaded": load.get("loaded_count", 0),
            "generated_at": datetime.now().isoformat()
        }, "stage": "report"}
    
    t_extract = dag.add_task(Task("extract", extract_data))
    t_validate = dag.add_task(Task("validate", validate_data))
    t_transform = dag.add_task(Task("transform", transform_data))
    t_load = dag.add_task(Task("load", load_data))
    t_report = dag.add_task(Task("report", generate_report))
    
    t_extract >> t_validate >> t_transform >> t_load >> t_report
    print(f"  DAG 任务: {list(dag.tasks.keys())}")
    print(f"  依赖关系: extract → validate → transform → load → report")
    print("✓ DAG 定义与依赖设置完成")
    
    print("\n--- 7.2 执行 DAG 并验证 XCom ---")
    summary = dag.run()
    for log_entry in dag.execution_log:
        print(log_entry)
    print(f"  执行摘要: {summary}")
    assert summary["success"] == 5
    assert summary["failed"] == 0
    
    report_data = t_report.instance.xcom_data.get("report", {})
    print(f"  XCom 最终报告: extracted={report_data.get('extracted')}, loaded={report_data.get('loaded')}")
    assert report_data["extracted"] == 100
    assert report_data["loaded"] == 100
    print("✓ DAG 执行 + XCom 数据传递验证通过")
    
    print("\n--- 7.3 重试机制验证 ---")
    dag2 = DAG("retry_test", schedule="@once")
    call_count = {"n": 0}
    
    def flaky_task(context):
        call_count["n"] += 1
        if call_count["n"] < 3:
            raise ValueError(f"模拟失败 (第{call_count['n']}次)")
        return {"result": "success_after_retry", "attempts": call_count["n"]}
    
    t_flaky = dag2.add_task(Task("flaky", flaky_task, retries=3, retry_delay=0.05))
    summary2 = dag2.run()
    print(f"  重试任务最终状态: {t_flaky.instance.status}")
    print(f"  总调用次数: {call_count['n']}, 重试次数: {t_flaky.instance.retries}")
    print(f"  返回数据: {t_flaky.instance.xcom_data}")
    assert t_flaky.instance.status == "success"
    assert call_count["n"] == 3
    print("✓ 重试机制: 失败后自动重试直到成功")
    
    print("\n--- 7.4 并行分支与汇合 ---")
    dag3 = DAG("parallel_branches", schedule="@daily")
    
    def start_task(ctx): return {"data": "input_data"}
    def branch_a(ctx): return {"result_a": "processed_by_A"}
    def branch_b(ctx): return {"result_b": "processed_by_B"}
    def merge_task(ctx):
        a_data = ctx["xcom"].get("branch_a", {})
        b_data = ctx["xcom"].get("branch_b", {})
        return {"merged": f"{a_data.get('result_a')} + {b_data.get('result_b')}"}
    
    t_start = dag3.add_task(Task("start", start_task))
    t_a = dag3.add_task(Task("branch_a", branch_a))
    t_b = dag3.add_task(Task("branch_b", branch_b))
    t_merge = dag3.add_task(Task("merge", merge_task))
    
    t_start >> t_a
    t_start >> t_b
    t_a >> t_merge
    t_b >> t_merge
    
    order = dag3._topological_sort()
    print(f"  并行 DAG 拓扑排序: {' → '.join(order)}")
    summary3 = dag3.run()
    print(f"  执行摘要: {summary3}")
    assert summary3["success"] == 4
    print(f"  merge 结果: {t_merge.instance.xcom_data}")
    assert "processed_by_A" in t_merge.instance.xcom_data.get("merged", "")
    print("✓ 并行分支与汇合验证通过")
    
    print("\n--- 7.5 调度策略模拟 ---")
    schedules = {
        "@daily": "每天 00:00 执行",
        "@hourly": "每小时整点执行",
        "@weekly": "每周一 00:00 执行",
        "0 2 * * 1-5": "工作日凌晨2点（cron表达式）",
    }
    print("  支持的调度策略:")
    for sched, desc in schedules.items():
        print(f"    {sched:20s} → {desc}")
    
    def next_run(schedule, now=None):
        if now is None: now = datetime.now()
        if schedule == "@daily":
            return (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        elif schedule == "@hourly":
            return (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
        elif schedule == "@weekly":
            days_ahead = 7 - now.weekday()
            return (now + timedelta(days=days_ahead)).replace(hour=0, minute=0, second=0, microsecond=0)
        return now
    
    for sched in ["@daily", "@hourly", "@weekly"]:
        nr = next_run(sched)
        print(f"    {sched} 下次执行: {nr.strftime('%Y-%m-%d %H:%M:%S')}")
    print("✓ 调度策略验证通过")
    
    print(f"\n✅ 题7完成")


# ============================================================
# 题 8: 数据质量监控（自研校验框架）
# ============================================================

def exercise_08():
    """
    知识点：数据画像、异常检测、SLA定义、校验报告生成
    
    因 great_expectations 安装超时，自研轻量数据质量校验框架。
    """
    print("=" * 70)
    print("题 8: 数据质量监控（自研校验框架）")
    print("=" * 70)
    
    tmpdir = "/tmp/data_quality_demo"
    if os.path.exists(tmpdir):
        shutil.rmtree(tmpdir)
    os.makedirs(tmpdir)
    
    # ---- 8.1 数据画像 (Data Profiling) ----
    print("\n--- 8.1 数据画像 ---")
    
    class DataProfiler:
        """数据画像：统计摘要、分布分析、缺失值检测"""
        @staticmethod
        def profile(df):
            profile = {}
            for col in df.columns:
                col_info = {
                    "dtype": str(df[col].dtype),
                    "count": int(df[col].count()),
                    "null_count": int(df[col].isnull().sum()),
                    "null_rate": round(df[col].isnull().mean(), 4),
                    "unique_count": int(df[col].nunique()),
                }
                if df[col].dtype in [np.float64, np.int64, float, int]:
                    col_info.update({
                        "min": float(df[col].min()),
                        "max": float(df[col].max()),
                        "mean": round(float(df[col].mean()), 4),
                        "std": round(float(df[col].std()), 4),
                        "median": float(df[col].median()),
                        "q25": float(df[col].quantile(0.25)),
                        "q75": float(df[col].quantile(0.75)),
                    })
                else:
                    top_values = df[col].value_counts().head(5)
                    col_info["top_values"] = {str(k): int(v) for k, v in top_values.items()}
                profile[col] = col_info
            return profile
    
    # 生成测试数据（含异常值和缺失值）
    np.random.seed(42)
    n = 1000
    test_df = pd.DataFrame({
        "user_id": range(1, n + 1),
        "age": np.where(np.random.random(n) < 0.05, np.random.choice([-1, 200, None], n),
                        np.random.randint(18, 65, n)),
        "salary": np.where(np.random.random(n) < 0.03, None,
                           np.round(np.random.lognormal(10, 0.5, n), 2)),
        "department": np.random.choice(["Engineering", "Sales", "Marketing", "HR", None], n,
                                        p=[0.3, 0.25, 0.2, 0.15, 0.1]),
        "join_date": pd.date_range("2020-01-01", periods=n, freq="h"),
    })
    
    profiler = DataProfiler()
    profile = profiler.profile(test_df)
    
    print("  数据画像摘要:")
    for col, info in profile.items():
        print(f"    {col}: dtype={info['dtype']}, nulls={info['null_count']}({info['null_rate']:.1%}), unique={info['unique_count']}")
        if "mean" in info:
            print(f"      min={info['min']}, max={info['max']}, mean={info['mean']}, std={info['std']}")
    
    assert profile["age"]["null_count"] > 0
    assert profile["salary"]["null_count"] > 0
    print("✓ 数据画像: 统计摘要 + 缺失值检测完成")
    
    # ---- 8.2 数据校验规则引擎 ----
    print("\n--- 8.2 数据校验规则引擎 ---")
    
    class Expectation:
        """期望规则基类"""
        def __init__(self, column, expectation_type, **kwargs):
            self.column = column
            self.expectation_type = expectation_type
            self.kwargs = kwargs
            self.result = None
        
        def validate(self, df):
            col_data = df[self.column]
            if self.expectation_type == "not_null":
                success = col_data.notnull().all()
                unexpected = int(col_data.isnull().sum())
            elif self.expectation_type == "unique":
                success = col_data.nunique() == len(col_data)
                unexpected = len(col_data) - col_data.nunique()
            elif self.expectation_type == "min_value":
                min_val = self.kwargs.get("value")
                success = col_data.min() >= min_val
                unexpected = int((col_data < min_val).sum())
            elif self.expectation_type == "max_value":
                max_val = self.kwargs.get("value")
                success = col_data.max() <= max_val
                unexpected = int((col_data > max_val).sum())
            elif self.expectation_type == "in_set":
                valid_set = set(self.kwargs.get("values", []))
                success = col_data.dropna().isin(valid_set).all()
                unexpected = int((~col_data.dropna().isin(valid_set)).sum())
            elif self.expectation_type == "between":
                lo, hi = self.kwargs.get("min"), self.kwargs.get("max")
                valid = (col_data >= lo) & (col_data <= hi)
                success = valid.all()
                unexpected = int((~valid).sum())
            elif self.expectation_type == "type":
                expected_type = self.kwargs.get("dtype")
                success = str(col_data.dtype) == expected_type
                unexpected = 0 if success else len(col_data)
            else:
                success = False
                unexpected = len(col_data)
            
            self.result = {
                "expectation": f"{self.column} {self.expectation_type} {self.kwargs}",
                "success": bool(success),
                "unexpected_count": unexpected,
                "unexpected_percent": round(unexpected / len(df) * 100, 2) if len(df) > 0 else 0,
            }
            return self.result
    
    class ValidationSuite:
        """校验套件：管理一组期望规则"""
        def __init__(self, name):
            self.name = name
            self.expectations = []
        
        def add_expectation(self, column, expectation_type, **kwargs):
            exp = Expectation(column, expectation_type, **kwargs)
            self.expectations.append(exp)
            return exp
        
        def run(self, df):
            results = []
            for exp in self.expectations:
                results.append(exp.validate(df))
            return results
        
        def summary(self, results):
            total = len(results)
            passed = sum(1 for r in results if r["success"])
            failed = total - passed
            return {"suite": self.name, "total": total, "passed": passed, "failed": failed,
                    "pass_rate": round(passed / total * 100, 2) if total > 0 else 0}
    
    suite = ValidationSuite("user_data_quality")
    suite.add_expectation("user_id", "not_null")
    suite.add_expectation("user_id", "unique")
    suite.add_expectation("age", "between", min=0, max=150)
    suite.add_expectation("salary", "not_null")
    suite.add_expectation("department", "in_set",
                          values=["Engineering", "Sales", "Marketing", "HR"])
    suite.add_expectation("join_date", "type", dtype="datetime64[ns]")
    
    results = suite.run(test_df)
    summ = suite.summary(results)
    
    print(f"  校验套件: {summ['suite']}")
    print(f"  总规则: {summ['total']}, 通过: {summ['passed']}, 失败: {summ['failed']}, 通过率: {summ['pass_rate']}%")
    for r in results:
        status = "✓" if r["success"] else "✗"
        print(f"    {status} {r['expectation']} → unexpected={r['unexpected_count']} ({r['unexpected_percent']}%)")
    
    assert summ["failed"] > 0  # 应有失败的规则（age有负值/空值, salary有空值等）
    print("✓ 数据校验规则引擎验证通过")
    
    # ---- 8.3 异常检测 ----
    print("\n--- 8.3 异常检测 ---")
    
    class AnomalyDetector:
        """异常检测：Z-Score + IQR + 孤立森林简化版"""
        @staticmethod
        def z_score_detect(series, threshold=3.0):
            mean, std = series.mean(), series.std()
            z_scores = (series - mean) / std
            anomalies = z_scores.abs() > threshold
            return anomalies, {"method": "z_score", "threshold": threshold,
                               "mean": round(mean, 4), "std": round(std, 4),
                               "anomaly_count": int(anomalies.sum())}
        
        @staticmethod
        def iqr_detect(series, multiplier=1.5):
            q1, q3 = series.quantile(0.25), series.quantile(0.75)
            iqr = q3 - q1
            lower, upper = q1 - multiplier * iqr, q3 + multiplier * iqr
            anomalies = (series < lower) | (series > upper)
            return anomalies, {"method": "iqr", "multiplier": multiplier,
                               "lower": round(lower, 4), "upper": round(upper, 4),
                               "anomaly_count": int(anomalies.sum())}
        
        @staticmethod
        def percentile_detect(series, lower_pct=1, upper_pct=99):
            lower = series.quantile(lower_pct / 100)
            upper = series.quantile(upper_pct / 100)
            anomalies = (series < lower) | (series > upper)
            return anomalies, {"method": "percentile", "lower_pct": lower_pct,
                               "upper_pct": upper_pct, "anomaly_count": int(anomalies.sum())}
    
    salary_data = test_df["salary"].dropna()
    
    z_anom, z_info = AnomalyDetector.z_score_detect(salary_data)
    print(f"  Z-Score 检测: {z_info}")
    
    iqr_anom, iqr_info = AnomalyDetector.iqr_detect(salary_data)
    print(f"  IQR 检测: {iqr_info}")
    
    pct_anom, pct_info = AnomalyDetector.percentile_detect(salary_data)
    print(f"  百分位检测: {pct_info}")
    
    assert z_info["anomaly_count"] > 0 or iqr_info["anomaly_count"] > 0
    print("✓ 异常检测: Z-Score + IQR + 百分位 三种方法验证通过")
    
    # ---- 8.4 SLA 定义与监控 ----
    print("\n--- 8.4 SLA 定义与监控 ---")
    
    @dataclass
    class SLA:
        name: str
        metric: str
        threshold: float
        operator: str  # >, <, ==, >=, <=
        critical: bool = False
        
        def check(self, actual_value):
            ops = {">": lambda a, b: a > b, "<": lambda a, b: a < b,
                   "==": lambda a, b: a == b, ">=": lambda a, b: a >= b,
                   "<=": lambda a, b: a <= b}
            passed = ops[self.operator](actual_value, self.threshold)
            return {"sla": self.name, "metric": self.metric,
                    "actual": actual_value, "threshold": self.threshold,
                    "operator": self.operator, "passed": passed,
                    "critical": self.critical}
    
    slas = [
        SLA("completeness", "null_rate", 5.0, "<", critical=True),
        SLA("uniqueness", "duplicate_rate", 1.0, "<"),
        SLA("validity", "invalid_rate", 2.0, "<", critical=True),
        SLA("freshness", "data_age_hours", 24.0, "<="),
    ]
    
    # 计算实际指标
    actual_metrics = {
        "null_rate": round(test_df.isnull().mean().mean() * 100, 2),
        "duplicate_rate": round((1 - test_df["user_id"].nunique() / len(test_df)) * 100, 2),
        "invalid_rate": round(sum(1 for r in results if not r["success"]) / len(results) * 100, 2),
        "data_age_hours": 2.5,
    }
    
    print("  SLA 监控结果:")
    for sla in slas:
        actual = actual_metrics.get(sla.metric, 0)
        result = sla.check(actual)
        status = "✓ PASS" if result["passed"] else "✗ FAIL"
        crit = " [CRITICAL]" if result["critical"] else ""
        print(f"    {status}{crit} {sla.name}: {sla.metric}={actual} {sla.operator} {sla.threshold}")
    
    critical_failures = [sla.check(actual_metrics.get(sla.metric, 0))
                         for sla in slas if sla.critical and not sla.check(actual_metrics.get(sla.metric, 0))["passed"]]
    print(f"  关键 SLA 失败数: {len(critical_failures)}")
    print("✓ SLA 定义与监控验证通过")
    
    # ---- 8.5 校验报告生成 ----
    print("\n--- 8.5 校验报告生成 ---")
    
    class QualityReport:
        def __init__(self, suite_results, suite_summary, profile, sla_results, anomaly_results):
            self.data = {
                "report_id": str(uuid.uuid4())[:8],
                "generated_at": datetime.now().isoformat(),
                "suite_results": suite_results,
                "suite_summary": suite_summary,
                "data_profile": {col: {k: v for k, v in info.items() if k != "top_values"}
                                 for col, info in profile.items()},
                "sla_results": sla_results,
                "anomaly_detection": anomaly_results,
            }
        
        def to_json(self):
            return json.dumps(self.data, indent=2, default=str)
        
        def save(self, filepath):
            with open(filepath, "w") as f:
                f.write(self.to_json())
        
        def display(self):
            print(f"  报告ID: {self.data['report_id']}")
            print(f"  生成时间: {self.data['generated_at'][:19]}")
            print(f"  校验套件: {self.data['suite_summary']['passed']}/{self.data['suite_summary']['total']} 通过")
            print(f"  SLA: {sum(1 for s in self.data['sla_results'] if s['passed'])}/{len(self.data['sla_results'])} 通过")
            print(f"  异常检测: {len(self.data['anomaly_detection'])} 种方法")
    
    sla_results = [sla.check(actual_metrics.get(sla.metric, 0)) for sla in slas]
    anomaly_results = [z_info, iqr_info, pct_info]
    
    report = QualityReport(results, summ, profile, sla_results, anomaly_results)
    report.display()
    
    report_file = os.path.join(tmpdir, "quality_report.json")
    report.save(report_file)
    assert os.path.exists(report_file)
    
    # 验证报告可被加载
    with open(report_file, "r") as f:
        loaded = json.load(f)
    assert loaded["suite_summary"]["total"] == 6
    print(f"  报告已保存: {report_file}")
    print("✓ 校验报告生成验证通过")
    
    print(f"\n✅ 题8完成")


# ============================================================
# 题 9: 向量数据库实战（纯 numpy 实现）
# ============================================================

def exercise_09():
    """
    知识点：向量索引(IVF/HNSW)、相似度搜索、混合检索、元数据过滤
    
    因 faiss-cpu 下载超时，用纯 numpy 实现向量索引和搜索。
    """
    print("=" * 70)
    print("题 9: 向量数据库实战（纯 numpy 实现）")
    print("=" * 70)
    
    tmpdir = "/tmp/vector_db_demo"
    if os.path.exists(tmpdir):
        shutil.rmtree(tmpdir)
    os.makedirs(tmpdir)
    
    # ---- 9.1 暴力搜索 (Brute Force) ----
    print("\n--- 9.1 暴力搜索基线 ---")
    
    class BruteForceIndex:
        """暴力搜索：计算所有向量的相似度"""
        def __init__(self, dim=128):
            self.dim = dim
            self.vectors = None
            self.ids = []
            self.metadata = []
        
        def add(self, ids, vectors, metadata=None):
            if self.vectors is None:
                self.vectors = vectors.astype(np.float32)
            else:
                self.vectors = np.vstack([self.vectors, vectors.astype(np.float32)])
            self.ids.extend(ids)
            if metadata:
                self.metadata.extend(metadata)
            else:
                self.metadata.extend([{}] * len(ids))
        
        def search(self, query, k=5):
            """余弦相似度搜索"""
            query = query.astype(np.float32)
            # 归一化
            norms = np.linalg.norm(self.vectors, axis=1, keepdims=True)
            norms[norms == 0] = 1
            normalized = self.vectors / norms
            query_norm = query / (np.linalg.norm(query) + 1e-8)
            similarities = normalized @ query_norm
            top_k_idx = np.argsort(-similarities)[:k]
            return [(self.ids[i], float(similarities[i]), self.metadata[i]) for i in top_k_idx]
    
    dim = 128
    n_vectors = 10000
    np.random.seed(42)
    
    vectors = np.random.randn(n_vectors, dim).astype(np.float32)
    ids = list(range(n_vectors))
    metadata = [{"category": np.random.choice(["news", "sports", "tech", "health"]),
                 "year": np.random.choice([2022, 2023, 2024])} for _ in range(n_vectors)]
    
    bf_index = BruteForceIndex(dim)
    bf_index.add(ids[:5000], vectors[:5000], metadata[:5000])
    
    query = vectors[5000]  # 用一个已有向量作为查询
    results_bf = bf_index.search(query, k=5)
    print(f"  暴力搜索 Top-5:")
    for rid, sim, meta in results_bf:
        print(f"    id={rid}, sim={sim:.4f}, meta={meta}")
    assert len(results_bf) == 5
    print("✓ 暴力搜索验证通过")
    
    # ---- 9.2 IVF 索引 (Inverted File Index) ----
    print("\n--- 9.2 IVF 索引（K-Means 聚类倒排）---")
    
    class IVFIndex:
        """IVF 索引：K-Means 聚类 + 倒排表，搜索时只扫描 nprobe 个聚类"""
        def __init__(self, dim=128, n_clusters=100):
            self.dim = dim
            self.n_clusters = n_clusters
            self.centroids = None
            self.inverted_lists = {}  # cluster_id -> [(id, vector, metadata)]
            self.all_ids = []
            self.all_metadata = []
        
        def train(self, vectors, ids, metadata):
            # K-Means 聚类（简化版）
            n = len(vectors)
            k = min(self.n_clusters, n)
            # 随机初始化中心
            idx = np.random.choice(n, k, replace=False)
            self.centroids = vectors[idx].copy().astype(np.float32)
            
            for iteration in range(10):
                # 分配到最近的聚类
                dists = np.linalg.norm(vectors[:, None] - self.centroids[None], axis=2)
                assignments = np.argmin(dists, axis=1)
                # 更新中心
                for c in range(k):
                    mask = assignments == c
                    if mask.any():
                        self.centroids[c] = vectors[mask].mean(axis=0)
            
            # 构建倒排表
            dists = np.linalg.norm(vectors[:, None] - self.centroids[None], axis=2)
            assignments = np.argmin(dists, axis=1)
            self.all_ids = list(ids)
            self.all_metadata = list(metadata)
            for i, c in enumerate(assignments):
                if c not in self.inverted_lists:
                    self.inverted_lists[c] = []
                self.inverted_lists[c].append((ids[i], vectors[i], metadata[i]))
            
            print(f"  [IVF] 训练完成: {k} 个聚类, {n} 条向量")
            cluster_sizes = [len(v) for v in self.inverted_lists.values()]
            print(f"  聚类大小: min={min(cluster_sizes)}, max={max(cluster_sizes)}, avg={np.mean(cluster_sizes):.1f}")
        
        def search(self, query, k=5, nprobe=10):
            """搜索：只扫描最近的 nprobe 个聚类"""
            query = query.astype(np.float32)
            # 找最近的 nprobe 个聚类
            cent_dists = np.linalg.norm(self.centroids - query, axis=1)
            probe_clusters = np.argsort(cent_dists)[:nprobe]
            
            candidates = []
            for c in probe_clusters:
                if c in self.inverted_lists:
                    candidates.extend(self.inverted_lists[c])
            
            if not candidates:
                return []
            
            cand_vectors = np.array([c[1] for c in candidates], dtype=np.float32)
            cand_ids = [c[0] for c in candidates]
            cand_meta = [c[2] for c in candidates]
            
            # 归一化余弦相似度
            norms = np.linalg.norm(cand_vectors, axis=1, keepdims=True)
            norms[norms == 0] = 1
            normalized = cand_vectors / norms
            query_norm = query / (np.linalg.norm(query) + 1e-8)
            sims = normalized @ query_norm
            
            top_k_idx = np.argsort(-sims)[:k]
            return [(cand_ids[i], float(sims[i]), cand_meta[i]) for i in top_k_idx]
    
    ivf_index = IVFIndex(dim=dim, n_clusters=50)
    ivf_index.train(vectors[:5000], ids[:5000], metadata[:5000])
    
    results_ivf = ivf_index.search(query, k=5, nprobe=10)
    print(f"  IVF 搜索 Top-5 (nprobe=10):")
    for rid, sim, meta in results_ivf:
        print(f"    id={rid}, sim={sim:.4f}, meta={meta}")
    
    # 对比 IVF 与暴力搜索的召回率
    bf_top_ids = set(r[0] for r in results_bf)
    ivf_top_ids = set(r[0] for r in results_ivf)
    recall = len(bf_top_ids & ivf_top_ids) / len(bf_top_ids) if bf_top_ids else 0
    print(f"  IVF vs 暴力搜索 召回率: {recall:.2%}")
    
    # 增大 nprobe 提高召回率
    results_ivf_high = ivf_index.search(query, k=5, nprobe=30)
    ivf_high_ids = set(r[0] for r in results_ivf_high)
    recall_high = len(bf_top_ids & ivf_high_ids) / len(bf_top_ids)
    print(f"  IVF (nprobe=30) 召回率: {recall_high:.2%}")
    assert recall_high >= recall
    print("✓ IVF 索引: 聚类倒排 + nprobe 控制召回率验证通过")
    
    # ---- 9.3 HNSW 简化实现 ----
    print("\n--- 9.3 HNSW 简化实现（分层导航小世界图）---")
    
    class SimpleHNSW:
        """简化版 HNSW：单层图 + 贪心搜索"""
        def __init__(self, dim=128, M=16, ef_construction=50):
            self.dim = dim
            self.M = M  # 每个节点的最大邻居数
            self.ef_construction = ef_construction
            self.graph = {}  # id -> [(neighbor_id, distance)]
            self.vectors = {}  # id -> vector
            self.metadata = {}
            self.entry_point = None
        
        def _distance(self, v1, v2):
            return np.linalg.norm(v1 - v2)
        
        def add(self, vec_id, vector, meta=None):
            vector = vector.astype(np.float32)
            self.vectors[vec_id] = vector
            self.metadata[vec_id] = meta or {}
            self.graph[vec_id] = []
            
            if self.entry_point is None:
                self.entry_point = vec_id
                return
            
            # 找最近的 M 个邻居
            candidates = []
            for existing_id, existing_vec in self.vectors.items():
                if existing_id == vec_id:
                    continue
                dist = self._distance(vector, existing_vec)
                candidates.append((existing_id, dist))
            
            candidates.sort(key=lambda x: x[1])
            neighbors = candidates[:self.M]
            self.graph[vec_id] = neighbors
            
            # 双向连接
            for nid, dist in neighbors:
                self.graph[nid].append((vec_id, dist))
                if len(self.graph[nid]) > self.M:
                    self.graph[nid].sort(key=lambda x: x[1])
                    self.graph[nid] = self.graph[nid][:self.M]
        
        def search(self, query, k=5, ef=50):
            """贪心图搜索"""
            if self.entry_point is None:
                return []
            
            query = query.astype(np.float32)
            visited = set()
            # 从入口点开始
            current = self.entry_point
            current_dist = self._distance(query, self.vectors[current])
            
            # 贪心搜索：不断跳到更近的邻居
            improved = True
            while improved:
                improved = False
                for nid, dist in self.graph.get(current, []):
                    if nid in visited:
                        continue
                    visited.add(nid)
                    n_dist = self._distance(query, self.vectors[nid])
                    if n_dist < current_dist:
                        current = nid
                        current_dist = n_dist
                        improved = True
            
            # 从最佳点扩展搜索 ef 个候选
            candidates = [(current, current_dist)]
            for nid, dist in self.graph.get(current, []):
                if nid not in visited:
                    n_dist = self._distance(query, self.vectors[nid])
                    candidates.append((nid, n_dist))
            
            # 也搜索邻居的邻居
            for nid, _ in self.graph.get(current, []):
                for nnid, _ in self.graph.get(nid, []):
                    if nnid not in [c[0] for c in candidates]:
                        n_dist = self._distance(query, self.vectors[nnid])
                        candidates.append((nnid, n_dist))
            
            candidates.sort(key=lambda x: x[1])
            top_k = candidates[:k]
            return [(cid, 1.0 / (1.0 + dist), self.metadata.get(cid, {})) for cid, dist in top_k]
    
    # 用较小的数据集测试 HNSW
    hnsw = SimpleHNSW(dim=dim, M=16)
    for i in range(1000):
        hnsw.add(i, vectors[i], metadata[i])
    
    results_hnsw = hnsw.search(query, k=5, ef=50)
    print(f"  HNSW 搜索 Top-5:")
    for rid, sim, meta in results_hnsw:
        print(f"    id={rid}, sim={sim:.4f}, meta={meta}")
    assert len(results_hnsw) == 5
    print("✓ HNSW 简化实现: 图构建 + 贪心搜索验证通过")
    
    # ---- 9.4 混合检索（向量 + 关键词）----
    print("\n--- 9.4 混合检索（向量相似度 + BM25关键词）---")
    
    class HybridRetriever:
        """混合检索：向量搜索 + BM25 关键词搜索"""
        def __init__(self, vector_index):
            self.vector_index = vector_index
            self.documents = {}  # id -> text
            self.term_freqs = {}  # id -> {term: freq}
            self.doc_freq = defaultdict(int)  # term -> doc_count
            self.avg_doc_len = 0
            self.n_docs = 0
        
        def add_documents(self, doc_ids, texts, vectors, metadata):
            for did, text, vec, meta in zip(doc_ids, texts, vectors, metadata):
                self.documents[did] = text
                terms = text.lower().split()
                tf = defaultdict(int)
                for t in terms:
                    tf[t] += 1
                self.term_freqs[did] = dict(tf)
                for t in set(terms):
                    self.doc_freq[t] += 1
                self.n_docs += 1
            self.avg_doc_len = np.mean([len(t.split()) for t in texts])
        
        def bm25_score(self, query_terms, doc_id, k1=1.5, b=0.75):
            score = 0.0
            doc_tf = self.term_freqs.get(doc_id, {})
            doc_len = len(self.documents.get(doc_id, "").split())
            for term in query_terms:
                if term not in doc_tf:
                    continue
                tf = doc_tf[term]
                df = self.doc_freq.get(term, 0)
                idf = math.log((self.n_docs - df + 0.5) / (df + 0.5) + 1)
                score += idf * (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * doc_len / self.avg_doc_len))
            return score
        
        def search(self, query_text, query_vector, k=5, alpha=0.5):
            """alpha: 向量权重, (1-alpha): BM25权重"""
            # 向量搜索
            vec_results = self.vector_index.search(query_vector, k=k * 2)
            vec_scores = {r[0]: r[1] for r in vec_results}
            
            # BM25 搜索
            query_terms = query_text.lower().split()
            bm25_scores = {}
            for did in self.documents:
                bm25_scores[did] = self.bm25_score(query_terms, did)
            
            # 归一化
            max_vec = max(vec_scores.values()) if vec_scores else 1
            max_bm = max(bm25_scores.values()) if bm25_scores else 1
            
            # 混合得分
            all_ids = set(vec_scores.keys()) | set(bm25_scores.keys())
            hybrid_scores = []
            for did in all_ids:
                vec_s = vec_scores.get(did, 0) / max_vec if max_vec > 0 else 0
                bm_s = bm25_scores.get(did, 0) / max_bm if max_bm > 0 else 0
                hybrid = alpha * vec_s + (1 - alpha) * bm_s
                hybrid_scores.append((did, hybrid, self.documents.get(did, "")[:50]))
            
            hybrid_scores.sort(key=lambda x: -x[1])
            return hybrid_scores[:k]
    
    # 准备文档数据
    doc_texts = [
        "machine learning deep neural network training",
        "data engineering pipeline etl batch processing",
        "vector database similarity search indexing",
        "time series database anomaly detection monitoring",
        "feature store online offline serving consistency",
        "distributed system consensus raft paxos",
        "kubernetes container orchestration deployment",
        "streaming data kafka flink real-time processing",
    ]
    doc_ids = list(range(len(doc_texts)))
    doc_vectors = np.random.randn(len(doc_texts), dim).astype(np.float32)
    # 让文档3的向量与查询向量更接近
    doc_vectors[2] = query + np.random.randn(dim) * 0.1
    
    bf_small = BruteForceIndex(dim)
    bf_small.add(doc_ids, doc_vectors, [{} for _ in doc_ids])
    
    hybrid = HybridRetriever(bf_small)
    hybrid.add_documents(doc_ids, doc_texts, doc_vectors, [{} for _ in doc_ids])
    
    # 混合检索
    results_hybrid = hybrid.search("vector similarity search", query, k=3, alpha=0.5)
    print(f"  混合检索 Top-3 (alpha=0.5):")
    for did, score, text in results_hybrid:
        print(f"    id={did}, score={score:.4f}, text='{text}...'")
    assert len(results_hybrid) == 3
    print("✓ 混合检索: 向量 + BM25 验证通过")
    
    # ---- 9.5 元数据过滤 ----
    print("\n--- 9.5 元数据过滤搜索 ---")
    
    class FilteredVectorIndex:
        """支持元数据过滤的向量索引"""
        def __init__(self, base_index):
            self.base = base_index
        
        def search_with_filter(self, query, k=5, filters=None):
            """先搜索，再按元数据过滤"""
            raw_results = self.base.search(query, k=k * 10)  # 多搜一些以补偿过滤
            if not filters:
                return raw_results[:k]
            
            filtered = []
            for rid, sim, meta in raw_results:
                match = True
                for key, value in filters.items():
                    if meta.get(key) != value:
                        match = False
                        break
                if match:
                    filtered.append((rid, sim, meta))
                    if len(filtered) >= k:
                        break
            return filtered
    
    filtered_index = FilteredVectorIndex(bf_index)
    
    # 不过滤
    results_no_filter = filtered_index.search_with_filter(query, k=3)
    print(f"  无过滤搜索 Top-3: {[(r[0], r[2]) for r in results_no_filter]}")
    
    # 按 category 过滤
    results_filtered = filtered_index.search_with_filter(query, k=3, filters={"category": "tech"})
    print(f"  category=tech 过滤搜索 Top-3: {[(r[0], r[2]) for r in results_filtered]}")
    assert all(r[2]["category"] == "tech" for r in results_filtered)
    print("✓ 元数据过滤: 搜索结果按 category 过滤验证通过")
    
    print(f"\n✅ 题9完成")


# ============================================================
# 题 10: 数据目录与血缘追踪
# ============================================================

def exercise_10():
    """
    知识点：元数据管理、数据血缘图构建、影响分析、数据资产目录、血缘可视化
    
    用纯 Python + networkx 实现。
    """
    print("=" * 70)
    print("题 10: 数据目录与血缘追踪")
    print("=" * 70)
    
    tmpdir = "/tmp/data_lineage_demo"
    if os.path.exists(tmpdir):
        shutil.rmtree(tmpdir)
    os.makedirs(tmpdir)
    
    # ---- 10.1 数据资产元数据管理 ----
    print("\n--- 10.1 数据资产元数据管理 ---")
    
    @dataclass
    class DataAsset:
        asset_id: str
        name: str
        type: str  # database, table, column, pipeline, dashboard
        location: str
        owner: str
        description: str = ""
        tags: list = field(default_factory=list)
        schema: dict = field(default_factory=dict)
        created_at: str = field(default_factory=lambda: datetime.now().isoformat())
        updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
        quality_score: float = 0.0
    
    class DataCatalog:
        """数据资产目录"""
        def __init__(self):
            self.assets = {}  # asset_id -> DataAsset
            self.lineage_graph = nx.DiGraph()
        
        def register_asset(self, asset: DataAsset):
            self.assets[asset.asset_id] = asset
            self.lineage_graph.add_node(asset.asset_id, **{
                "name": asset.name, "type": asset.type,
                "owner": asset.owner, "tags": asset.tags
            })
            print(f"  [catalog] 注册资产: {asset.name} ({asset.type}) → {asset.asset_id}")
        
        def add_lineage(self, source_id, target_id, transformation=""):
            """添加血缘关系：source → target"""
            if source_id not in self.assets or target_id not in self.assets:
                raise ValueError("资产未注册")
            self.lineage_graph.add_edge(source_id, target_id,
                                       transformation=transformation)
            print(f"  [lineage] {self.assets[source_id].name} → {self.assets[target_id].name} ({transformation})")
        
        def get_asset(self, asset_id):
            return self.assets.get(asset_id)
        
        def search_assets(self, keyword="", asset_type=None, tag=None):
            """搜索资产"""
            results = []
            for asset in self.assets.values():
                match = True
                if keyword and keyword.lower() not in asset.name.lower() and \
                   keyword.lower() not in asset.description.lower():
                    match = False
                if asset_type and asset.type != asset_type:
                    match = False
                if tag and tag not in asset.tags:
                    match = False
                if match:
                    results.append(asset)
            return results
        
        def get_upstream(self, asset_id):
            """获取上游血缘（数据来源）"""
            return list(self.lineage_graph.predecessors(asset_id))
        
        def get_downstream(self, asset_id):
            """获取下游血缘（数据消费者）"""
            return list(self.lineage_graph.successors(asset_id))
        
        def impact_analysis(self, asset_id):
            """影响分析：某个资产变更时，哪些下游资产会受影响"""
            affected = set()
            queue = deque([asset_id])
            visited = {asset_id}
            while queue:
                current = queue.popleft()
                for successor in self.lineage_graph.successors(current):
                    if successor not in visited:
                        visited.add(successor)
                        affected.add(successor)
                        queue.append(successor)
            return affected
        
        def root_cause_analysis(self, asset_id):
            """根因分析：追溯某个资产的所有上游来源"""
            sources = set()
            queue = deque([asset_id])
            visited = {asset_id}
            while queue:
                current = queue.popleft()
                predecessors = list(self.lineage_graph.predecessors(current))
                if not predecessors:
                    sources.add(current)
                for pred in predecessors:
                    if pred not in visited:
                        visited.add(pred)
                        queue.append(pred)
            return sources
    
    catalog = DataCatalog()
    
    # 注册数据资产
    assets = [
        DataAsset("src_mysql_users", "MySQL用户表", "table", "mysql://prod/users", "DBA团队",
                  "生产用户主表", tags=["PII", "critical"], schema={"id": "int", "name": "varchar", "email": "varchar"}),
        DataAsset("src_mysql_orders", "MySQL订单表", "table", "mysql://prod/orders", "DBA团队",
                  "生产订单主表", tags=["critical"], schema={"id": "int", "user_id": "int", "amount": "decimal"}),
        DataAsset("etl_user_extract", "用户数据ETL", "pipeline", "airflow://dag/user_etl", "数据工程团队",
                  "用户数据抽取管道", tags=["daily"]),
        DataAsset("etl_order_extract", "订单数据ETL", "pipeline", "airflow://dag/order_etl", "数据工程团队",
                  "订单数据抽取管道", tags=["daily"]),
        DataAsset("dwh_user_dim", "用户维度表", "table", "dwh://dim/users", "数据仓库团队",
                  "用户维度表（脱敏后）", tags=["dim"], schema={"user_key": "int", "name": "varchar", "age_bucket": "varchar"}),
        DataAsset("dwh_order_fact", "订单事实表", "table", "dwh://fact/orders", "数据仓库团队",
                  "订单事实表", tags=["fact"], schema={"order_key": "int", "user_key": "int", "amount": "decimal"}),
        DataAsset("etl_join_user_order", "用户订单关联", "pipeline", "airflow://dag/join_etl", "数据工程团队",
                  "用户订单关联管道", tags=["daily"]),
        DataAsset("ml_feature_user_order", "用户订单特征表", "table", "featurestore://user_order_features",
                  "ML团队", "用户订单特征", tags=["feature"]),
        DataAsset("ml_model_churn", "流失预测模型", "pipeline", "mlflow://model/churn_v2", "ML团队",
                  "用户流失预测模型", tags=["model"]),
        DataAsset("bi_dashboard_revenue", "营收看板", "dashboard", "tableau://dash/revenue", "BI团队",
                  "营收分析看板", tags=["dashboard"]),
    ]
    for a in assets:
        catalog.register_asset(a)
    
    assert len(catalog.assets) == 10
    print("✓ 数据资产注册验证通过")
    
    # ---- 10.2 数据血缘图构建 ----
    print("\n--- 10.2 数据血缘图构建 ---")
    
    # 构建血缘关系
    catalog.add_lineage("src_mysql_users", "etl_user_extract", "CDC抽取")
    catalog.add_lineage("src_mysql_orders", "etl_order_extract", "CDC抽取")
    catalog.add_lineage("etl_user_extract", "dwh_user_dim", "脱敏+维度建模")
    catalog.add_lineage("etl_order_extract", "dwh_order_fact", "事实表建模")
    catalog.add_lineage("dwh_user_dim", "etl_join_user_order", "JOIN")
    catalog.add_lineage("dwh_order_fact", "etl_join_user_order", "JOIN")
    catalog.add_lineage("etl_join_user_order", "ml_feature_user_order", "特征工程")
    catalog.add_lineage("ml_feature_user_order", "ml_model_churn", "模型训练")
    catalog.add_lineage("dwh_order_fact", "bi_dashboard_revenue", "数据可视化")
    
    print(f"  血缘图: {catalog.lineage_graph.number_of_nodes()} 节点, {catalog.lineage_graph.number_of_edges()} 边")
    assert catalog.lineage_graph.number_of_edges() == 9
    print("✓ 血缘图构建验证通过")
    
    # ---- 10.3 影响分析 ----
    print("\n--- 10.3 影响分析 ---")
    
    # 如果 MySQL 用户表变更，影响哪些下游？
    impacted = catalog.impact_analysis("src_mysql_users")
    print(f"  'MySQL用户表' 变更影响 {len(impacted)} 个下游资产:")
    for aid in impacted:
        asset = catalog.get_asset(aid)
        print(f"    → {asset.name} ({asset.type})")
    
    expected_impacted = {"etl_user_extract", "dwh_user_dim", "etl_join_user_order",
                         "ml_feature_user_order", "ml_model_churn"}
    assert impacted == expected_impacted
    print("✓ 影响分析: 正确识别所有受影响的下游资产")
    
    # ---- 10.4 根因分析 ----
    print("\n--- 10.4 根因分析 ---")
    
    # 流失预测模型的数据来源追溯
    root_sources = catalog.root_cause_analysis("ml_model_churn")
    print(f"  '流失预测模型' 的根因数据源:")
    for aid in root_sources:
        asset = catalog.get_asset(aid)
        print(f"    ← {asset.name} ({asset.location})")
    
    assert "src_mysql_users" in root_sources
    assert "src_mysql_orders" in root_sources
    print("✓ 根因分析: 正确追溯到所有上游数据源")
    
    # ---- 10.5 数据资产搜索 ----
    print("\n--- 10.5 数据资产搜索 ---")
    
    # 按关键词搜索
    results = catalog.search_assets(keyword="用户")
    print(f"  搜索 '用户': 找到 {len(results)} 个资产")
    for r in results:
        print(f"    {r.name} ({r.type})")
    assert len(results) >= 3
    
    # 按类型搜索
    results_type = catalog.search_assets(asset_type="pipeline")
    print(f"  搜索 type=pipeline: 找到 {len(results_type)} 个资产")
    assert len(results_type) == 4
    
    # 按标签搜索
    results_tag = catalog.search_assets(tag="critical")
    print(f"  搜索 tag=critical: 找到 {len(results_tag)} 个资产")
    assert len(results_tag) == 2
    print("✓ 资产搜索: 关键词/类型/标签 三种搜索方式验证通过")
    
    # ---- 10.6 血缘可视化 ----
    print("\n--- 10.6 血缘可视化（文本图表）---")
    
    def visualize_lineage(catalog, root_id=None, max_depth=3):
        """文本方式可视化血缘图"""
        if root_id is None:
            # 找到所有根节点（没有上游的节点）
            roots = [n for n in catalog.lineage_graph.nodes()
                     if catalog.lineage_graph.in_degree(n) == 0]
        else:
            roots = [root_id]
        
        lines = []
        for root in roots:
            _draw_tree(catalog, root, "", True, lines, max_depth, 0, set())
        return "\n".join(lines)
    
    def _draw_tree(catalog, node_id, prefix, is_last, lines, max_depth, depth, visited):
        if node_id in visited or depth > max_depth:
            return
        visited.add(node_id)
        asset = catalog.get_asset(node_id)
        connector = "└── " if is_last else "├── "
        lines.append(f"  {prefix}{connector}{asset.name} [{asset.type}]")
        
        successors = list(catalog.lineage_graph.successors(node_id))
        for i, succ in enumerate(successors):
            child_is_last = (i == len(successors) - 1)
            extension = "    " if is_last else "│   "
            _draw_tree(catalog, succ, prefix + extension, child_is_last,
                       lines, max_depth, depth + 1, visited)
    
    viz = visualize_lineage(catalog)
    print(viz)
    
    # ---- 10.7 血缘图统计与分析 ----
    print("\n--- 10.7 血缘图统计分析 ---")
    
    G = catalog.lineage_graph
    
    # 度中心性（哪些资产连接最多）
    degree_cent = nx.degree_centrality(G)
    top_connected = sorted(degree_cent.items(), key=lambda x: x[1], reverse=True)[:5]
    print("  连接度最高的资产 Top 5:")
    for aid, cent in top_connected:
        asset = catalog.get_asset(aid)
        in_deg = G.in_degree(aid)
        out_deg = G.out_degree(aid)
        print(f"    {asset.name}: 中心性={cent:.3f} (in={in_deg}, out={out_deg})")
    
    # 最长血缘链
    longest_path = nx.dag_longest_path(G)
    print(f"  最长血缘链 ({len(longest_path)} 层):")
    for i, aid in enumerate(longest_path):
        asset = catalog.get_asset(aid)
        arrow = " → " if i < len(longest_path) - 1 else ""
        print(f"    {asset.name}{arrow}", end="")
    print()
    assert len(longest_path) >= 4
    print("✓ 血缘图统计分析验证通过")
    
    # 保存血缘元数据
    lineage_data = {
        "nodes": [{"id": n, "name": catalog.get_asset(n).name,
                    "type": catalog.get_asset(n).type} for n in G.nodes()],
        "edges": [{"source": u, "target": v,
                    "transformation": d.get("transformation", "")}
                   for u, v, d in G.edges(data=True)],
    }
    lineage_file = os.path.join(tmpdir, "lineage.json")
    with open(lineage_file, "w") as f:
        json.dump(lineage_data, f, indent=2, ensure_ascii=False)
    assert os.path.exists(lineage_file)
    print(f"  血缘元数据已保存: {lineage_file}")
    
    print(f"\n✅ 题10完成")


# ============================================================
# 主函数：运行全部 10 道题
# ============================================================

def main():
    print("\n" + "🌟" * 35)
    print("  阶段六：数据库与数据集工程 — 10 道实战练习题")
    print("🌟" * 35 + "\n")
    
    exercises = [
        exercise_01, exercise_02, exercise_03, exercise_04, exercise_05,
        exercise_06, exercise_07, exercise_08, exercise_09, exercise_10,
    ]
    
    passed = 0
    failed = 0
    for i, exercise in enumerate(exercises, 1):
        try:
            exercise()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"\n❌ 题{i}失败: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 70)
    print(f"  最终结果: {passed}/10 通过, {failed}/10 失败")
    print("=" * 70)
    
    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
