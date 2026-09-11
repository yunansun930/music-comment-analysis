"""
Step3 数据清洗 - 清洗规则定义

改进点：
1. 扩充黑名单与停用词表
2. 增加垃圾评论规则库（广告、刷屏、纯符号等）
3. 增加 SimHash 近似去重，避免完全不同但语义雷同的垃圾评论
"""
import re

# 无意义评论精确匹配黑名单（不区分大小写）
COMMENT_BLACKLIST = {
    "666", "6666", "66666", "牛", "牛逼", "赞", "好", "好听", "不错", "喜欢",
    "爱", "爱了", "可以", "行", "ok", "good", "nice", "great", "awesome",
    "哈哈", "哈哈哈", "哈哈哈哈", "呵呵", "嘿嘿", "嘻嘻", "嘤嘤嘤",
    "嗯", "嗯嗯", "哦", "哦哦", "啊", "啊啊", "啊啊啊",
    "111", "222", "233", "2333", "hhh", "hhhhh",
    "打卡", "路过", "沙发", "前排", "占楼",
    "顶", "dd", "DD", "蹲", "蹲一个", "马住", "mark", "MARK", "Mark",
    "👍", "👍👍", "🎉", "💪", "🔥",
    "好棒", "绝绝子", "yyds", "YYDS", "awsl", "AWSL",
    "啊啊啊啊", "啊啊啊啊啊", "好听到爆", "神仙",
    "无限循环", "单曲循环", "刷屏",
}

# 无意义评论正则模式
COMMENT_NOISE_PATTERNS = [
    r"^[\d\s]+$",                       # 纯数字
    r"^[hH]{3,}$",                       # hhh...
    r"^[6]{3,}$",                        # 666...
    r"^[2]{3,}$",                        # 222...
    r"^[啊哈嘿嘻嗯哦哼哇哦嗷呜]{2,}$",    # 纯语气词重复
    r"^[.\.。!！?？~～\s]+$",             # 纯标点
    r"^(?:😂|🤣|😢|😍|👍|💪|🔥|🎉|❤️|💕)+$",  # 纯 emoji 重复
]

# 垃圾评论规则（广告、刷屏、引流等）
SPAM_PATTERNS = [
    r"(加\s*[微Vv]\s*|加\s*qq|加\s*微信|vx\s*[:：]|\d{5,}\s*微信)",
    r"(关注公众号|扫码|二维码|扫一扫|长按复制)",
    r"(http[s]?://|www\.|t\.cn/|dwz\.cn)",
    r"(代刷|淘宝|优惠券|返利|兼职|刷单|招聘)",
    r"(进群|拉群|加群|免费送|免费领|点击链接)",
    r"(.)\1{9,}",  # 同字符重复 10 次以上（刷屏）
]

_SPAM_RE = [re.compile(p, re.IGNORECASE) for p in SPAM_PATTERNS]
_NOISE_RE = [re.compile(p) for p in COMMENT_NOISE_PATTERNS]


def clean_text(text: str) -> str:
    """
    清洗单条评论文本：
    1. 去除首尾空白
    2. 去除特殊控制字符
    3. 合并连续空白
    4. 去除重复标点
    """
    if not isinstance(text, str):
        return ""

    text = text.strip()
    # 去除控制字符和零宽字符
    text = re.sub(r"[\x00-\x08\x0b-\x0c\x0e-\x1f\u200b-\u200f\ufeff]", "", text)
    # 合并连续空白
    text = re.sub(r"\s+", " ", text)
    # 去除连续重复标点，保留一个
    text = re.sub("([。！？，、；：\"\"''（）【】\\[\\]{}])\\1+", "\\1", text)
    return text.strip()


def is_meaningless_comment(text: str) -> bool:
    """判断评论是否无意义。"""
    if not isinstance(text, str):
        return True

    cleaned = clean_text(text)
    if not cleaned:
        return True

    stripped = re.sub("\\s+|[。！？，、；：\"\"''（）【】\\[\\]{}]", "", cleaned)
    if len(stripped) < 3:
        return True

    if stripped.lower() in COMMENT_BLACKLIST:
        return True

    for pat in _NOISE_RE:
        if pat.match(stripped):
            return True

    return False


def is_spam_comment(text: str) -> bool:
    """判断是否垃圾评论（广告、刷屏、引流等）。"""
    if not isinstance(text, str):
        return False
    for pat in _SPAM_RE:
        if pat.search(text):
            return True
    return False


def normalize_comment(text: str) -> str:
    """对有效评论进行规范化处理。"""
    return clean_text(text)


# ==================== SimHash 近似去重 ====================


def _tokenize(text: str) -> list:
    """简易字符级 token 化（中文按 2-gram，英文按空格）。"""
    if not text:
        return []
    tokens = []
    # 英文按空格分词
    for w in text.split():
        if all(ord(c) < 128 for c in w):
            tokens.append(w.lower())
    # 中文按 2-gram
    cn_chars = [c for c in text if ord(c) >= 128]
    for i in range(len(cn_chars) - 1):
        tokens.append(cn_chars[i] + cn_chars[i + 1])
    return tokens


def simhash(text: str, hash_bits: int = 64) -> int:
    """
    计算文本的 SimHash 指纹。

    改进：避免完全不同但语义雷同的垃圾评论被保留。
    """
    tokens = _tokenize(text)
    if not tokens:
        return 0

    v = [0] * hash_bits
    for tok in tokens:
        h = hash(tok) & ((1 << hash_bits) - 1)
        for i in range(hash_bits):
            bit = (h >> i) & 1
            v[i] += 1 if bit else -1

    fingerprint = 0
    for i in range(hash_bits):
        if v[i] > 0:
            fingerprint |= 1 << i
    return fingerprint


def hamming_distance(a: int, b: int) -> int:
    """计算两个 SimHash 指纹的汉明距离。"""
    return bin(a ^ b).count("1")


class SimHashDedup:
    """
    SimHash 近似去重器。

    用法：
        dedup = SimHashDedup(threshold=3)
        if dedup.is_duplicate(text):
            # 跳过该条
        else:
            dedup.add(text)
    """

    def __init__(self, threshold: int = 3, hash_bits: int = 64):
        self.threshold = threshold
        self.hash_bits = hash_bits
        self._fingerprints = []  # list[int]

    def add(self, text: str) -> int:
        fp = simhash(text, self.hash_bits)
        self._fingerprints.append(fp)
        return fp

    def is_duplicate(self, text: str) -> bool:
        """判断该文本与已有指纹是否近似重复（汉明距离 <= threshold）。"""
        fp = simhash(text, self.hash_bits)
        for existing in self._fingerprints:
            if hamming_distance(fp, existing) <= self.threshold:
                return True
        return False

    def __len__(self):
        return len(self._fingerprints)
