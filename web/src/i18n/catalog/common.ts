import type { Nine } from "./types";

/** Site text for words used everywhere. */
export const common = {
  "common.loading": ["Loading…", "Cargando…", "Chargement…", "Wird geladen …", "Caricamento…", "Carregando…", "読み込み中…", "加载中…", "불러오는 중…"],
  "common.cancel": ["Cancel", "Cancelar", "Annuler", "Abbrechen", "Annulla", "Cancelar", "キャンセル", "取消", "취소"],
  "common.delete": ["Delete", "Eliminar", "Supprimer", "Löschen", "Elimina", "Excluir", "削除", "删除", "삭제"],
  "common.clear": ["Clear", "Quitar", "Effacer", "Aufheben", "Deseleziona", "Limpar", "解除", "清除", "해제"],
  "common.add": ["Add", "Añadir", "Ajouter", "Hinzufügen", "Aggiungi", "Adicionar", "追加", "添加", "추가"],
  "common.back": ["Back", "Volver", "Retour", "Zurück", "Indietro", "Voltar", "戻る", "返回", "뒤로"],
  "common.previous": ["Previous", "Anterior", "Précédent", "Zurück", "Precedente", "Anterior", "前へ", "上一页", "이전"],
  "common.next": ["Next", "Siguiente", "Suivant", "Weiter", "Avanti", "Próximo", "次へ", "下一页", "다음"],
  "common.close": ["Close", "Cerrar", "Fermer", "Schließen", "Chiudi", "Fechar", "閉じる", "关闭", "닫기"],
  "common.open": ["Open", "Abrir", "Ouvrir", "Öffnen", "Apri", "Abrir", "開く", "打开", "열기"],
  "common.send": ["Send", "Enviar", "Envoyer", "Senden", "Invia", "Enviar", "送信", "发送", "보내기"],
  "common.tryAgain": ["Try again", "Intentar de nuevo", "Réessayer", "Erneut versuchen", "Riprova", "Tentar novamente", "もう一度試す", "重试", "다시 시도"],
  "common.range": ["{from}–{to} of {total}", "{from}–{to} de {total}", "{from}–{to} sur {total}", "{from}–{to} von {total}", "{from}–{to} di {total}", "{from}–{to} de {total}", "{total} 件中 {from}–{to} 件", "共 {total} 条，第 {from}–{to} 条", "총 {total}개 중 {from}–{to}"],
  "common.looksGood": ["Looks good", "Se ve bien", "Tout est bon", "Sieht gut aus", "Va bene", "Está bom", "問題ありません", "看起来不错", "좋아 보여요"],
  "common.needsLook": ["Needs a look", "Conviene revisarlo", "À vérifier", "Bitte prüfen", "Da controllare", "Vale a pena conferir", "確認が必要です", "需要看一下", "확인이 필요해요"],
  "common.savedToLibrary": ["Saved to your library", "Guardado en tu biblioteca", "Enregistré dans ta bibliothèque", "In deiner Bibliothek gespeichert", "Salvato nella tua libreria", "Salvo na sua biblioteca", "ライブラリに保存しました", "已保存到你的书库", "라이브러리에 저장했어요"],
  "common.saveFailed": ["Couldn't save. Please try again.", "No se pudo guardar. Inténtalo de nuevo.", "Enregistrement impossible. Réessaie.", "Speichern nicht möglich. Bitte versuche es erneut.", "Impossibile salvare. Riprova.", "Não foi possível salvar. Tente novamente.", "保存できませんでした。もう一度お試しください。", "无法保存，请重试。", "저장하지 못했어요. 다시 시도해 주세요."],
} as const satisfies Record<string, Nine>;
