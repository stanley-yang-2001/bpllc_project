import type { Nine } from "./types";

/** Site text for the reader: a story with the learner's own words underlined and a card for the word that was tapped. */
export const reader = {
  "reader.hint": [
    "Your words are underlined. Tap any word to hear it, see what it means or add it to your words.",
    "Tus palabras están subrayadas. Toca cualquier palabra para oírla, ver qué significa o añadirla a tus palabras.",
    "Tes mots sont soulignés. Touche un mot pour l'écouter, voir ce qu'il veut dire ou l'ajouter à tes mots.",
    "Deine Wörter sind unterstrichen. Tippe auf ein Wort, um es zu hören, seine Bedeutung zu sehen oder es zu deinen Wörtern hinzuzufügen.",
    "Le tue parole sono sottolineate. Tocca una parola per ascoltarla, vedere cosa significa o aggiungerla alle tue parole.",
    "As suas palavras estão sublinhadas. Toque numa palavra para ouvi-la, ver o que significa ou adicioná-la às suas palavras.",
    "あなたの単語には下線が引かれています。単語をタップすると、発音を聞いたり、意味を見たり、単語リストに追加したりできます。",
    "你的单词带有下划线。点按任意单词即可听发音、查看含义，或将其添加到你的单词中。",
    "내 단어에는 밑줄이 있습니다. 단어를 누르면 발음을 듣고, 뜻을 보고, 내 단어에 추가할 수 있습니다.",
  ],
  "reader.card": ["About this word", "Sobre esta palabra", "À propos de ce mot", "Zu diesem Wort", "Su questa parola", "Sobre esta palavra", "この単語について", "关于这个单词", "이 단어에 대해"],
  "reader.notInList": [
    "“{word}” is not in your words yet.",
    "«{word}» todavía no está en tus palabras.",
    "« {word} » n'est pas encore dans tes mots.",
    "„{word}“ ist noch nicht in deinen Wörtern.",
    "«{word}» non è ancora tra le tue parole.",
    "“{word}” ainda não está nas suas palavras.",
    "「{word}」はまだ単語リストにありません。",
    "“{word}”还不在你的单词中。",
    "“{word}”은(는) 아직 내 단어에 없습니다.",
  ],
  "reader.noMeaning": [
    "No meaning saved yet.",
    "Todavía no hay significado guardado.",
    "Aucun sens enregistré pour l'instant.",
    "Noch keine Bedeutung gespeichert.",
    "Nessun significato salvato per ora.",
    "Ainda não há significado guardado.",
    "意味はまだ保存されていません。",
    "还没有保存含义。",
    "저장된 뜻이 아직 없습니다.",
  ],
} as const satisfies Record<string, Nine>;
