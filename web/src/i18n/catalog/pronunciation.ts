import type { Nine } from "./types";

/** Site text for pronunciation and translation. */
export const pronunciation = {
  "reading.show": ["Show pronunciation", "Mostrar pronunciación", "Afficher la prononciation", "Aussprache anzeigen", "Mostra la pronuncia", "Mostrar pronúncia", "発音を表示", "显示发音", "발음 보기"],
  "reading.hide": ["Hide pronunciation", "Ocultar pronunciación", "Masquer la prononciation", "Aussprache ausblenden", "Nascondi la pronuncia", "Ocultar pronúncia", "発音を隠す", "隐藏发音", "발음 숨기기"],
  "reading.kind.ipa": ["IPA", "AFI", "API", "IPA", "IPA", "AFI", "IPA（国際音声記号）", "国际音标（IPA）", "IPA(국제음성기호)"],
  "reading.kind.pinyin": ["Pinyin", "Pinyin", "Pinyin", "Pinyin", "Pinyin", "Pinyin", "ピンイン", "拼音", "병음"],
  "reading.kind.romaji": ["Romaji", "Romaji", "Romaji", "Romaji", "Romaji", "Romaji", "ローマ字", "罗马字", "로마자(일본어)"],
  "reading.kind.romanization": ["Romanization", "Romanización", "Romanisation", "Romanisierung", "Romanizzazione", "Romanização", "ローマ字表記", "罗马字转写", "로마자 표기"],
  "reading.approx": ["Written by the tutor: a guide, not a dictionary.", "Escrito por el tutor: una guía, no un diccionario.", "Écrit par le tuteur : un repère, pas un dictionnaire.", "Vom Tutor geschrieben: eine Orientierung, kein Wörterbuch.", "Scritto dal tutor: una guida, non un dizionario.", "Escrito pelo tutor: um guia, não um dicionário.", "チューターが作成：目安であり、辞書ではありません。", "由导师编写：仅供参考，不等同于词典。", "튜터가 작성했어요. 참고용이며 사전은 아니에요."],
  "reading.loading": ["Writing the pronunciation…", "Escribiendo la pronunciación…", "Écriture de la prononciation…", "Aussprache wird geschrieben …", "Scrittura della pronuncia…", "Escrevendo a pronúncia…", "発音を作成中…", "正在生成发音…", "발음을 만드는 중…"],
  "reading.none": ["No pronunciation came back for this line.", "No llegó la pronunciación de esta línea.", "Aucune prononciation reçue pour cette ligne.", "Für diese Zeile kam keine Aussprache zurück.", "Nessuna pronuncia per questa riga.", "Nenhuma pronúncia voltou para esta linha.", "この行の発音は取得できませんでした。", "这一行没有得到发音。", "이 줄의 발음을 받지 못했어요."],
  "translate.open": ["Translate", "Traducir", "Traduire", "Übersetzen", "Traduci", "Traduzir", "翻訳", "翻译", "번역"],
  "translate.close": ["Hide translation", "Ocultar traducción", "Masquer la traduction", "Übersetzung ausblenden", "Nascondi la traduzione", "Ocultar tradução", "翻訳を隠す", "隐藏翻译", "번역 숨기기"],
  "translate.into": ["Translate into", "Traducir al", "Traduire en", "Übersetzen nach", "Traduci in", "Traduzir para", "翻訳先", "翻译成", "번역할 언어"],
  "translate.go": ["Translate", "Traducir", "Traduire", "Übersetzen", "Traduci", "Traduzir", "翻訳する", "开始翻译", "번역하기"],
  "translate.loading": ["Translating…", "Traduciendo…", "Traduction…", "Übersetze …", "Traduzione…", "Traduzindo…", "翻訳中…", "翻译中…", "번역 중…"],
  "translate.missing": ["(no translation came back)", "(no llegó la traducción)", "(aucune traduction reçue)", "(keine Übersetzung erhalten)", "(nessuna traduzione ricevuta)", "(a tradução não voltou)", "（翻訳が取得できませんでした）", "（没有得到翻译）", "(번역을 받지 못했어요)"],
  "translate.hint": ["The tutor writes the translation when you ask. It is not saved.", "El tutor escribe la traducción cuando lo pides. No se guarda.", "Le tuteur écrit la traduction à ta demande. Elle n'est pas enregistrée.", "Der Tutor schreibt die Übersetzung auf Wunsch. Sie wird nicht gespeichert.", "Il tutor scrive la traduzione quando lo chiedi. Non viene salvata.", "O tutor escreve a tradução quando você pede. Ela não é salva.", "チューターが依頼に応じて翻訳します。保存はされません。", "导师会在你需要时翻译，翻译不会被保存。", "요청하면 튜터가 번역해요. 저장되지는 않아요."],
  "translate.selectWords": ["Translate the selected words", "Traducir las palabras seleccionadas", "Traduire les mots sélectionnés", "Ausgewählte Wörter übersetzen", "Traduci le parole selezionate", "Traduzir as palavras selecionadas", "選択した単語を翻訳", "翻译所选单词", "선택한 단어 번역"],
  "translate.tooMany": ["Select at most 60 words to translate at once.", "Selecciona como máximo 60 palabras para traducir a la vez.", "Sélectionne au plus 60 mots à traduire à la fois.", "Wähle höchstens 60 Wörter auf einmal zum Übersetzen.", "Seleziona al massimo 60 parole da tradurre insieme.", "Selecione no máximo 60 palavras para traduzir de uma vez.", "一度に翻訳できるのは60語までです。", "一次最多选择60个单词翻译。", "한 번에 최대 60개까지 선택할 수 있어요."],
} as const satisfies Record<string, Nine>;
