"""中文别名名字池（zh_names.py）。

与 data/names.py 的角色完全相同：生成开放式的设备别名，让模型学会"照抄
一个任意片段"这个槽位，而不是记住固定清单。区别只在表层语言：

  * 中文没有复数，组名走"集合量词"路线（"客厅的灯"、"前门的灯组"）；
  * 中文词间没有空格，所以 "kitchen light" 这类多词名对应 "厨房的灯"；
  * 下划线/编号风格保留（"LED_2"、"水泵3"），因为给设备起名的人确实会用；
  * 自造词不再是拼音式音节，而是常用汉字的随机组合（"泽卡灯"），同样是
    "模型不可能 memorise 的词"。

关键不变量与英文版一致：名字必须**逐字**出现在最终话语里，prepare.py
要在完成的话语里找到这个名字并把它的 token 切出来做标签——任何改写名字
的模板都会让该行作废（SpanError）。
"""

from __future__ import annotations

import random
from functools import lru_cache
from pathlib import Path

ADJ = [
    "红色", "蓝色", "绿色", "白色", "黄色", "紫色", "橙色", "粉色",
    "大", "小", "老", "新", "主", "备用", "前", "后", "左", "右",
    "上", "下", "里", "外", "楼上", "楼下", "应急", "安全", "夜间",
    "工作", "测试", "智能", "热", "冷", "暖", "静音", "超强", "迷你",
    "第一", "第二", "第三", "前门", "后门", "侧门",
]

PLACE = [
    "厨房", "卧室", "卫生间", "走廊", "门廊", "车库", "花园", "工具房",
    "阁楼", "地下室", "书房", "工作室", "车间", "实验室", "储物间",
    "阳台", "庭院", "车道", "楼梯", "过道", "大厅", "门口", "露台",
    "院子", "客厅", "餐厅", "游戏室", "洗衣房", "储藏室", "前门",
    "后门", "侧门", "顶楼", "一楼", "二楼", "会议室", "机房", "儿童房",
    "茶室", "琴房", "画室", "温室", "酒窖", "门厅", "玄关", "衣帽间",
    "吧台", "卡座", "操作台", "货架区", "包装区", "发货区",
]

DEVICE = [
    "灯", "台灯", "电灯", "LED", "灯泡", "风扇", "电机", "水泵", "阀门",
    "继电器", "蜂鸣器", "警笛", "铃", "铃铛", "警报", "警报器", "加热器",
    "冷风机", "排气扇", "电磁阀", "音箱", "灯带", "指示灯", "插座",
    "插头", "开关", "线圈", "舵机", "压缩机", "鼓风机", "喇叭", "射灯",
    "显示器", "面板", "大门", "门锁", "锁", "窗帘", "卷帘", "百叶窗",
    "喂食器", "加湿器", "过滤器", "充电器", "分配器", "传送带", "主轴",
    "执行器", "风门", "喷射器", "水壶", "烤箱", "收音机", "投影仪",
    "打印机", "扫描仪", "摄像头", "传感器", "监视器", "手电筒", "路灯",
    "泛光灯", "筒灯", "夜灯", "智能插座", "墙插", "电源插座", "壁灯",
    "门铃", "烟雾报警器", "气泵", "加热垫", "植物灯", "彩灯", "吸顶灯",
    "落地灯", "灯箱", "霓虹灯", "闪光灯", "雾化器", "喷灌", "卷扬机",
    # 复合设备词——"智能插座开关" 被截断成 "智能插座" 这类跨段错误，就是
    # 因为设备名词全是单段词。中文对应物：把常见多字设备名收进来。
    "智能插座开关", "灯带控制器", "RGB灯", "氛围灯", "感应灯",
    "流水灯", "补光灯", "消毒灯", "杀菌灯", "诱虫灯", "水族灯", "鱼缸灯",
    "鱼缸水泵", "氧气泵", "抽水机", "浇花器", "喷雾器", "升降桌",
    "升降机", "道闸", "门禁", "闸机", "风淋室", "排风扇", "换气扇",
]

# 普通中文名词——设备名的"头名词"经常不是设备词（"咖啡机"、"鱼缸"、
# "激光切割机"），英文版靠 5,598 行的 Unix 词表解决；这里收一份常用的
# 家用/车间名词，并靠 ADJ/PLACE 的组合展开保证广度，让任何一个词都小到
# 不值得 memorise。
ORDINARY = [
    "咖啡机", "咖啡壶", "榨汁机", "破壁机", "洗碗机", "消毒柜", "蒸箱",
    "微波炉", "电饭煲", "热水器", "饮水机", "净水器", "空气净化器",
    "除湿机", "电暖器", "暖风机", "壁炉", "电热毯", "艾灸仪", "按摩椅",
    "跑步机", "动感单车", "鱼缸", "鱼缸过滤器", "龟缸", "鸟笼", "猫窝",
    "宠物饮水机", "自动猫砂盆", "冰箱", "冷柜", "酒柜", "冰淇淋机",
    "爆米花机", "棉花糖机", "烤炉", "烤架", "煎锅", "电磁炉", "砂锅",
    "饮水槽", "饲料机", "孵化器", "切割机", "打磨机", "电钻", "电锯",
    "热熔胶枪", "焊台", "焊锡炉", "回流焊", "贴片机", "点胶机",
    "雕刻机", "激光切割机", "3d打印机", "注塑机", "空压机", "吸尘器",
    "扫地机器人", "洗地机", "高压清洗机", "割草机", "吹叶机", "喷雾机",
    "灌溉阀", "滴灌带", "温控器", "湿度计", "二氧化碳阀", "补气泵",
    "新风系统", "中央空调", "地暖", "暖气片", "窗帘电机", "晾衣架",
    "烘鞋器", "干衣机", "熨烫台", "缝纫机", "织布机", "印刷机",
    "包装机", "封口机", "打标机", "喷码机", "贴标机", "上料机",
    "送料机", "搅拌机", "和面机", "压面机", "绞肉机", "切菜机",
    "脱皮机", "烘干机", "烘烤线", "固化炉", "老化台", "测试台",
    "信号灯", "警示灯", "照明塔", "探照灯塔", "航标灯", "障碍灯",
    "风机", "排烟机", "油烟机", "燃气阀", "水表阀", "总闸", "分闸",
]

# 自造词用的常用字池——随机组合出"模型在任何词表里都见不到"的名字。
_INV_CHARS = (
    "泽明卡洛希兰特波恩迪赛图米纳科瑞维克斯通达启元凌耀晨曦风雷"
    "云海山川星辰光影子午卯酉金木水火土日月天地人和吉安泰福禄寿"
)

# 常用单字量词后缀（"灯2"、"灯_2" 风格）
_NUM_SUFFIX = "123456789"


@lru_cache(maxsize=1)
def _words() -> tuple[list[str], list[str], list[int]]:
    """读 data/zh_wordlist.txt -> (全部词, 单侧词, 权重)。

    英文版靠这个词表纠正两个实测缺陷：负样本专用的词变成"拒绝触发器"，
    语料里缺席的词让模型提前截断。中文版用同一个机制：zh_wordlist.txt
    汇总负样本会用的名词与普通名词，保证"没有哪个词是拒绝的证据，也没
    有哪个词是停下的证据"。
    """
    p = Path(__file__).parent / "zh_wordlist.txt"
    every: list[str] = []
    heavy: list[str] = []
    weight: list[int] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        word, _, n = line.partition("\t")
        every.append(word)
        if n:
            heavy.append(word)
            weight.append(int(n))
    if len(every) < 200:
        raise SystemExit(f"{p} 只有 {len(every)} 个词；重点就是让词表大到"
                         f"没法 memorise")
    return every, heavy, weight


WORDS, _HEAVY, _HEAVY_W = _words()

# 一个名字的词取自"单侧池"的概率。与英文版同理由：两侧都出现的词才不
# 构成任何一方的证据。
ONE_SIDED_PROB = 0.55


def _word(rng: random.Random) -> str:
    if _HEAVY and rng.random() < ONE_SIDED_PROB:
        return rng.choices(_HEAVY, weights=_HEAVY_W)[0]
    return rng.choice(WORDS)


def _invented(rng: random.Random) -> str:
    """随机汉字组合，2-3 字，保证在词表之外。"""
    n = rng.randint(2, 3)
    return "".join(rng.choice(_INV_CHARS) for _ in range(n))


def _ordinary(rng: random.Random) -> str:
    """由普通中文词构成的设备名。

    头名词经常**不是**设备词——"咖啡机"、"鱼缸"、"激光切割机"——因为
    那正是英文版模型抄不出来的形状：它停在最后一个认识的名词上。
    """
    w = lambda: _word(rng)
    r = rng.random()
    if r < 0.34:                                    # "咖啡壶"
        return w()
    if r < 0.55:                                    # "鱼缸水泵"
        return f"{w()}{rng.choice(DEVICE)}"
    if r < 0.70:                                    # "备用切割机"
        return f"{rng.choice(ADJ)}{w()}"
    if r < 0.82:                                    # "雕刻机"
        return w()
    if r < 0.92:                                    # "水族_灯"
        return f"{w()}_{rng.choice(DEVICE)}"
    return f"{rng.choice(PLACE)}的{w()}"            # "厨房的榨汁机"


def sample_name(rng: random.Random) -> str:
    """一个别名名字。反复调用获得多样性。

    配比照搬英文版的实测结论：普通名词占大头（那曾是整个失败所在），
    自造词降到 6%（它太容易了，学不到想要的东西）。
    """
    r = rng.random()
    if r < 0.32:                                    # 普通名词
        return _ordinary(rng)
    if r < 0.47:                                    # "红色台灯"
        return f"{rng.choice(ADJ)}{rng.choice(DEVICE)}"
    if r < 0.60:                                    # "厨房的灯"
        return f"{rng.choice(PLACE)}的{rng.choice(DEVICE)}"
    if r < 0.68:                                    # "台灯"
        return rng.choice(DEVICE)
    if r < 0.75:                                    # "前门廊灯"
        return f"{rng.choice(ADJ)}{rng.choice(PLACE)}{rng.choice(DEVICE)}"
    if r < 0.82:                                    # "状态灯"、"水泵_2"
        base = rng.choice(DEVICE)
        head = rng.choice(ADJ + PLACE)
        return (f"{head}_{base}" if rng.random() < 0.5
                else f"{base}_{rng.randint(1, 9)}")
    if r < 0.89:                                    # "LED2"、"继电器 3"
        sep = "" if rng.random() < 0.5 else " "
        return f"{rng.choice(DEVICE)}{sep}{rng.randint(1, 12)}"
    if r < 0.97:                                    # 自造词
        w = _invented(rng)
        return w if rng.random() < 0.6 else f"{w}{rng.choice(DEVICE)}"
    return f"{_invented(rng)}_{rng.choice(DEVICE)}"  # 自造标识符


def sample_group_name(rng: random.Random) -> str:
    """一个大概率覆盖多个引脚的名字——中文没有复数，走集合路线。"""
    r = rng.random()
    if r < 0.22:                            # "咖啡机们"不通顺；用量词
        w = _word(rng)
        return (f"所有的{w}{rng.choice(DEVICE)}" if rng.random() < 0.5
                else f"{rng.choice(ADJ)}{w}组")
    if r < 0.48:
        return f"{rng.choice(PLACE)}的{rng.choice(DEVICE)}"
    if r < 0.68:
        return f"{rng.choice(ADJ)}{rng.choice(DEVICE)}组"
    if r < 0.84:
        return f"所有{rng.choice(DEVICE)}"
    return rng.choice([
        f"{rng.choice(PLACE)}一排", f"{rng.choice(ADJ)}灯组",
        f"{rng.choice(DEVICE)}组", f"{rng.choice(DEVICE)}阵列",
        f"{rng.choice(PLACE)}灯组", f"{rng.choice(DEVICE)}群",
    ])


if __name__ == "__main__":
    rng = random.Random(0)
    print("single:", "、".join(sample_name(rng) for _ in range(18)))
    print("group :", "、".join(sample_group_name(rng) for _ in range(10)))
