# 蛇形数据处理插件 (SnakeData)

这是一个用于处理以特定符号开头的数据的插件。默认支持以🐍、~、@符号开头的消息。

## 功能

- 识别以配置的激活符号（默认为🐍、~、@）开头的消息
- 去掉激活符号前缀，将数据按逗号分隔
- 将数据写入SQLite数据库
- 返回数据写入成功的消息和统计信息
- 生成时间透视图，展示每日交易金额和累计净值变化

## 使用方法

发送以配置的激活符号开头的消息，后面跟着要处理的数据，数据格式为：

```
🐍名称1,类型1,方向1,数量1,价格1,链接1,名称2,类型2,方向2,数量2,价格2,链接2,...
```

或者使用其他配置的激活符号：

```
~名称1,类型1,方向1,数量1,价格1,链接1
@名称1,类型1,方向1,数量1,价格1,链接1
```

例如：

```
🐍比特币,0,1,0.5,35000,https://example.com/btc,以太坊,0,0,2.5,2500,https://example.com/eth
~比特币,0,1,0.5,35000,https://example.com/btc
@以太坊,0,0,2.5,2500,https://example.com/eth
```

插件会将数据写入数据库，并返回统计信息：

```
数据已成功写入
统计信息：
- 数据行数：X行
- 数据总和：Y
- 买入总额：Z1
- 卖出总额：Z2
- 目前盈亏：Z3
```

同时，插件会生成一个时间透视图，展示每日交易金额和累计净值变化。

## 配置激活符号

插件支持通过JSON配置文件自定义激活符号。配置文件位于`plugins/SnakeDataPlugin/config/triggers.json`，格式如下：

```json
{
    "triggers": [
        {
            "symbol": "🐍",
            "enabled": true,
            "description": "默认激活符号"
        },
        {
            "symbol": "~",
            "enabled": true,
            "description": "波浪线激活符号"
        },
        {
            "symbol": "@",
            "enabled": true,
            "description": "at符号激活符号"
        }
    ],
    "examples": [
        {
            "symbol": "#",
            "enabled": false,
            "description": "井号激活符号示例（未启用）"
        },
        {
            "symbol": "$",
            "enabled": false,
            "description": "美元符号激活符号示例（未启用）"
        }
    ]
}
```

要添加新的激活符号，只需在`triggers`数组中添加新的对象，并设置`enabled`为`true`。

## 数据格式

- 数据以逗号(,)分隔
- 也支持使用中文逗号(，)、斜杠(/)或空格作为分隔符
- 每六个值为一组：名称、类型、方向、数量、价格、链接
- 类型：0代表现货，1代表合约
- 方向：0代表卖出，1代表买入
- 数量和价格必须是数字
- 链接是可选的，如果没有可以省略或使用"-"代替

## 数据库

数据存储在SQLite数据库中，文件名为`snake_data.db`，位于`/data`目录下。

数据表结构：

```sql
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
```

字段说明：
- id: 自增主键
- date: 系统自动生成的日期时间
- name: 名称（文本类型）
- type: 类型（0代表现货，1代表合约）
- direction: 方向（0代表卖出，1代表买入）
- number: 数量（小数类型）
- price: 价格（小数类型）
- link: 分析的视频网址（文本类型，非必须，默认为"-"）

## 时间透视图

插件会生成一个时间透视图，包含两部分：
1. 每日交易金额柱状图：展示每天的买入和卖出金额
2. 累计净值折线图：展示累计净值（买入-卖出）的变化趋势

透视图保存在`data/picture`目录下，并在消息回复中自动发送。图片命名格式为`snake_pivot_{日期}.png`。 

![案例图片](https://github.com/ldyers/snakeData/blob/main/%E6%A1%88%E4%BE%8B%E5%9B%BE%E7%89%87.png)
