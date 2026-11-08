"""Chinese, Japanese and Korean: particles and measure words, the mistakes that have a fixed right answer.

Korean particles follow the sound of the last syllable of the noun (은/는, 이/가, 을/를, 과/와, 으로/로, 이에요/예요): they are checked
after a noun the code knows (the learner's words and the nouns below), because a word that merely ends in 이 or 가 is not a particle.
"""
from __future__ import annotations

import re

from .rules_common import Ctx, hit

# --- Korean --------------------------------------------------------------------------------------------------------------------------

_KO_NOUNS = ("물 빵 커피 우유 밥 생선 사과 계란 치즈 친구 가족 어머니 아버지 아이 집 학교 도시 거리 가게 일 책 오늘 내일 고양이 개 나무 꽃 하늘 "
             "바다 산 강 사람 선생님 학생 의사 음식 책상 의자 문 창문 버스 기차 공원 시장 병원 은행 시간 이름 나라 마을 아침 저녁 점심 비 눈 "
             "바람 영화 노래 공부 운동 여행 선물").split()          # "차" is left out: "차이" (difference) is a word of its own
_HANGUL = re.compile(r"[가-힣]")


def _batchim(ch: str) -> int:
    """0 when the syllable ends in a vowel, 8 for ㄹ, another number for any other final consonant."""
    return (ord(ch) - 0xAC00) % 28


def _ko_stems(words) -> list:
    stems = set(_KO_NOUNS)
    for w in words:
        w = w.strip()
        if 1 <= len(w) <= 4 and all(_HANGUL.match(c) for c in w) and not w.endswith(("다", "요", "까", "니다")):
            stems.add(w)
    return sorted(stems, key=len, reverse=True)


def ko_particles(ctx: Ctx) -> list:
    out = []
    for stem in _ko_stems(ctx.words):
        b = _batchim(stem[-1])
        wrong = ["이랑", "으로", "이에요", "은", "이", "을", "과"] if b == 0 else ["랑", "가", "는", "를", "와", "예요"]
        if b == 8:
            wrong = wrong + ["으로"] if "으로" not in wrong else wrong
        elif b:
            wrong = wrong + ["로"]
        right = {"이랑": "랑", "으로": "로", "이에요": "예요", "은": "는", "이": "가", "을": "를", "과": "와",
                 "랑": "이랑", "가": "이", "는": "은", "를": "을", "와": "과", "예요": "이에요", "로": "으로"}
        pattern = re.compile(re.escape(stem) + "(" + "|".join(sorted(set(wrong), key=len, reverse=True)) + ")(?![가-힣])")
        for m in pattern.finditer(ctx.text):
            particle = m.group(1)
            fix_particle = right[particle]
            if b == 8 and particle == "으로":
                fix_particle = "로"
            out.append(hit(ctx, "particle", m.start(), m.end(), stem + fix_particle, True,
                           f'after "{stem}" the particle is {fix_particle}'))
    return out


def ko_double_particle(ctx: Ctx) -> list:
    return [hit(ctx, "particle", m.start(), m.end(), m.group(0)[0], False, "two particles in a row")
            for m in re.finditer(r"(?<=[가-힣])(을를|를을|은는|는은)(?![가-힣])", ctx.text)]


# --- Japanese ------------------------------------------------------------------------------------------------------------------------

_JA_PLACES = "学校|会社|店|駅|病院|銀行|図書館|空港|家"
_JA_THINGS = "水|お茶|パン|ご飯|本|コーヒー|牛乳|りんご|卵|新聞|映画|手紙|肉"


def ja_rules(ctx: Ctx) -> list:
    out = []
    for m in re.finditer(rf"({_JA_PLACES})を(行|来|帰)", ctx.text):
        at = m.start() + len(m.group(1))
        out.append(hit(ctx, "particle", at, at + 1, "に", True, f'"{m.group(1)}" is where you go: に, not を'))
    for m in re.finditer(rf"({_JA_THINGS})が(飲み|食べ|読み|買い|見|書き|聞き)(ます|ません|ました|ましょう)", ctx.text):
        at = m.start() + len(m.group(1))
        out.append(hit(ctx, "particle", at, at + 1, "を", True, f'"{m.group(1)}" is the object: を, not が'))
    for m in re.finditer(r"を(好き|嫌い|上手|下手|分かり|わかり|できま|できる|できた)", ctx.text):
        out.append(hit(ctx, "particle", m.start(), m.start() + 1, "が", False, f'"{m.group(1)}" takes が'))
    for m in re.finditer(r"る(ます|ません|ました|ましょう)", ctx.text):
        out.append(hit(ctx, "verb_form", m.start(), m.end(), "", False, "ます attaches to the stem, not to the dictionary form"))
    for m in re.finditer(r"(だです|でです|ですです|ますです|ますでした|ますだ)", ctx.text):
        out.append(hit(ctx, "verb_form", m.start(), m.end(), "", False, "two endings in a row"))
    for m in re.finditer(r"(を|が)\1", ctx.text):
        out.append(hit(ctx, "particle", m.start(), m.end(), m.group(1), True, "the same particle twice"))
    return out


# --- Chinese -------------------------------------------------------------------------------------------------------------------------

_ZH_CLASSIFIER = {"书": "本", "猫": "只", "狗": "只", "鱼": "条", "车": "辆", "桌子": "张", "椅子": "把", "纸": "张", "路": "条", "河": "条",
                  "山": "座", "花": "朵", "树": "棵"}


def zh_rules(ctx: Ctx) -> list:
    out = []
    nouns = "|".join(sorted(_ZH_CLASSIFIER, key=len, reverse=True))
    for m in re.finditer(rf"([一二两三四五六七八九十几每])个({nouns})", ctx.text):
        right = _ZH_CLASSIFIER[m.group(2)]
        out.append(hit(ctx, "measure_word", m.start() + 1, m.start() + 2, right, True, f'"{m.group(2)}" takes the measure word {right}, not 个'))
    for m in re.finditer(r"(?<![第十百千万零一二三四五六七八九])二(?=[个本只条张辆杯件位])", ctx.text):
        out.append(hit(ctx, "numeral", m.start(), m.end(), "两", True, "before a measure word: 两, not 二"))
    for m in re.finditer(r"不有", ctx.text):
        out.append(hit(ctx, "negation", m.start(), m.end(), "没有", True, "the negative of 有 is 没有"))
    for m in re.finditer(r"(的|着|过|吗|呢|吧)\1", ctx.text):
        out.append(hit(ctx, "doubled_particle", m.start(), m.end(), m.group(1), True, "the same particle twice"))
    return out


RULES = {"ko": [ko_particles, ko_double_particle], "ja": [ja_rules], "zh": [zh_rules]}
