import type { Nine } from "./types";

/** Site text for dialogs. */
export const dialogs = {
  "modal.close": ["Close dialog", "Cerrar diálogo", "Fermer la boîte de dialogue", "Dialog schließen", "Chiudi la finestra", "Fechar diálogo", "ダイアログを閉じる", "关闭对话框", "대화상자 닫기"],
} as const satisfies Record<string, Nine>;
