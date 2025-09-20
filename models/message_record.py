import hashlib
import os
from datetime import datetime, timedelta
from typing import Optional
import aiosqlite
from astrbot.api import logger


class MessageRecord:
    """消息记录数据库模型"""

    def __init__(self, db_path: str = None):
        if db_path is None:
            db_dir = "data/plugins/banshi_administrator"
            os.makedirs(db_dir, exist_ok=True)
            db_path = os.path.join(db_dir, "message_records.db")
        self.db_path = db_path

    async def init_db(self):
        """初始化数据库"""
        async with aiosqlite.connect(self.db_path) as db:
            # 创建消息记录表
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS message_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    group_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    message_hash TEXT NOT NULL,
                    message_type TEXT NOT NULL,
                    content_preview TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
            )

            # 创建索引以提高查询效率
            await db.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_group_user_hash
                ON message_records (group_id, user_id, message_hash)
            """
            )

            await db.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_created_at
                ON message_records (created_at)
            """
            )

            await db.commit()

    def _get_message_hash(self, content: str) -> str:
        """生成消息内容的哈希值"""
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    async def add_message_record(
        self,
        group_id: int,
        user_id: int,
        content: str,
        message_type: str,
        content_preview: str = "",
    ):
        """添加消息记录"""
        message_hash = self._get_message_hash(content)

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO message_records
                (group_id, user_id, message_hash, message_type, content_preview)
                VALUES (?, ?, ?, ?, ?)
            """,
                (group_id, user_id, message_hash, message_type, content_preview),
            )
            await db.commit()

    async def check_duplicate_message(
        self, group_id: int, user_id: int, content: str
    ) -> Optional[dict]:
        """检查是否为重复消息（24小时内同一用户）"""
        message_hash = self._get_message_hash(content)
        cutoff_time = datetime.now() - timedelta(hours=24)

        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                """
                SELECT message_type, content_preview, created_at
                FROM message_records
                WHERE group_id = ?
                    AND user_id = ?
                    AND message_hash = ?
                    AND created_at > ?
                ORDER BY created_at DESC
                LIMIT 1
            """,
                (group_id, user_id, message_hash, cutoff_time.isoformat()),
            ) as cursor:
                row = await cursor.fetchone()

                if row:
                    return {
                        "message_type": row[0],
                        "content_preview": row[1],
                        "created_at": row[2],
                    }

        return None

    async def cleanup_old_records(self):
        """清理超过25小时的旧记录"""
        cutoff_time = datetime.now() - timedelta(hours=25)

        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                DELETE FROM message_records
                WHERE created_at < ?
            """,
                (cutoff_time.isoformat(),),
            )

            deleted_count = cursor.rowcount
            await db.commit()

            if deleted_count > 0:
                logger.info(f"清理了 {deleted_count} 条过期的消息记录")
