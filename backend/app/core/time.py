"""上海时区工具。

TODO: 提供带 Asia/Shanghai 时区的 now；写 MySQL 前转为上海本地 naive datetime；
实现 HH:mm 发车时间合成日期及跨午夜判定，并覆盖边界测试。
"""

from zoneinfo import ZoneInfo

SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")

