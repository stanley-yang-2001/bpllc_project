"""Add a starter list of everyday words to one learner, so run_story_batch.py can measure a language.

Run in the container (it uses the same database account as the tools):
    docker compose exec langflow python /app/scripts/seed_batch_words.py --learner-id 197 --languages de,it,pt,zh,ko
    docker compose exec langflow python /app/scripts/seed_batch_words.py --learner-id 197 --languages all

Each language gets 25 common words (nouns a beginner meets first). Words already in the learner's list are left alone, so it is
safe to run twice. It only ADDS words; it never removes or changes any."""
import argparse
import sys

sys.path.insert(0, "/app/custom_components")

WORDS = {
    "de": "Haus Wasser Brot Freund Mutter Vater Buch Schule Katze Hund Tisch Stuhl Apfel Milch Kaffee Straße Auto Zug Garten Blume Sonne Regen Arbeit Lehrer Kind",
    "it": "casa acqua pane amico madre padre libro scuola gatto cane tavolo sedia mela latte caffè strada macchina treno giardino fiore sole pioggia lavoro maestro bambino",
    "pt": "casa água pão amigo mãe pai livro escola gato cachorro mesa cadeira maçã leite café rua carro trem jardim flor sol chuva trabalho professor criança",
    "zh": "房子 水 面包 朋友 妈妈 爸爸 书 学校 猫 狗 桌子 椅子 苹果 牛奶 咖啡 路 汽车 火车 花园 花 太阳 雨 工作 老师 孩子",
    "ko": "집 물 빵 친구 엄마 아빠 책 학교 고양이 개 탁자 의자 사과 우유 커피 길 자동차 기차 정원 꽃 해 비 일 선생님 아이",
    "es": "casa agua pan amigo madre padre libro escuela gato perro mesa silla manzana leche café calle coche tren jardín flor sol lluvia trabajo maestro niño",
    "fr": "maison eau pain ami mère père livre école chat chien table chaise pomme lait café rue voiture train jardin fleur soleil pluie travail professeur enfant",
    "ja": "いえ みず パン ともだち おかあさん おとうさん ほん がっこう ねこ いぬ つくえ いす りんご ぎゅうにゅう コーヒー みち くるま でんしゃ にわ はな たいよう あめ しごと せんせい こども",
}


def word_list(code):
    return WORDS[code].split()


def seed(conn, learner_id, codes):
    """Add the lists; returns {code: (added, already_there)}."""
    from tutor_core import vocab

    summary = {}
    for code in codes:
        added = 0
        for word in word_list(code):
            if vocab.add_word(conn, learner_id, code, word).added:
                added += 1
        summary[code] = (added, len(word_list(code)) - added)
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--learner-id", type=int, required=True)
    parser.add_argument("--languages", default="de,it,pt,zh,ko", help="comma-separated language codes, or 'all'")
    args = parser.parse_args(argv)
    codes = list(WORDS) if args.languages.strip().lower() == "all" else [c.strip() for c in args.languages.split(",") if c.strip()]
    unknown = [c for c in codes if c not in WORDS]
    if unknown:
        print(f"No starter list for: {', '.join(unknown)}. Available: {', '.join(WORDS)}")
        return 2
    from tutor_core import db

    conn = db.connect()
    try:
        for code, (added, there) in seed(conn, args.learner_id, codes).items():
            print(f"{code}: added {added}, already there {there}")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
