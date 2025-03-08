from pkg.plugin.context import register, handler, llm_func, BasePlugin, APIHost, EventContext
from pkg.plugin.events import *  # 导入事件类

import sqlite3
import time
import os
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from io import BytesIO
import matplotlib.font_manager as fm
from matplotlib import rcParams
import json


# 设置中文字体支持
def set_matplotlib_chinese_font():
    # 尝试设置中文字体
    font_list = ['SimHei', 'Microsoft YaHei', 'SimSun', 'FangSong', 'KaiTi', 'Arial Unicode MS']
    
    # 检查系统中是否有这些字体
    available_font = None
    for font in font_list:
        # 查找字体文件
        font_path = fm.findfont(fm.FontProperties(family=font), fallback_to_default=False)
        if font_path and os.path.exists(font_path) and font_path.lower().endswith('.ttf'):
            available_font = font
            break
    
    if available_font:
        # 设置全局字体
        plt.rcParams['font.sans-serif'] = [available_font]
        plt.rcParams['axes.unicode_minus'] = False  # 解决负号显示问题
        return True
    else:
        # 如果没有找到中文字体，使用英文标签
        return False


# 注册插件
@register(name="SnakeData", description="处理以🐍开头的数据", version="0.3", author="Claude")
class SnakeDataPlugin(BasePlugin):

    # 插件加载时触发
    def __init__(self, host: APIHost):
        super().__init__(host)
        self.db = None
        self.has_chinese_font = set_matplotlib_chinese_font()
        self.triggers = []  # 激活符号列表

    # 异步初始化
    async def initialize(self):
        self.db = Database()
        # 加载激活符号配置
        self.load_triggers()
        self.ap.logger.debug(f"SnakeData插件初始化完成，激活符号: {self.triggers}")

    # 加载激活符号配置
    def load_triggers(self):
        config_path = os.path.join('plugins', 'SnakeDataPlugin', 'config', 'triggers.json')
        
        # 默认激活符号
        default_triggers = ["🐍"]
        
        try:
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                
                # 获取已启用的激活符号
                self.triggers = [item["symbol"] for item in config.get("triggers", []) if item.get("enabled", False)]
                
                if not self.triggers:  # 如果没有启用的激活符号，使用默认值
                    self.triggers = default_triggers
            else:
                self.ap.logger.warning(f"激活符号配置文件不存在: {config_path}，使用默认值")
                self.triggers = default_triggers
        except Exception as e:
            self.ap.logger.error(f"加载激活符号配置失败: {str(e)}，使用默认值")
            self.triggers = default_triggers

    # 检查消息是否以任一激活符号开头
    def is_triggered_by(self, message):
        for trigger in self.triggers:
            if message.startswith(trigger):
                return trigger
        return None

    # 当收到个人消息时触发
    @handler(PersonNormalMessageReceived)
    async def person_normal_message_received(self, ctx: EventContext):
        msg = ctx.event.text_message  # 获取消息内容
        
        # 检查消息是否以任一激活符号开头
        trigger = self.is_triggered_by(msg)
        if trigger:
            await self.process_snake_data(msg, ctx, trigger)
            # 阻止该事件默认行为（向接口获取回复）
            ctx.prevent_default()

    # 当收到群消息时触发
    @handler(GroupNormalMessageReceived)
    async def group_normal_message_received(self, ctx: EventContext):
        msg = ctx.event.text_message  # 获取消息内容
        
        # 检查消息是否以任一激活符号开头
        trigger = self.is_triggered_by(msg)
        if trigger:
            await self.process_snake_data(msg, ctx, trigger)
            # 阻止该事件默认行为（向接口获取回复）
            ctx.prevent_default()

    # 处理蛇形数据
    async def process_snake_data(self, msg, ctx, trigger):
        try:
            # 去掉激活符号前缀
            data = msg[len(trigger):].strip()
            
            # 使用逗号分隔数据
            data = data.replace('，', ',').replace('/', ',').replace(' ', ',').strip()
            parts = data.split(',')
            
            # 过滤空字符串并获取有效部分
            parts = [p.strip() for p in parts if p.strip()]
            
            # 检查数据格式是否正确
            if len(parts) < 5:  # 至少需要5个值：名称、类型、方向、数量、价格
                ctx.add_return("reply", ["数据格式不正确，请确保至少包含名称、类型、方向、数量、价格五个值"])
                return
            
            # 将数据写入数据库
            records_added = 0
            for i in range(0, len(parts), 6):  # 每6个值为一组：名称、类型、方向、数量、价格、链接
                if i + 4 < len(parts):  # 至少需要5个值
                    name = parts[i]
                    try:
                        # 解析类型（0代表现货，1代表合约）
                        type_val = int(parts[i+1])
                        if type_val not in [0, 1]:
                            ctx.add_return("reply", [f"类型值错误: {parts[i+1]}，应为0(现货)或1(合约)，已跳过"])
                            continue
                        
                        # 解析方向（0代表卖出，1代表买入）
                        direction = int(parts[i+2])
                        if direction not in [0, 1]:
                            ctx.add_return("reply", [f"方向值错误: {parts[i+2]}，应为0(卖出)或1(买入)，已跳过"])
                            continue
                        
                        # 解析数量和价格
                        number = float(parts[i+3])
                        price = float(parts[i+4])
                        
                        # 解析链接（如果有）
                        link = "-"  # 默认值
                        if i + 5 < len(parts):
                            link = parts[i+5]
                            if not link or link.strip() == "":
                                link = "-"
                        
                        # 插入数据
                        self.db.insert_data(name, type_val, direction, number, price, link)
                        records_added += 1
                    except ValueError as ve:
                        ctx.add_return("reply", [f"数据格式错误: {parts[i:i+6]}，已跳过。错误: {str(ve)}"])
                    except Exception as e:
                        ctx.add_return("reply", [f"处理数据时出错: {str(e)}，已跳过"])
            
            if records_added == 0:
                ctx.add_return("reply", ["没有有效数据被添加"])
                return
            
            # 获取统计信息
            stats = self.db.get_statistics()
            
            # 生成时间透视图
            try:
                chart_path = self.generate_time_pivot_chart()
                
                # 回复消息
                reply = "✅数据已写入！\n"
                reply += f"统计信息：\n"
                reply += f"- 数据行数：{stats['row_count']}行\n"
                reply += f"- 数据总和：{stats['sum_value']}\n"
                reply += f"- 买入总额：{stats['buy_sum']}\n"
                reply += f"- 卖出总额：{stats['sell_sum']}\n"
                reply += f"- 目前盈亏：{stats['profit_loss']}"
                
                # 添加图片回复
                if chart_path:
                    ctx.add_return("image", [chart_path])
                
                ctx.add_return("reply", [reply])
            except Exception as e:
                self.ap.logger.error(f"生成透视图时出错: {str(e)}")
                
                # 回复基本消息（不含图表）
                reply = "数据已成功写入\n"
                reply += f"统计信息：\n"
                reply += f"- 数据行数：{stats['row_count']}行\n"
                reply += f"- 数据总和：{stats['sum_value']:.2f}\n"
                reply += f"- 买入总额：{stats['buy_sum']:.2f}\n"
                reply += f"- 卖出总额：{stats['sell_sum']:.2f}\n"
                reply += f"- 目前盈亏：{stats['profit_loss']:.2f}\n"
                reply += f"(生成透视图时出错: {str(e)})"
                
                ctx.add_return("reply", [reply])
            
        except Exception as e:
            self.ap.logger.error(f"处理数据时出错: {str(e)}")
            ctx.add_return("reply", [f"处理数据时出错: {str(e)}"])

    def generate_time_pivot_chart(self):
        """生成时间透视图"""
        try:
            # 获取数据
            df = self.db.get_data_as_dataframe()
            
            if len(df) == 0:
                return None
            
            # 确保日期列是日期时间类型
            df['date'] = pd.to_datetime(df['date'])
            
            # 添加日期列（只包含日期部分）
            df['day'] = df['date'].dt.date
            
            # 计算每天的交易金额
            daily_amounts = df.groupby(['day', 'direction']).apply(
                lambda x: (x['number'] * x['price']).sum()
            ).unstack(fill_value=0)
            
            # 如果没有买入或卖出的数据，添加对应的列
            if 1 not in daily_amounts.columns:
                daily_amounts[1] = 0  # 买入
            if 0 not in daily_amounts.columns:
                daily_amounts[0] = 0  # 卖出
                
            # 重命名列
            if self.has_chinese_font:
                daily_amounts.columns = ['卖出', '买入']
            else:
                daily_amounts.columns = ['Sell', 'Buy']
            
            # 计算每天的净值（买入-卖出）
            if self.has_chinese_font:
                daily_amounts['净值'] = daily_amounts['买入'] - daily_amounts['卖出']
                daily_amounts['累计净值'] = daily_amounts['净值'].cumsum()
            else:
                daily_amounts['Net'] = daily_amounts['Buy'] - daily_amounts['Sell']
                daily_amounts['Cumulative'] = daily_amounts['Net'].cumsum()
            
            # 创建图表
            plt.figure(figsize=(12, 8), dpi=100)
            
            # 绘制柱状图（每日买入和卖出）
            ax1 = plt.subplot(2, 1, 1)
            if self.has_chinese_font:
                daily_amounts[['买入', '卖出']].plot(kind='bar', ax=ax1)
                plt.title('每日交易金额')
                plt.ylabel('金额')
            else:
                daily_amounts[['Buy', 'Sell']].plot(kind='bar', ax=ax1)
                plt.title('Daily Transaction Amount')
                plt.ylabel('Amount')
            plt.xticks(rotation=45)
            plt.grid(axis='y', linestyle='--', alpha=0.7)
            
            # 绘制折线图（累计净值）
            ax2 = plt.subplot(2, 1, 2)
            if self.has_chinese_font:
                daily_amounts['累计净值'].plot(kind='line', marker='o', ax=ax2)
                plt.title('累计净值变化')
                plt.ylabel('累计净值')
            else:
                daily_amounts['Cumulative'].plot(kind='line', marker='o', ax=ax2)
                plt.title('Cumulative Net Value')
                plt.ylabel('Cumulative Value')
            plt.xticks(rotation=45)
            plt.grid(linestyle='--', alpha=0.7)
            
            plt.tight_layout()
            
            # 确保目录存在
            picture_dir = os.path.join('data', 'picture')
            os.makedirs(picture_dir, exist_ok=True)
            
            # 使用当前日期作为文件名
            current_date = datetime.now().strftime('%Y-%m-%d')
            chart_path = os.path.join(picture_dir, f'snake_pivot_{current_date}.png')
            
            # 使用savefig时添加参数来避免iCCP警告
            plt.savefig(chart_path, bbox_inches='tight', metadata={'Software': 'SnakeDataPlugin'})
            plt.close()
            
            return chart_path
        except Exception as e:
            self.ap.logger.error(f"生成时间透视图时出错: {str(e)}")
            return None

    # 插件卸载时触发
    def __del__(self):
        if self.db:
            self.db.close()


# 数据库类
class Database:
    def __init__(self):
        """初始化数据库连接"""
        # 确保data目录存在
        data_dir = 'data'
        os.makedirs(data_dir, exist_ok=True)
        
        # 数据库文件路径
        self.db_path = os.path.join(data_dir, 'snake_data.db')
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()
        self.create_table()
    
    def create_table(self):
        """创建数据表"""
        create_table_sql = '''
        CREATE TABLE IF NOT EXISTS snake_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            name TEXT,
            type INTEGER,
            direction INTEGER,
            number DECIMAL(10,2),
            price DECIMAL(10,2),
            link TEXT
        )
        '''
        self.cursor.execute(create_table_sql)
        self.conn.commit()
    
    def insert_data(self, name, type_val, direction, number, price, link="-"):
        """插入数据"""
        insert_sql = '''
        INSERT INTO snake_data (name, type, direction, number, price, link)
        VALUES (?, ?, ?, ?, ?, ?)
        '''
        self.cursor.execute(insert_sql, (name, type_val, direction, number, price, link))
        self.conn.commit()
    
    def get_all_data(self):
        """获取所有数据"""
        self.cursor.execute('SELECT * FROM snake_data')
        return self.cursor.fetchall()
    
    def get_data_as_dataframe(self):
        """获取所有数据并转换为DataFrame"""
        self.cursor.execute('''
            SELECT id, date, name, type, direction, number, price, link 
            FROM snake_data
            ORDER BY date
        ''')
        
        columns = ['id', 'date', 'name', 'type', 'direction', 'number', 'price', 'link']
        data = self.cursor.fetchall()
        
        return pd.DataFrame(data, columns=columns)
    
    def get_statistics(self):
        """获取统计信息"""
        # 获取行数
        self.cursor.execute('SELECT COUNT(*) FROM snake_data')
        row_count = self.cursor.fetchone()[0]
        
        # 获取数量*价格的总和
        self.cursor.execute('SELECT SUM(number * price) FROM snake_data')
        sum_value = self.cursor.fetchone()[0] or 0
        
        # 获取买入总额（direction=1）
        self.cursor.execute('SELECT SUM(number * price) FROM snake_data WHERE direction = 1')
        buy_sum = self.cursor.fetchone()[0] or 0
        
        # 获取卖出总额（direction=0）
        self.cursor.execute('SELECT SUM(number * price) FROM snake_data WHERE direction = 0')
        sell_sum = self.cursor.fetchone()[0] or 0
        
        # 计算盈亏（卖出总额 - 买入总额）
        profit_loss = sell_sum - buy_sum
        
        return {
            'row_count': row_count,
            'sum_value': sum_value,
            'buy_sum': buy_sum,
            'sell_sum': sell_sum,
            'profit_loss': profit_loss
        }
    
    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close() 