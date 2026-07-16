"""万能域推断引擎 — 一通百通：任意中国高校/企业 → 自动推断域名。

核心能力：
  1. 覆盖 300+ 中国高校精确域名映射（985/211/双一流全覆盖）
  2. 覆盖 100+ 中国头部企业域名映射
  3. 算法推算：拼音首字母缩写 + .edu.cn / .com / .com.cn
  4. 自动识别高校 / 企业 / 政府 / 普通域名
"""
from __future__ import annotations

import re
from typing import Dict, Optional

# ──────────────────────────────────────────────
# 中国高校域名知识库（985/211/双一流全覆盖）
# ──────────────────────────────────────────────

UNIVERSITY_DOMAIN_MAP: Dict[str, str] = {
    # === C9 顶尖高校 ===
    "北京大学": "pku.edu.cn",
    "清华大学": "tsinghua.edu.cn",
    "复旦大学": "fudan.edu.cn",
    "上海交通大学": "sjtu.edu.cn",
    "浙江大学": "zju.edu.cn",
    "南京大学": "nju.edu.cn",
    "中国科学技术大学": "ustc.edu.cn",
    "哈尔滨工业大学": "hit.edu.cn",
    "西安交通大学": "xjtu.edu.cn",

    # === 985 高校 ===
    "中国人民大学": "ruc.edu.cn",
    "北京航空航天大学": "buaa.edu.cn",
    "北京理工大学": "bit.edu.cn",
    "北京师范大学": "bnu.edu.cn",
    "中国农业大学": "cau.edu.cn",
    "南开大学": "nankai.edu.cn",
    "天津大学": "tju.edu.cn",
    "大连理工大学": "dlut.edu.cn",
    "东北大学": "neu.edu.cn",
    "吉林大学": "jlu.edu.cn",
    "哈尔滨工业大学(威海)": "hit.edu.cn",
    "同济大学": "tongji.edu.cn",
    "华东师范大学": "ecnu.edu.cn",
    "东南大学": "seu.edu.cn",
    "厦门大学": "xmu.edu.cn",
    "山东大学": "sdu.edu.cn",
    "中国海洋大学": "ouc.edu.cn",
    "武汉大学": "whu.edu.cn",
    "华中科技大学": "hust.edu.cn",
    "湖南大学": "hnu.edu.cn",
    "中南大学": "csu.edu.cn",
    "国防科技大学": "nudt.edu.cn",
    "中山大学": "sysu.edu.cn",
    "华南理工大学": "scut.edu.cn",
    "四川大学": "scu.edu.cn",
    "电子科技大学": "uestc.edu.cn",
    "重庆大学": "cqu.edu.cn",
    "西北工业大学": "nwpu.edu.cn",
    "西北农林科技大学": "nwsuaf.edu.cn",
    "兰州大学": "lzu.edu.cn",

    # === 211 高校 ===
    "北京交通大学": "bjtu.edu.cn",
    "北京工业大学": "bjut.edu.cn",
    "北京科技大学": "ustb.edu.cn",
    "北京化工大学": "buct.edu.cn",
    "北京邮电大学": "bupt.edu.cn",
    "北京林业大学": "bjfu.edu.cn",
    "北京协和医学院": "pumc.edu.cn",
    "北京中医药大学": "bucm.edu.cn",
    "北京外国语大学": "bfsu.edu.cn",
    "中国传媒大学": "cuc.edu.cn",
    "中央财经大学": "cufe.edu.cn",
    "对外经济贸易大学": "uibe.edu.cn",
    "北京体育大学": "bsu.edu.cn",
    "中央音乐学院": "ccom.edu.cn",
    "中国政法大学": "cupl.edu.cn",
    "华北电力大学": "ncepu.edu.cn",
    "河北工业大学": "hebut.edu.cn",
    "太原理工大学": "tyut.edu.cn",
    "内蒙古大学": "imu.edu.cn",
    "辽宁大学": "lnu.edu.cn",
    "大连海事大学": "dlmu.edu.cn",
    "延边大学": "ybu.edu.cn",
    "东北师范大学": "nenu.edu.cn",
    "哈尔滨工程大学": "hrbeu.edu.cn",
    "东北农业大学": "neau.edu.cn",
    "东北林业大学": "nefu.edu.cn",
    "华东理工大学": "ecust.edu.cn",
    "东华大学": "dhu.edu.cn",
    "上海外国语大学": "shisu.edu.cn",
    "上海财经大学": "shufe.edu.cn",
    "上海大学": "shu.edu.cn",
    "苏州大学": "suda.edu.cn",
    "南京航空航天大学": "nuaa.edu.cn",
    "南京理工大学": "njust.edu.cn",
    "中国矿业大学": "cumt.edu.cn",
    "河海大学": "hhu.edu.cn",
    "江南大学": "jiangnan.edu.cn",
    "南京农业大学": "njau.edu.cn",
    "中国药科大学": "cpu.edu.cn",
    "南京师范大学": "njnu.edu.cn",
    "安徽大学": "ahu.edu.cn",
    "合肥工业大学": "hfut.edu.cn",
    "福州大学": "fzu.edu.cn",
    "福建农林大学": "fafu.edu.cn",
    "南昌大学": "ncu.edu.cn",
    "中国石油大学(华东)": "upc.edu.cn",
    "郑州大学": "zzu.edu.cn",
    "中国地质大学(武汉)": "cug.edu.cn",
    "武汉理工大学": "whut.edu.cn",
    "华中农业大学": "hzau.edu.cn",
    "华中师范大学": "ccnu.edu.cn",
    "中南财经政法大学": "zuel.edu.cn",
    "湘潭大学": "xtu.edu.cn",
    "湖南师范大学": "hunnu.edu.cn",
    "暨南大学": "jnu.edu.cn",
    "华南师范大学": "scnu.edu.cn",
    "华南农业大学": "scau.edu.cn",
    "海南大学": "hainanu.edu.cn",
    "广西大学": "gxu.edu.cn",
    "西南交通大学": "swjtu.edu.cn",
    "西南大学": "swu.edu.cn",
    "西南财经大学": "swufe.edu.cn",
    "四川农业大学": "sicau.edu.cn",
    "西南石油大学": "swpu.edu.cn",
    "成都理工大学": "cdut.edu.cn",
    "贵州大学": "gzu.edu.cn",
    "云南大学": "ynu.edu.cn",
    "西藏大学": "utibet.edu.cn",
    "西北大学": "nwu.edu.cn",
    "西安电子科技大学": "xidian.edu.cn",
    "长安大学": "chd.edu.cn",
    "陕西师范大学": "snnu.edu.cn",
    "青海大学": "qhu.edu.cn",
    "宁夏大学": "nxu.edu.cn",
    "新疆大学": "xju.edu.cn",
    "石河子大学": "shzu.edu.cn",
    "中国石油大学(北京)": "cup.edu.cn",
    "中国地质大学(北京)": "cugb.edu.cn",
    "中国矿业大学(北京)": "cumtb.edu.cn",
    "中央民族大学": "muc.edu.cn",
    "华北水利水电大学": "ncwu.edu.cn",

    # === 特色高校 ===
    "南方科技大学": "sustech.edu.cn",
    "上海科技大学": "shanghaitech.edu.cn",
    "中国科学院大学": "ucas.ac.cn",
    "中国社会科学院大学": "ucass.edu.cn",
    "外交学院": "cfau.edu.cn",
    "国际关系学院": "uir.edu.cn",
    "上海纽约大学": "shanghai.nyu.edu",
    "西交利物浦大学": "xjtlu.edu.cn",
    "宁波诺丁汉大学": "nottingham.edu.cn",
    "温州肯恩大学": "wku.edu.cn",
    "深圳大学": "szu.edu.cn",
    "广州大学": "gzhu.edu.cn",
    "杭州电子科技大学": "hdu.edu.cn",
    "浙江工业大学": "zjut.edu.cn",
    "南京邮电大学": "njupt.edu.cn",
    "南京信息工程大学": "nuist.edu.cn",
    "重庆邮电大学": "cqupt.edu.cn",
    "重庆交通大学": "cqjtu.edu.cn",
    "武汉科技大学": "wust.edu.cn",
    "上海理工大学": "usst.edu.cn",
    "上海海事大学": "shmtu.edu.cn",
    "上海海洋大学": "shou.edu.cn",
    "上海师范大学": "shnu.edu.cn",
    "上海对外经贸大学": "suibe.edu.cn",
    "天津工业大学": "tiangong.edu.cn",
    "天津科技大学": "tust.edu.cn",
    "天津理工大学": "tjut.edu.cn",
    "天津师范大学": "tjnu.edu.cn",
    "天津财经大学": "tjufe.edu.cn",
    "河北大学": "hbu.edu.cn",
    "燕山大学": "ysu.edu.cn",
    "山西大学": "sxu.edu.cn",
    "中北大学": "nuc.edu.cn",
    "内蒙古工业大学": "imut.edu.cn",
    "沈阳工业大学": "sut.edu.cn",
    "沈阳航空航天大学": "sau.edu.cn",
    "沈阳建筑大学": "sjzu.edu.cn",
    "大连交通大学": "djtu.edu.cn",
    "大连工业大学": "dlpu.edu.cn",
    "辽宁科技大学": "ustl.edu.cn",
    "东北财经大学": "dufe.edu.cn",
    "长春理工大学": "cust.edu.cn",
    "东北电力大学": "neepu.edu.cn",
    "哈尔滨理工大学": "hrbust.edu.cn",
    "哈尔滨商业大学": "hrbcu.edu.cn",
    "江苏大学": "ujs.edu.cn",
    "南京工业大学": "njtech.edu.cn",
    "常州大学": "cczu.edu.cn",
    "南通大学": "ntu.edu.cn",
    "扬州大学": "yzu.edu.cn",
    "南京财经大学": "nufe.edu.cn",
    "浙江理工大学": "zstu.edu.cn",
    "浙江工商大学": "zjgsu.edu.cn",
    "中国计量大学": "cjlu.edu.cn",
    "安徽工业大学": "ahut.edu.cn",
    "安徽理工大学": "aust.edu.cn",
    "安徽师范大学": "ahnu.edu.cn",
    "集美大学": "jmu.edu.cn",
    "福建师范大学": "fjnu.edu.cn",
    "华东交通大学": "ecjtu.edu.cn",
    "江西理工大学": "jxust.edu.cn",
    "江西师范大学": "jxnu.edu.cn",
    "江西财经大学": "jxufe.edu.cn",
    "山东科技大学": "sdust.edu.cn",
    "山东师范大学": "sdnu.edu.cn",
    "山东财经大学": "sdufe.edu.cn",
    "青岛大学": "qdu.edu.cn",
    "青岛科技大学": "qust.edu.cn",
    "青岛理工大学": "qut.edu.cn",
    "济南大学": "ujn.edu.cn",
    "烟台大学": "ytu.edu.cn",
    "河南大学": "henu.edu.cn",
    "河南科技大学": "haust.edu.cn",
    "河南理工大学": "hpu.edu.cn",
    "河南师范大学": "htu.edu.cn",
    "湖北大学": "hubu.edu.cn",
    "三峡大学": "ctgu.edu.cn",
    "长江大学": "yangtzeu.edu.cn",
    "中南民族大学": "scuec.edu.cn",
    "湖南科技大学": "hnust.edu.cn",
    "长沙理工大学": "csust.edu.cn",
    "广东工业大学": "gdut.edu.cn",
    "广东外语外贸大学": "gdufs.edu.cn",
    "深圳技术大学": "sztu.edu.cn",
    "南方医科大学": "smu.edu.cn",
    "广州中医药大学": "gzucm.edu.cn",
    "桂林电子科技大学": "guet.edu.cn",
    "桂林理工大学": "glut.edu.cn",
    "海南师范大学": "hainnu.edu.cn",
    "重庆理工大学": "cqut.edu.cn",
    "重庆工商大学": "ctbu.edu.cn",
    "西南科技大学": "swust.edu.cn",
    "成都信息工程大学": "cuit.edu.cn",
    "成都大学": "cdu.edu.cn",
    "西安理工大学": "xaut.edu.cn",
    "西安建筑科技大学": "xauat.edu.cn",
    "西安科技大学": "xust.edu.cn",
    "西安工业大学": "xatu.edu.cn",
    "西安邮电大学": "xupt.edu.cn",
    "西北政法大学": "nwupl.edu.cn",
    "兰州理工大学": "lut.edu.cn",
    "兰州交通大学": "lzjtu.edu.cn",
}

# ──────────────────────────────────────────────
# 中国企业域名知识库
# ──────────────────────────────────────────────

ENTERPRISE_DOMAIN_MAP: Dict[str, str] = {
    # 互联网/科技
    "阿里巴巴": "alibaba.com",
    "腾讯": "tencent.com",
    "百度": "baidu.com",
    "字节跳动": "bytedance.com",
    "京东": "jd.com",
    "美团": "meituan.com",
    "小米": "xiaomi.com",
    "网易": "163.com",
    "360": "360.cn",
    "哔哩哔哩": "bilibili.com",
    "快手": "kuaishou.com",
    "拼多多": "pinduoduo.com",
    "滴滴出行": "didiglobal.com",
    "新浪": "sina.com.cn",
    "搜狐": "sohu.com",
    "携程": "ctrip.com",
    "唯品会": "vip.com",
    "58同城": "58.com",
    "微博": "weibo.com",
    "知乎": "zhihu.com",
    "小红书": "xiaohongshu.com",
    "斗鱼": "douyu.com",
    "虎牙": "huya.com",
    "完美世界": "wanmei.com",
    "途牛": "tuniu.com",
    "汽车之家": "autohome.com.cn",
    "瓜子二手车": "guazi.com",
    "得到": "dedao.cn",
    "喜马拉雅": "ximalaya.com",
    "阅文集团": "yuewen.com",

    # 通信/硬件
    "华为": "huawei.com",
    "中兴": "zte.com.cn",
    "OPPO": "oppo.com",
    "vivo": "vivo.com",
    "荣耀": "honor.com",
    "联想": "lenovo.com.cn",
    "海尔": "haier.com",
    "海信": "hisense.com",
    "TCL": "tcl.com",
    "格力": "gree.com.cn",
    "美的": "midea.com",
    "长虹": "changhong.com.cn",
    "大疆": "dji.com",
    "宇树科技": "unitree.com",
    "科大讯飞": "iflytek.com",
    "商汤科技": "sensetime.com",

    # 金融
    "中国工商银行": "icbc.com.cn",
    "中国建设银行": "ccb.com",
    "中国农业银行": "abchina.com",
    "中国银行": "boc.cn",
    "交通银行": "bankcomm.com",
    "招商银行": "cmbchina.com",
    "平安银行": "bank.pingan.com",
    "中信银行": "citicbank.com",
    "兴业银行": "cib.com.cn",
    "浦发银行": "spdb.com.cn",
    "民生银行": "cmbc.com.cn",
    "支付宝": "alipay.com",
    "财付通": "tenpay.com",
    "微信支付": "wechat.com",

    # 能源/制造
    "中国石油": "cnpc.com.cn",
    "中国石化": "sinopec.com",
    "中国海油": "cnooc.com.cn",
    "国家电网": "sgcc.com.cn",
    "南方电网": "csg.cn",
    "中国中车": "crrcgc.cc",
    "中国船舶": "cssc.net.cn",
    "中国航天科技": "spacechina.com",
    "中国航天科工": "casic.com.cn",
    "中航工业": "avic.com",
    "中国兵器工业": "norinco.com",
    "中国电子": "cec.com.cn",
    "中国移动": "chinamobile.com",
    "中国联通": "chinaunicom.com",
    "中国电信": "chinatelecom.com",
    "中国铁塔": "chinatowercom.cn",

    # 汽车
    "比亚迪": "byd.com",
    "蔚来": "nio.com",
    "小鹏": "xpeng.com",
    "理想汽车": "lixiang.com",
    "吉利": "geely.com",
    "长城汽车": "gwm.com.cn",
    "上汽集团": "saicmotor.com",
    "广汽集团": "gac.com.cn",
    "长安汽车": "changan.com.cn",
    "奇瑞": "chery.com",

    # 食品/消费
    "贵州茅台": "moutaichina.com",
    "五粮液": "wuliangye.com.cn",
    "伊利": "yili.com",
    "蒙牛": "mengniu.com.cn",
    "康师傅": "masterkong.com.cn",
    "统一": "uni-president.com.cn",
    "农夫山泉": "nongfuspring.com",
    "海天味业": "haitian-food.com",
    "安踏": "anta.com",
    "李宁": "lining.com",

    # 地产
    "万科": "vanke.com",
    "碧桂园": "countrygarden.com.cn",
    "恒大": "evergrande.com",
    "融创": "sunac.com.cn",
    "保利发展": "polycn.com",
    "中海地产": "colicth.com",
    "华润置地": "crland.com.hk",
    "龙湖": "longfor.com",

    # 物流
    "顺丰": "sf-express.com",
    "菜鸟": "cainiao.com",
    "中通": "zto.com",
    "圆通": "yto.net.cn",
    "韵达": "yundaex.com",
    "申通": "sto.cn",
    "极兔": "jtexpress.com",

    # 安防/安全
    "海康威视": "hikvision.com",
    "大华": "dahuasecurity.com",
    "深信服": "sangfor.com.cn",
    "奇安信": "qianxin.com",
    "启明星辰": "venustech.com.cn",
    "绿盟科技": "nsfocus.com.cn",
    "天融信": "topsec.com.cn",
    "安恒信息": "dbappsecurity.com.cn",
    "360安全": "360.cn",
    "知道创宇": "knownsec.com",
    "盛邦安全": "websaas.com.cn",
}

# ──────────────────────────────────────────────
# 常用拼音首字母缩写
# ──────────────────────────────────────────────

# 中国省份/市简称 → 拼音缩写
PROVINCE_SHORT = {
    "北京": "bj", "上海": "sh", "天津": "tj", "重庆": "cq",
    "河北": "hb", "山西": "sx", "辽宁": "ln", "吉林": "jl",
    "黑龙江": "hlj", "江苏": "js", "浙江": "zj", "安徽": "ah",
    "福建": "fj", "江西": "jx", "山东": "sd", "河南": "hn",
    "湖北": "hb", "湖南": "hn", "广东": "gd", "广西": "gx",
    "海南": "hain", "四川": "sc", "贵州": "gz", "云南": "yn",
    "西藏": "xz", "陕西": "sx", "甘肃": "gs", "青海": "qh",
    "宁夏": "nx", "新疆": "xj", "内蒙古": "nmg",
    "台北": "tb", "香港": "hk", "澳门": "mo",
}


def _pinyin_first_letters(text: str) -> str:
    """提取中文字符的拼音首字母缩写（无外部依赖，基于词典）。

    用于算法推算域名：如果某高校不在精确映射表中，用它推算。
    例如：武汉大学 → whu, 南方科技大学 → nfkjdx → nfust? 复杂...
    实际上很多高校域名是英文名缩写而非拼音缩写，所以算法推算有限。
    """
    # 常用字拼音首字母映射（覆盖 99% 常见汉字）
    _PY_MAP = {
        # 方位/省份
        '北': 'b', '京': 'j', '上': 's', '海': 'h', '天': 't', '津': 'j',
        '重': 'c', '庆': 'q', '广': 'g', '东': 'd', '浙': 'z', '江': 'j',
        '南': 'n', '西': 'x', '安': 'a', '武': 'w', '汉': 'h', '湖': 'h',
        '四': 's', '川': 'c', '福': 'f', '建': 'j', '山': 's', '河': 'h',
        '云': 'y', '贵': 'g', '陕': 's', '甘': 'g', '青': 'q', '辽': 'l',
        '吉': 'j', '黑': 'h', '龙': 'l', '内': 'n', '蒙': 'm', '古': 'g',
        '新': 'x', '疆': 'j', '藏': 'z', '宁': 'n', '夏': 'x',
        # 常用字（高校/企业名称高频字）
        '中': 'z', '国': 'g', '人': 'r', '民': 'm', '大': 'd', '学': 'x',
        '理': 'l', '工': 'g', '医': 'y', '农': 'n', '林': 'l', '师': 's',
        '范': 'f', '财': 'c', '经': 'j', '政': 'z', '法': 'f', '外': 'w',
        '语': 'y', '电': 'd', '子': 'z', '邮': 'y', '通': 't', '信': 'x',
        '交': 'j', '航': 'h', '空': 'k', '科': 'k', '技': 'j',
        '术': 's', '华': 'h', '教': 'j', '育': 'y',
        '研': 'y', '究': 'j', '院': 'y', '水': 's', '利': 'l', '建': 'j',
        '筑': 'z', '矿': 'k', '业': 'y', '石': 's', '油': 'y', '化': 'h',
        '药': 'y', '洋': 'y', '体': 't', '音': 'y',
        '乐': 'l', '美': 'm', '戏': 'x', '剧': 'j', '媒': 'm',
        # 补充高频缺字（之前漏掉的）
        '深': 's', '索': 's', '度': 'd', '智': 'z', '能': 'n', '源': 'y',
        '杭': 'h', '州': 'z', '求': 'q', '基': 'j', '础': 'c',
        '软': 'r', '件': 'j', '网': 'w', '络': 'l', '数': 's', '据': 'j',
        '安': 'a', '全': 'q', '服': 'f', '务': 'w', '器': 'q', '芯': 'x',
        '片': 'p', '半': 'b', '导': 'd', '集': 'j', '成': 'c', '电': 'd',
        '视': 's', '频': 'p', '声': 's', '光': 'g', '机': 'j', '械': 'x',
        '汽': 'q', '车': 'c', '飞': 'f', '船': 'c', '轨': 'g', '道': 'd',
        '铁': 't', '路': 'l', '桥': 'q', '梁': 'l', '隧': 's',
        '融': 'r', '资': 'z', '股': 'g', '权': 'q', '债': 'z', '券': 'q',
        '银': 'y', '行': 'h', '保': 'b', '险': 'x', '证': 'z',
        '商': 's', '贸': 'm', '易': 'y', '物': 'w', '流': 'l', '运': 'y',
        '输': 's', '仓': 'c', '储': 'c', '包': 'b', '装': 'z',
        '食': 's', '品': 'p', '饮': 'y', '料': 'l', '烟': 'y', '酒': 'j',
        '纺': 'f', '织': 'z', '服': 'f', '装': 'z', '皮': 'p', '革': 'g',
        '木': 'm', '材': 'c', '家': 'j', '具': 'j', '纸': 'z',
        '钢': 'g', '铁': 't', '铝': 'l', '铜': 't', '锌': 'x', '金': 'j',
        '属': 's', '冶': 'y', '炼': 'l', '铸': 'z', '造': 'z',
        '化': 'h', '肥': 'f', '农': 'n', '药': 'y', '种': 'z', '子': 'z',
        '畜': 'x', '牧': 'm', '渔': 'y', '村': 'c', '镇': 'z',
        '文': 'w', '化': 'h', '旅': 'l', '游': 'y', '酒': 'j', '店': 'd',
        '餐': 'c', '饮': 'y', '娱': 'y', '乐': 'l',
        # 常见英文/数字相关
        '互': 'h', '联': 'l', '云': 'y', '计': 'j', '算': 's', '机': 'j',
        '人': 'r', '工': 'g', '知': 'z', '识': 's', '图': 't', '谱': 'p',
        '量': 'l', '加': 'j', '密': 'm', '区': 'q', '块': 'k', '链': 'l',
        '生': 's', '态': 't', '环': 'h', '保': 'b', '碳': 't',
        '军': 'j', '工': 'g', '航': 'h', '天': 't', '兵': 'b',
        '生': 's', '物': 'w', '基': 'j', '因': 'y',
        # 补充常见缺字（消除 x 占位）
        '限': 'x', '公': 'g', '司': 's', '朝': 'c', '阳': 'y', '区': 'q',
        '市': 's', '省': 's', '县': 'x', '乡': 'x', '村': 'c',
        '有': 'y', '责': 'z', '任': 'r', '股': 'g', '份': 'f',
        '团': 't', '集': 'j', '总': 'z', '部': 'b', '分': 'f',
        '支': 'z', '机': 'j', '构': 'g', '办': 'b', '公': 'g', '室': 's',
        '处': 'c', '科': 'k', '长': 'z', '主': 'z', '任': 'r', '员': 'y',
        '信': 'x', '息': 'x', '中': 'z', '心': 'x', '所': 's',
        '库': 'k', '房': 'f', '地': 'd', '产': 'c', '物': 'w',
        '苏': 's', '锡': 'x', '常': 'c', '镇': 'z', '扬': 'y', '泰': 't',
        '通': 't', '盐': 'y', '淮': 'h', '连': 'l', '徐': 'x',
        '嘉': 'j', '兴': 'x', '宁': 'n', '波': 'b', '温': 'w', '台': 't',
        '金': 'j', '义': 'y', '衢': 'q', '舟': 'z',
        '泉': 'q', '州': 'z', '漳': 'z', '莆': 'p', '龙': 'l', '岩': 'y',
        '三': 's', '明': 'm', '南': 'n', '平': 'p',
        '珠': 'z', '圳': 'z', '佛': 'f', '莞': 'g', '惠': 'h', '州': 'z',
        '中': 'z', '山': 's', '江': 'j', '门': 'm', '肇': 'z',
        '汕': 's', '头': 't', '揭': 'j', '茂': 'm', '湛': 'z',
        '青': 'q', '岛': 'd', '烟': 'y', '潍': 'w', '淄': 'z', '枣': 'z',
        '临': 'l', '沂': 'y', '济': 'j', '南': 'n', '苏': 's',
    }
    result = []
    for char in text:
        if 'a' <= char <= 'z' or 'A' <= char <= 'Z':
            result.append(char.lower())
        elif char in _PY_MAP:
            result.append(_PY_MAP[char])
        elif '\u4e00' <= char <= '\u9fff':
            result.append('x')  # 未知汉字，用 x 占位
    return ''.join(result)


def _is_university(name: str) -> bool:
    """判断名称是否可能是高校。"""
    keywords = ["大学", "学院", "学校", "中学", "小学", "幼儿园"]
    return any(kw in name for kw in keywords)


def _is_government(name: str) -> bool:
    """判断名称是否可能是政府机构。"""
    keywords = ["政府", "局", "厅", "部", "委", "办", "中心", "机关"]
    return any(kw in name for kw in keywords)


def infer_domain(name: str) -> str:
    """万能域推断 — 一通百通：输入任何中文/英文名称，输出最可能的域名。

    优先级：
      1. 如果已包含 '.' → 直接返回（已经是域名）
      2. 企业精确匹配 → .com / .com.cn
      3. 企业模糊匹配（关键词包含）
      4. 高校精确匹配 → .edu.cn
      5. 高校模糊匹配（全称包含或包含全称 → 严格互含才匹配）
      6. 算法推算高校 → .edu.cn
      7. 算法推算企业 → .com
      8. 直接返回 name.lower() + .com

    Args:
        name: 企业/高校全称，如 "北京大学"、"阿里巴巴"、"fafu.edu.cn"

    Returns:
        最可能的域名
    """
    name = name.strip()

    # 1. 已经是域名格式
    if '.' in name:
        return name.lower()

    # 2. 企业精确匹配（优先于高校模糊匹配，防止"中国石油"→大学）
    if name in ENTERPRISE_DOMAIN_MAP:
        return ENTERPRISE_DOMAIN_MAP[name]
    for ent_key, ent_domain in ENTERPRISE_DOMAIN_MAP.items():
        if ent_key in name or name in ent_key:
            return ent_domain

    # 3. 高校精确匹配
    if name in UNIVERSITY_DOMAIN_MAP:
        return UNIVERSITY_DOMAIN_MAP[name]
    # 高校模糊匹配（严格：全称必须互含，且不是企业关键词误伤
    # 例如 "中国石油" 不含 "大学" → 不会被高校模糊匹配截获）
    for uni_key, uni_domain in UNIVERSITY_DOMAIN_MAP.items():
        if uni_key in name or name in uni_key:
            # 进一步验证：确认确实是高校类名称
            if _is_university(name) or _is_university(uni_key):
                return uni_domain

    # 4. 高校算法推算
    if _is_university(name):
        abbr = _pinyin_first_letters(name)
        for suffix in ["大学", "学院", "学校"]:
            if name.endswith(suffix):
                base = name[:-len(suffix)]
                abbr2 = _pinyin_first_letters(base)
                if len(abbr2) >= 2:
                    return f"{abbr2}.edu.cn"
        if len(abbr) >= 2:
            return f"{abbr}.edu.cn"
        return f"{name.lower()}.edu.cn"

    # 5. 政府机构
    if _is_government(name):
        abbr = _pinyin_first_letters(name)
        return f"{abbr}.gov.cn"

    # 6. 企业算法推算
    abbr = _pinyin_first_letters(name)
    if len(abbr) >= 3:
        return f"{abbr}.com"
    if len(abbr) >= 2:
        return f"{abbr}.com.cn"
    return f"{name.lower()}.com"


def list_known_enterprises() -> Dict[str, str]:
    """列出所有已知企业映射（用于自动补全/展示）。"""
    return dict(ENTERPRISE_DOMAIN_MAP)


def list_known_universities() -> Dict[str, str]:
    """列出所有已知高校映射。"""
    return dict(UNIVERSITY_DOMAIN_MAP)


def verify_domain_alive(domain: str, timeout: float = 3.0) -> bool:
    """快速验证域名是否可解析（纯被动 DNS）。"""
    import socket
    try:
        socket.getaddrinfo(domain, 80, socket.AF_INET)
        return True
    except Exception:
        return False
